from __future__ import annotations

from datetime import datetime

from fastapi import Body, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api

STATUS_COMERCIAIS = {
    "novo",
    "confirmado",
    "em_preparacao",
    "pronto_retirada",
    "enviado",
    "concluido",
    "cancelado",
}

TRANSICOES_COMERCIAIS = {
    "novo": {"confirmado", "cancelado"},
    "confirmado": {"em_preparacao", "cancelado"},
    "em_preparacao": {"pronto_retirada", "enviado", "cancelado"},
    "pronto_retirada": {"concluido", "cancelado"},
    "enviado": {"concluido", "cancelado"},
    "concluido": set(),
    "cancelado": set(),
}

# Fase 3: "pronto_retirada" só existe para pedidos retirados na loja e
# "enviado" só para pedidos com entrega — nunca o inverso (um pedido de
# retirada não pode ser marcado como "enviado" nem um de entrega como
# "pronto para retirada"). Estados sem exigência específica de modalidade
# (novo/confirmado/em_preparacao/concluido/cancelado) não aparecem aqui.
STATUS_EXCLUSIVO_RETIRADA = {"pronto_retirada"}
STATUS_EXCLUSIVO_ENTREGA = {"enviado"}


class StatusComercialIn(BaseModel):
    status_pedido: str = Field(min_length=1, max_length=40)
    observacao: str | None = Field(default=None, max_length=280)


def _texto_seguro(valor, limite: int = 280) -> str:
    texto = str(valor or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite]


def _pedido_detalhado(conn, venda_id: int) -> dict:
    pedido = conn.execute(
        """
        SELECT id, cliente, telefone, email, data_venda, data_iso, subtotal, desconto,
               taxa, frete, total_final, forma_pagamento, payment_type_id,
               payment_method_id, parcelas, status, status_pedido, forma_recebimento,
               endereco_cep, endereco_rua, endereco_numero, endereco_complemento,
               endereco_bairro, endereco_cidade, endereco_uf,
               codigo_rastreio, data_aprovacao, observacao_pedido,
               visualizado_admin_em, visualizado_admin_por
          FROM pedidos
         WHERE id=?
        """,
        (venda_id,),
    ).fetchone()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    itens = conn.execute(
        """
        SELECT id, codigo_p, nome_p, quantidade, valor_unitario, valor_total
          FROM pedidos_itens
         WHERE pedido_id=?
         ORDER BY id ASC
        """,
        (venda_id,),
    ).fetchall()
    historico = conn.execute(
        """
        SELECT id, status, usuario, observacao, data_hora, tipo, origem
          FROM pedido_status_log
         WHERE venda_id=?
         ORDER BY id DESC
        """,
        (venda_id,),
    ).fetchall()
    pagamentos = conn.execute(
        """
        SELECT id, forma, valor, status, observacao, usuario, data_hora
          FROM pagamentos
         WHERE venda_id=?
         ORDER BY id DESC
        """,
        (venda_id,),
    ).fetchall()
    tentativas = conn.execute(
        """
        SELECT id, provedor, status_interno, status_externo, bandeira,
               payment_type_id, parcelas, criado_em, atualizado_em
          FROM tentativas_pagamento
         WHERE pedido_id=?
         ORDER BY id DESC
        """,
        (venda_id,),
    ).fetchall()

    resposta = dict(pedido)
    resposta["itens"] = [dict(item) for item in itens]
    resposta["historico_status"] = [dict(item) for item in historico]
    resposta["historico_pagamentos"] = [dict(item) for item in pagamentos]
    resposta["tentativas_pagamento"] = [dict(item) for item in tentativas]
    return resposta


def registrar_rotas_admin_pedidos() -> None:
    # Importação tardia: main.py já carregou pedido_notificacao_routes antes de
    # system_status_routes. Assim, as rotas abaixo entram no mesmo APIRouter já
    # incluído pela aplicação, sem alterar o bootstrap nem criar rota pública.
    from backend.pedido_notificacao_routes import router

    @router.get("/pedidos/{venda_id}/detalhes-admin")
    def detalhes_admin_pedido(
        venda_id: int,
        sessao: dict = Depends(exigir_sessao_ou_chave_api("vendedor")),
    ):
        with conectar() as conn:
            return _pedido_detalhado(conn, venda_id)

    @router.patch("/pedidos/{venda_id}/status-comercial")
    def alterar_status_comercial(
        venda_id: int,
        payload: StatusComercialIn = Body(...),
        sessao: dict = Depends(exigir_sessao_ou_chave_api("adm")),
    ):
        destino = _texto_seguro(payload.status_pedido, 40).lower()
        if destino not in STATUS_COMERCIAIS:
            raise HTTPException(status_code=400, detail="Situação comercial inválida.")

        usuario = _texto_seguro(sessao.get("nome") or sessao.get("login") or "Admin", 120) or "Admin"
        observacao = _texto_seguro(payload.observacao, 280) or "Atualização realizada no painel unificado de pedidos."
        agora = datetime.now().isoformat(timespec="seconds")

        with conectar() as conn:
            pedido = conn.execute(
                "SELECT id, status, status_pedido, forma_recebimento FROM pedidos WHERE id=?",
                (venda_id,),
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")

            atual = str(pedido["status_pedido"] or "novo").strip().lower()
            if atual == destino:
                return {
                    "ok": True,
                    "venda_id": venda_id,
                    "status_pedido": atual,
                    "ja_registrado": True,
                }

            if destino not in TRANSICOES_COMERCIAIS.get(atual, set()):
                raise HTTPException(
                    status_code=409,
                    detail=f"Não é permitido alterar a situação comercial de '{atual}' para '{destino}'.",
                )

            forma_recebimento = str(pedido["forma_recebimento"] or "").strip().lower()
            if destino in STATUS_EXCLUSIVO_RETIRADA and forma_recebimento != "retirada":
                raise HTTPException(
                    status_code=409,
                    detail="'Pronto para retirada' só se aplica a pedidos com retirada na loja.",
                )
            if destino in STATUS_EXCLUSIVO_ENTREGA and forma_recebimento != "entrega":
                raise HTTPException(
                    status_code=409,
                    detail="'Enviado' só se aplica a pedidos com entrega.",
                )

            # Cancelamento comercial não cancela, estorna ou aprova pagamento.
            # O domínio financeiro permanece intocado nesta rota.
            claim = conn.execute(
                "UPDATE pedidos SET status_pedido=? WHERE id=? AND COALESCE(status_pedido,'novo')=?",
                (destino, venda_id, atual),
            )
            if claim.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail="O pedido foi atualizado por outra operação. Atualize a tela e tente novamente.",
                )

            conn.execute(
                """
                INSERT INTO pedido_status_log
                    (venda_id, status, usuario, observacao, data_hora, tipo, origem)
                VALUES (?,?,?,?,?,'pedido','administrador')
                """,
                (venda_id, destino, usuario, observacao, agora),
            )
            registrar_auditoria(
                conn,
                "pedido",
                venda_id,
                "alterar_status_comercial",
                usuario,
                antes={"status_pedido": atual, "status_financeiro": pedido["status"]},
                depois={"status_pedido": destino, "status_financeiro": pedido["status"]},
            )
            conn.commit()

        return {
            "ok": True,
            "venda_id": venda_id,
            "status_pedido": destino,
            "ja_registrado": False,
        }
