from __future__ import annotations

from datetime import datetime

from fastapi import Body, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api

FORMAS_RECEBIMENTO = {"retirada", "entrega"}


class LogisticaPedidoIn(BaseModel):
    forma_recebimento: str = Field(min_length=1, max_length=20)
    codigo_rastreio: str | None = Field(default=None, max_length=120)
    observacao: str | None = Field(default=None, max_length=280)


def _texto_seguro(valor, limite: int) -> str | None:
    texto = str(valor or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite] or None


def registrar_rotas_admin_logistica() -> None:
    """Registra o primeiro incremento logístico usando somente schema existente.

    A Fase 3 começa de forma aditiva e conservadora: forma de recebimento e
    rastreio já existem em pedidos. Transportadora, prazo, endereço estruturado
    e histórico dedicado serão adicionados em incremento posterior com migração
    centralizada e testes próprios, nunca por DDL durante import ou requisição.
    """
    from backend.pedido_notificacao_routes import router

    @router.get("/pedidos/{venda_id}/logistica")
    def consultar_logistica(
        venda_id: int,
        sessao: dict = Depends(exigir_sessao_ou_chave_api("vendedor")),
    ):
        del sessao
        with conectar() as conn:
            pedido = conn.execute(
                """
                SELECT id, status, status_pedido, forma_recebimento,
                       codigo_rastreio, observacao_pedido
                  FROM pedidos
                 WHERE id=?
                """,
                (venda_id,),
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            return dict(pedido)

    @router.patch("/pedidos/{venda_id}/logistica")
    def atualizar_logistica(
        venda_id: int,
        payload: LogisticaPedidoIn = Body(...),
        sessao: dict = Depends(exigir_sessao_ou_chave_api("adm")),
    ):
        forma = (_texto_seguro(payload.forma_recebimento, 20) or "").lower()
        if forma not in FORMAS_RECEBIMENTO:
            raise HTTPException(status_code=400, detail="Forma de recebimento inválida.")

        rastreio = _texto_seguro(payload.codigo_rastreio, 120)
        observacao = _texto_seguro(payload.observacao, 280)
        if forma == "retirada" and rastreio:
            raise HTTPException(
                status_code=400,
                detail="Código de rastreio não se aplica a pedidos para retirada.",
            )

        usuario = _texto_seguro(sessao.get("nome") or sessao.get("login") or "Admin", 120) or "Admin"
        agora = datetime.now().isoformat(timespec="seconds")

        with conectar() as conn:
            pedido = conn.execute(
                """
                SELECT id, status, status_pedido, forma_recebimento,
                       codigo_rastreio, observacao_pedido
                  FROM pedidos
                 WHERE id=?
                """,
                (venda_id,),
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            if str(pedido["status_pedido"] or "").lower() == "cancelado":
                raise HTTPException(status_code=409, detail="Pedido cancelado não pode ter a logística alterada.")

            antes = dict(pedido)
            claim = conn.execute(
                """
                UPDATE pedidos
                   SET forma_recebimento=?, codigo_rastreio=?, observacao_pedido=?
                 WHERE id=?
                   AND COALESCE(forma_recebimento,'')=COALESCE(?, '')
                   AND COALESCE(codigo_rastreio,'')=COALESCE(?, '')
                """,
                (
                    forma,
                    rastreio,
                    observacao if observacao is not None else pedido["observacao_pedido"],
                    venda_id,
                    pedido["forma_recebimento"],
                    pedido["codigo_rastreio"],
                ),
            )
            if claim.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail="O pedido foi atualizado por outra operação. Atualize a tela e tente novamente.",
                )

            registrar_auditoria(
                conn,
                "pedido",
                venda_id,
                "atualizar_logistica",
                usuario,
                antes=antes,
                depois={
                    "status_financeiro": pedido["status"],
                    "status_pedido": pedido["status_pedido"],
                    "forma_recebimento": forma,
                    "codigo_rastreio": rastreio,
                    "observacao_pedido": observacao if observacao is not None else pedido["observacao_pedido"],
                    "atualizado_em": agora,
                },
            )
            conn.commit()

        return {
            "ok": True,
            "venda_id": venda_id,
            "forma_recebimento": forma,
            "codigo_rastreio": rastreio,
            "logistica_atualizada_em": agora,
        }
