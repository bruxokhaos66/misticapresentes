from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar
from backend.idempotency import (
    concluir_chave_idempotente,
    liberar_chave_idempotente,
    reivindicar_chave_idempotente,
)
from backend.money import centavos
from backend.order_status_routes import (
    STATUS_PEDIDO_CONCLUIDOS,
    baixar_estoque_do_pedido,
    expirar_pedidos_pendentes,
)
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api", tags=["pagamentos"])

STATUS_PAGAMENTO = {"Aguardando", "Confirmado", "Recusado", "Cancelado", "Estornado"}

# Resultado da conciliação entre o valor recebido e o total autoritativo do
# pedido (pedidos.total_final). Só "ok" pode confirmar o pedido e baixar
# estoque; qualquer divergência fica registrada, mas nunca marca o pedido
# como pago silenciosamente.
CONCILIACAO_OK = "ok"
CONCILIACAO_MENOR = "divergente_menor"
CONCILIACAO_MAIOR = "divergente_maior"
CONCILIACAO_NAO_AVALIADA = "nao_avaliado"
# Pagamento (de qualquer valor) recebido depois que o pedido já saiu dos
# status que aceitam confirmação financeira pela primeira vez — cancelado
# (expiração também vira 'Cancelado' neste sistema, não há status
# 'Expirado' separado) ou já avançado além de 'Pagamento confirmado'
# (Separando pedido, Pronto para retirada, Entregue, Concluído). Nunca
# reabre o pedido, nunca baixa/repõe estoque; fica só registrado para
# conciliação administrativa.
CONCILIACAO_TARDIO = "pagamento_tardio"

# Únicos status de pedido em que uma confirmação financeira "pela primeira
# vez" é aceita. 'Pagamento confirmado' é tratado à parte (ver
# _classificar_conciliacao): reconfirmação/divergência ali já tinham
# comportamento definido e testado antes deste PR e permanecem intactos.
STATUS_PEDIDO_ELEGIVEIS_CONFIRMACAO = {"Aguardando pagamento", "Pagamento divergente"}
STATUS_PEDIDO_JA_CONFIRMADO = "Pagamento confirmado"

limitar_registrar_pagamento = limitar_requisicoes("registrar_pagamento", limite=20, janela_segundos=60)
limitar_webhook_pagamento = limitar_requisicoes("webhook_pagamento", limite=30, janela_segundos=60)
limitar_status_pagamento = limitar_requisicoes("status_pagamento", limite=20, janela_segundos=60)


class PagamentoIn(BaseModel):
    venda_id: int = Field(gt=0)
    forma: str = "Pix"
    # Valor efetivamente recebido. Obrigatório: a ausência do campo já é
    # rejeitada pela validação do Pydantic (422) antes de qualquer alteração
    # no pedido — nunca assumimos o total esperado como valor recebido.
    valor: float = Field(ge=0)
    status: str = "Confirmado"
    comprovante: Optional[str] = None
    observacao: Optional[str] = None
    usuario: str = "Admin"


class PagamentoStatusIn(BaseModel):
    status: str = Field(min_length=1)
    observacao: Optional[str] = None
    usuario: str = "Admin"


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.")


def registrar_log_status(conn, venda_id: int, status: str, usuario: str, observacao: str):
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (venda_id, status, usuario or "Admin", observacao or "", datetime.now().isoformat(timespec="seconds")),
    )


def _conciliar_valor(valor_recebido, total_final) -> tuple[str, Optional[str], float, float]:
    """Compara o valor recebido com o total autoritativo do pedido usando
    centavos em Decimal (nunca `float ==`). Devolve
    (status_conciliacao, motivo_divergencia, valor_recebido_float, valor_esperado_float)."""
    try:
        recebido_dec = centavos(valor_recebido)
    except ValueError:
        raise HTTPException(status_code=400, detail="Valor recebido inválido.")
    # total_final tem default 0.0 no schema; None só ocorreria em dado legado
    # corrompido, tratado aqui como zero em vez de propagar um erro genérico.
    esperado_dec = centavos(total_final if total_final is not None else 0)

    if recebido_dec == esperado_dec:
        return CONCILIACAO_OK, None, float(recebido_dec), float(esperado_dec)
    if recebido_dec < esperado_dec:
        motivo = f"Valor recebido (R$ {recebido_dec}) é menor que o total do pedido (R$ {esperado_dec})."
        return CONCILIACAO_MENOR, motivo, float(recebido_dec), float(esperado_dec)
    motivo = f"Valor recebido (R$ {recebido_dec}) é maior que o total do pedido (R$ {esperado_dec})."
    return CONCILIACAO_MAIOR, motivo, float(recebido_dec), float(esperado_dec)


def _classificar_conciliacao(status_pedido_atual: str, valor_recebido, total_final) -> tuple[str, Optional[str], float, float]:
    """Primeiro decide se o pedido ainda está em um status que aceita
    confirmação financeira; só then compara o valor recebido com o total
    autoritativo. Esta é a revalidação de status "dentro da mesma
    transação" exigida antes de qualquer confirmação — o chamador já deve
    ter rodado expirar_pedidos_pendentes(conn, agora) nesta mesma conexão
    logo antes, para que o status lido aqui reflita o prazo autoritativo mesmo
    que o worker periódico (backend/main.py) ainda não tenha rodado.

    - Aguardando pagamento / Pagamento divergente: aceitam confirmação pela
      primeira vez (comportamento já existente do PR #311).
    - Pagamento confirmado: reconfirmação (exata, idempotente) ou divergência
      sobre um pedido já pago — comportamento já existente do PR #311,
      preservado sem alteração.
    - Qualquer outro status (Cancelado — inclui pedidos expirados, que viram
      Cancelado neste sistema — ou já avançado além da confirmação:
      Separando pedido, Pronto para retirada, Entregue, Concluído): o
      pagamento nunca confirma, nunca reabre, nunca baixa/repõe estoque;
      fica classificado como pagamento tardio para conciliação
      administrativa, com o valor sempre registrado."""
    conciliacao, motivo, recebido_f, esperado_f = _conciliar_valor(valor_recebido, total_final)
    if status_pedido_atual in STATUS_PEDIDO_ELEGIVEIS_CONFIRMACAO or status_pedido_atual == STATUS_PEDIDO_JA_CONFIRMADO:
        return conciliacao, motivo, recebido_f, esperado_f

    detalhe = "o valor bate com o total do pedido" if conciliacao == CONCILIACAO_OK else (motivo or "o valor não bate com o total do pedido")
    motivo_tardio = f"Pagamento tardio: pedido já está '{status_pedido_atual or 'desconhecido'}'. {detalhe}"
    return CONCILIACAO_TARDIO, motivo_tardio, recebido_f, esperado_f


def _aplicar_resultado_confirmacao(conn, venda_id: int, status_pedido_atual: str, conciliacao: str, motivo: Optional[str], usuario: str, agora: str, valor_recebido: float, valor_esperado: float) -> bool:
    """Aplica ao pedido o resultado da conciliação (já classificado por
    _classificar_conciliacao, que filtrou pedidos em status terminal
    incompatível para CONCILIACAO_TARDIO). Só confirma e baixa estoque
    quando a conciliação é exata; divergência nunca altera o pedido para
    pago e nunca baixa estoque. Pagamento tardio nunca toca em
    pedidos.status nem em estoque — fica só no histórico e na auditoria."""
    if conciliacao == CONCILIACAO_OK:
        estoque_baixado_agora = baixar_estoque_do_pedido(conn, venda_id, usuario, agora, "Baixa automática ao confirmar pagamento")
        conn.execute("UPDATE pedidos SET status='Pagamento confirmado' WHERE id=?", (venda_id,))
        registrar_log_status(conn, venda_id, "Pagamento confirmado", usuario, "Pagamento confirmado: valor recebido bate com o total do pedido.")
        return estoque_baixado_agora

    observacao = (motivo or "Divergência de valor no pagamento.") + f" Recebido: R$ {valor_recebido:.2f} | Esperado: R$ {valor_esperado:.2f}."
    if conciliacao == CONCILIACAO_TARDIO:
        registrar_log_status(conn, venda_id, "Pagamento tardio registrado para conciliação", usuario, observacao)
        return False
    if status_pedido_atual not in STATUS_PEDIDO_CONCLUIDOS:
        conn.execute("UPDATE pedidos SET status='Pagamento divergente' WHERE id=?", (venda_id,))
        registrar_log_status(conn, venda_id, "Pagamento divergente", usuario, observacao)
    else:
        registrar_log_status(conn, venda_id, "Divergência de pagamento registrada", usuario, observacao)
    return False


def _payload_idempotencia_pagamento(payload: "PagamentoIn") -> dict:
    return {
        "venda_id": payload.venda_id,
        "forma": payload.forma,
        "valor": str(payload.valor),
        "status": payload.status,
        "comprovante": payload.comprovante,
    }


@router.post("/pagamentos", dependencies=[Depends(limitar_registrar_pagamento)])
def registrar_pagamento(
    payload: PagamentoIn,
    x_mistica_api_key: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    validar_site_api_key(x_mistica_api_key)
    status_informado = payload.status.strip()
    if status_informado not in STATUS_PAGAMENTO:
        raise HTTPException(status_code=400, detail="Status de pagamento inválido")

    # Reivindicação atômica da Idempotency-Key: duas chamadas concorrentes
    # (retry de rede, callback duplicado do PSP, dois workers processando o
    # mesmo evento) nunca processam a confirmação em paralelo — a segunda
    # aguarda a primeira terminar e recebe a MESMA resposta, sem reprocessar
    # nem baixar estoque de novo. Sem chave, o comportamento é o mesmo de
    # antes (sem proteção de idempotência).
    resposta_existente = reivindicar_chave_idempotente(
        conectar, "registrar_pagamento", idempotency_key, _payload_idempotencia_pagamento(payload)
    )
    if resposta_existente is not None:
        return resposta_existente

    agora = datetime.now().isoformat(timespec="seconds")
    try:
        with conectar() as conn:
            # Revalida o prazo de expiração ANTES de ler o status do pedido,
            # na mesma transação da confirmação: se o prazo já passou mas o
            # worker periódico (backend/main.py) ainda não rodou, este
            # pedido é cancelado agora mesmo (reivindicação atômica, já
            # segura sob concorrência — ver expirar_pedidos_pendentes) antes
            # de decidirmos se o pagamento confirma. A confirmação nunca
            # depende exclusivamente da tarefa periódica.
            expirar_pedidos_pendentes(conn, agora)

            venda = conn.execute("SELECT id, total_final, status FROM pedidos WHERE id=?", (payload.venda_id,)).fetchone()
            if not venda:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")

            conciliacao = CONCILIACAO_NAO_AVALIADA
            motivo = None
            valor_recebido_f = float(payload.valor)
            valor_esperado_f: Optional[float] = None
            status_gravado_pagamento = status_informado

            if status_informado == "Confirmado":
                conciliacao, motivo, valor_recebido_f, valor_esperado_f = _classificar_conciliacao(str(venda["status"] or ""), payload.valor, venda["total_final"])
                if conciliacao != CONCILIACAO_OK:
                    # Nunca gravamos "Confirmado" no registro de pagamento quando o
                    # valor diverge: o que de fato aconteceu é que o pedido segue
                    # aguardando conciliação, não pago.
                    status_gravado_pagamento = "Aguardando"

            cur = conn.execute(
                """
                INSERT INTO pagamentos (venda_id, forma, valor, status, comprovante, observacao, usuario, data_hora, valor_esperado, status_conciliacao, motivo_divergencia)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payload.venda_id,
                    payload.forma or "Pix",
                    valor_recebido_f,
                    status_gravado_pagamento,
                    payload.comprovante or "",
                    payload.observacao or "",
                    payload.usuario or "Admin",
                    agora,
                    valor_esperado_f,
                    conciliacao,
                    motivo,
                ),
            )
            pagamento_id = int(cur.lastrowid)

            estoque_baixado_agora = False
            if status_informado == "Confirmado":
                estoque_baixado_agora = _aplicar_resultado_confirmacao(
                    conn, payload.venda_id, str(venda["status"] or ""), conciliacao, motivo,
                    payload.usuario or "Admin", agora, valor_recebido_f, valor_esperado_f or 0.0,
                )

            registrar_auditoria(
                conn,
                "pagamento",
                pagamento_id,
                "registrar",
                payload.usuario,
                depois={
                    "venda_id": payload.venda_id,
                    "forma": payload.forma,
                    "valor": valor_recebido_f,
                    "status_informado": status_informado,
                    "status_conciliacao": conciliacao,
                    "status_pedido_no_momento": str(venda["status"] or ""),
                },
            )

            resposta = {
                "ok": True,
                "id": pagamento_id,
                "venda_id": payload.venda_id,
                "status": status_gravado_pagamento,
                "status_conciliacao": conciliacao,
                "confirmado": conciliacao == CONCILIACAO_OK if status_informado == "Confirmado" else None,
                "estoque_baixado_agora": estoque_baixado_agora,
                "data_hora": agora,
            }
            if motivo:
                resposta["motivo_divergencia"] = motivo

            concluir_chave_idempotente(conn, "registrar_pagamento", idempotency_key, resposta)
            conn.commit()
    except Exception:
        liberar_chave_idempotente(conectar, "registrar_pagamento", idempotency_key)
        raise

    return resposta


class PixWebhookIn(BaseModel):
    txid: Optional[str] = None
    venda_id: Optional[int] = None
    valor: float = Field(ge=0)
    status: str = "Confirmado"
    comprovante: Optional[str] = None


def _validar_segredo_webhook_pix(x_mistica_webhook_secret: str | None):
    segredo = os.environ.get("MISTICA_PIX_WEBHOOK_SECRET", "").strip()
    if not segredo:
        raise HTTPException(status_code=503, detail="Confirmação automática de Pix não está configurada.")
    if not x_mistica_webhook_secret or not secrets.compare_digest(x_mistica_webhook_secret, segredo):
        raise HTTPException(status_code=403, detail="Segredo de webhook inválido.")


@router.post("/pagamentos/webhook", dependencies=[Depends(limitar_webhook_pagamento)])
def confirmar_pagamento_webhook(
    payload: PixWebhookIn,
    x_mistica_webhook_secret: str | None = Header(default=None),
):
    """Ponto de entrada para confirmação automatizada de Pix (ex.: webhook do
    banco/PSP). Protegido por segredo compartilhado próprio (nunca a chave
    geral da API), configurado em MISTICA_PIX_WEBHOOK_SECRET. Localiza o
    pedido pelo txid gerado na criação (ver backend/pix.py) ou pelo venda_id.
    O valor recebido é sempre conciliado contra pedidos.total_final antes de
    confirmar (ver registrar_pagamento) — o payload do webhook nunca decide
    sozinho se o pedido foi pago."""
    _validar_segredo_webhook_pix(x_mistica_webhook_secret)
    status = payload.status.strip()
    if status not in STATUS_PAGAMENTO:
        raise HTTPException(status_code=400, detail="Status de pagamento inválido")

    with conectar() as conn:
        venda = None
        if payload.txid:
            venda = conn.execute("SELECT id, total_final FROM pedidos WHERE pix_txid=?", (payload.txid,)).fetchone()
        if not venda and payload.venda_id:
            venda = conn.execute("SELECT id, total_final FROM pedidos WHERE id=?", (payload.venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado para o txid/venda_id informado.")
        venda_id = int(venda["id"])

    chave_interna = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    # Chave de idempotência determinística por evento: o mesmo txid (ou
    # venda_id, se o PSP não enviar txid) sempre reivindica a MESMA chave, de
    # forma que reenvio de webhook (replay) ou duas notificações concorrentes
    # do mesmo evento nunca processem a confirmação duas vezes.
    resposta = registrar_pagamento(
        PagamentoIn(
            venda_id=venda_id,
            forma="Pix automático",
            valor=payload.valor,
            status=status,
            comprovante=payload.comprovante,
            observacao="Confirmado automaticamente via webhook Pix",
            usuario="Webhook Pix",
        ),
        x_mistica_api_key=chave_interna,
        idempotency_key=f"webhook_pix:{payload.txid or venda_id}",
    )

    if status == "Confirmado" and resposta.get("status_conciliacao") == CONCILIACAO_OK:
        with conectar() as conn:
            conn.execute("UPDATE pedidos SET confirmado_automaticamente=1 WHERE id=?", (venda_id,))
            conn.commit()

    return resposta


@router.get("/pagamentos")
def listar_pagamentos(venda_id: Optional[int] = None, limite: int = Query(100, ge=1, le=500), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    with conectar() as conn:
        if venda_id:
            rows = conn.execute(
                """
                SELECT p.*, v.cliente, v.total_final
                FROM pagamentos p
                LEFT JOIN pedidos v ON v.id = p.venda_id
                WHERE p.venda_id=?
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (venda_id, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT p.*, v.cliente, v.total_final
                FROM pagamentos p
                LEFT JOIN pedidos v ON v.id = p.venda_id
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
    return [dict(row) for row in rows]


@router.put("/pagamentos/{pagamento_id}/status", dependencies=[Depends(limitar_status_pagamento)])
def atualizar_status_pagamento(pagamento_id: int, payload: PagamentoStatusIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = payload.status.strip()
    if status not in STATUS_PAGAMENTO:
        raise HTTPException(status_code=400, detail="Status de pagamento inválido")

    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        pagamento = conn.execute("SELECT id, venda_id, valor FROM pagamentos WHERE id=?", (pagamento_id,)).fetchone()
        if not pagamento:
            raise HTTPException(status_code=404, detail="Pagamento não encontrado")

        conciliacao = CONCILIACAO_NAO_AVALIADA
        motivo = None
        status_gravado = status
        valor_esperado_f: Optional[float] = None
        venda = None

        if status == "Confirmado":
            # Mesma revalidação de prazo que a rota principal (ver
            # registrar_pagamento): a rota manual segue exatamente a mesma
            # regra, nunca depende só da tarefa periódica.
            expirar_pedidos_pendentes(conn, agora)
            venda = conn.execute("SELECT id, total_final, status FROM pedidos WHERE id=?", (pagamento["venda_id"],)).fetchone()
            if not venda:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            # Reconcilia o valor já registrado neste pagamento (nunca aceito de
            # novo do corpo desta requisição, que só troca o status) contra o
            # total autoritativo do pedido, e o status atual do pedido (nunca
            # confirma/reabre um pedido em status terminal incompatível).
            conciliacao, motivo, valor_recebido_f, valor_esperado_f = _classificar_conciliacao(str(venda["status"] or ""), pagamento["valor"], venda["total_final"])
            if conciliacao != CONCILIACAO_OK:
                status_gravado = "Aguardando"

        conn.execute(
            "UPDATE pagamentos SET status=?, observacao=?, status_conciliacao=?, motivo_divergencia=?, valor_esperado=COALESCE(?, valor_esperado) WHERE id=?",
            (status_gravado, payload.observacao or "", conciliacao, motivo, valor_esperado_f, pagamento_id),
        )
        registrar_auditoria(
            conn,
            "pagamento",
            pagamento_id,
            "atualizar_status",
            payload.usuario,
            depois={
                "status_informado": status,
                "status_conciliacao": conciliacao,
                "status_pedido_no_momento": str(venda["status"] or "") if venda else None,
            },
        )

        estoque_baixado_agora = False
        if status == "Confirmado":
            estoque_baixado_agora = _aplicar_resultado_confirmacao(
                conn, pagamento["venda_id"], str(venda["status"] or ""), conciliacao, motivo,
                payload.usuario or "Admin", agora, float(pagamento["valor"] or 0), valor_esperado_f or 0.0,
            )
        conn.commit()
    return {
        "ok": True,
        "id": pagamento_id,
        "status": status_gravado,
        "status_conciliacao": conciliacao,
        "estoque_baixado_agora": estoque_baixado_agora,
    }
