"""Rotas públicas e administrativas do pagamento por cartão de crédito via
Mercado Pago. O Pix (backend/pix.py, backend/payment_routes.py) não é
alterado por este módulo -- os dois provedores coexistem, escolhidos pelo
cliente no checkout.

Nenhum dado de cartão (número, CVV) passa por este servidor: o frontend usa
o SDK oficial do Mercado Pago para gerar um token no navegador; só o token
chega aqui. O valor cobrado é sempre pedidos.total_final (recalculado pelo
servidor na criação do pedido) -- o corpo desta requisição nunca informa um
valor a cobrar.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.idempotency import (
    concluir_chave_idempotente,
    liberar_chave_idempotente,
    reivindicar_chave_idempotente,
)
from backend.logging_config import get_logger
from backend.mercadopago_client import MercadoPagoIndisponivel, criar_pagamento_cartao, consultar_pagamento
from backend.mercadopago_flags import mercado_pago_habilitado, public_key_mercadopago
from backend.order_status_routes import expirar_pedidos_pendentes
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.payment_routes import (
    STATUS_PEDIDO_ELEGIVEIS_CONFIRMACAO,
    STATUS_PEDIDO_JA_CONFIRMADO,
    PagamentoIn,
    registrar_pagamento,
    tentar_transicao_status_pagamento,
)
from backend.payment_webhook_routes import STATUS_PROVEDOR_EM_ANALISE, STATUS_PROVEDOR_PARA_INTERNO
from backend.rate_limit import limitar_requisicoes

logger = get_logger(__name__)

router = APIRouter(prefix="/api/payments/mercadopago", tags=["pagamentos-mercadopago"])

limitar_config_mp = limitar_requisicoes("mercadopago_config", limite=60, janela_segundos=60)
limitar_pagamento_cartao = limitar_requisicoes("mercadopago_cartao", limite=10, janela_segundos=60)
limitar_consulta_tentativas = limitar_requisicoes("mercadopago_tentativas", limite=30, janela_segundos=60)


@router.get("/config", dependencies=[Depends(limitar_config_mp)])
def obter_config_publica():
    """Estado seguro para o checkout decidir se deve mostrar a opção de
    cartão. Nunca expõe o Access Token nem qualquer variável de ambiente
    bruta -- só a Public Key (segura para o navegador) quando habilitado."""
    if not mercado_pago_habilitado():
        return {"enabled": False}
    return {"enabled": True, "public_key": public_key_mercadopago()}


def _chave_interna() -> str:
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Pagamento indisponível no momento.")
    return chave


class PayerIn(BaseModel):
    email: EmailStr
    documento_tipo: Optional[str] = Field(default="CPF", max_length=10)
    documento_numero: Optional[str] = Field(default=None, max_length=20)


class CartaoPagamentoIn(BaseModel):
    pedido_id: int = Field(gt=0)
    # Identificador seguro do próprio pedido (mesmo pix_txid devolvido na
    # criação) -- confirma que quem está pagando tem acesso legítimo a este
    # pedido específico, sem depender de sessão (checkout de convidado).
    txid: str = Field(min_length=1)
    token: str = Field(min_length=10, max_length=200)
    payment_method_id: str = Field(min_length=1, max_length=40)
    installments: int = Field(default=1, ge=1, le=24)
    issuer_id: Optional[str] = Field(default=None, max_length=40)
    payer: PayerIn


def _sanitizar_doc(numero: Optional[str]) -> Optional[str]:
    if not numero:
        return None
    limpo = "".join(ch for ch in numero if ch.isdigit())
    return limpo[:20] or None


def _payload_idempotencia_cartao(payload: CartaoPagamentoIn) -> dict:
    # O token nunca entra em texto puro no payload de idempotência (só um
    # hash) -- calcular_payload_hash serializa e faz SHA256 do dict inteiro,
    # então mesmo o hash do token aqui já fica encadeado dentro de outro
    # hash; ainda assim, evitamos guardar o valor bruto por princípio.
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    return {
        "pedido_id": payload.pedido_id,
        "payment_method_id": payload.payment_method_id,
        "installments": payload.installments,
        "issuer_id": payload.issuer_id,
        "payer_email": payload.payer.email,
        "token_hash": token_hash,
    }


def _mensagem_amigavel(status: str, status_detail: str) -> str:
    """Mensagem neutra para o cliente -- nunca expõe status_detail bruto do
    Mercado Pago (código interno do provedor)."""
    if status == "approved":
        return "Pagamento aprovado."
    if status in STATUS_PROVEDOR_EM_ANALISE:
        return "Pagamento em análise. Você será avisado assim que for confirmado."
    if status == "rejected":
        return "Não foi possível aprovar o pagamento com este cartão. Revise os dados, tente outro cartão ou escolha Pix."
    if status == "cancelled":
        return "Pagamento cancelado."
    return "Não foi possível concluir o pagamento agora. Tente novamente ou escolha Pix."


@router.post("/card", dependencies=[Depends(limitar_pagamento_cartao)])
def pagar_com_cartao(payload: CartaoPagamentoIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not mercado_pago_habilitado():
        raise HTTPException(status_code=503, detail="Pagamento com cartão indisponível no momento. Utilize o Pix.")
    if not idempotency_key or len(idempotency_key.strip()) < 8:
        raise HTTPException(status_code=400, detail="Cabeçalho Idempotency-Key obrigatório.")

    resposta_existente = reivindicar_chave_idempotente(
        conectar, "pagamento_cartao_mp", idempotency_key, _payload_idempotencia_cartao(payload)
    )
    if resposta_existente is not None:
        return resposta_existente

    agora = datetime.now().isoformat(timespec="seconds")
    try:
        with conectar() as conn:
            expirar_pedidos_pendentes(conn, agora)
            pedido = conn.execute(
                "SELECT id, total_final, status, pix_txid FROM pedidos WHERE id=?", (payload.pedido_id,)
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado.")
            txid_pedido = str(pedido["pix_txid"] or "")
            if not txid_pedido or not secrets.compare_digest(payload.txid, txid_pedido):
                raise HTTPException(status_code=403, detail="Acesso ao pedido não autorizado.")

            status_pedido = str(pedido["status"] or "")
            if status_pedido in STATUS_PEDIDO_JA_CONFIRMADO:
                raise HTTPException(status_code=409, detail="Este pedido já foi pago.")
            if status_pedido not in STATUS_PEDIDO_ELEGIVEIS_CONFIRMACAO:
                raise HTTPException(status_code=409, detail="Este pedido não está mais disponível para pagamento (cancelado ou expirado).")

            total_final = float(pedido["total_final"] or 0)
            if total_final <= 0:
                raise HTTPException(status_code=409, detail="Pedido sem valor válido para cobrança.")

            doc_numero = _sanitizar_doc(payload.payer.documento_numero)
            cur = conn.execute(
                """
                INSERT INTO tentativas_pagamento
                    (pedido_id, provedor, metodo, idempotency_key, status_interno, valor, parcelas, criado_em, atualizado_em)
                VALUES (?, 'mercadopago', 'cartao_credito', ?, 'processando', ?, ?, ?, ?)
                """,
                (payload.pedido_id, idempotency_key, total_final, payload.installments, agora, agora),
            )
            tentativa_id = int(cur.lastrowid)
            conn.commit()
    except HTTPException:
        liberar_chave_idempotente(conectar, "pagamento_cartao_mp", idempotency_key)
        raise
    except Exception:
        liberar_chave_idempotente(conectar, "pagamento_cartao_mp", idempotency_key)
        raise

    try:
        resultado = criar_pagamento_cartao(
            idempotency_key=idempotency_key,
            transaction_amount=total_final,
            token=payload.token,
            installments=payload.installments,
            payment_method_id=payload.payment_method_id,
            issuer_id=payload.issuer_id,
            payer_email=payload.payer.email,
            payer_doc_type=payload.payer.documento_tipo,
            payer_doc_number=doc_numero,
            external_reference=str(payload.pedido_id),
            description=f"Pedido #{payload.pedido_id} - Mística Presentes",
        )
    except MercadoPagoIndisponivel:
        agora_erro = datetime.now().isoformat(timespec="seconds")
        with conectar() as conn:
            conn.execute(
                "UPDATE tentativas_pagamento SET status_interno='erro', atualizado_em=? WHERE id=?",
                (agora_erro, tentativa_id),
            )
            conn.commit()
        liberar_chave_idempotente(conectar, "pagamento_cartao_mp", idempotency_key)
        raise HTTPException(status_code=503, detail="Não foi possível processar o pagamento agora. Tente novamente em instantes ou utilize o Pix.")

    # A partir daqui a Idempotency-Key NUNCA é liberada em caso de erro: o
    # Mercado Pago já pode ter processado a cobrança (resultado.id
    # preenchido). Liberar a chave permitiria uma nova tentativa criar uma
    # SEGUNDA cobrança para o mesmo clique/retry -- prioridade nº 1 desta
    # integração é nunca cobrar em duplicidade. Uma falha de gravação local
    # depois deste ponto fica visível para o admin via GET
    # /tentativas/{pedido_id} e é resolvida com o botão de reconsulta
    # (POST /tentativas/{id}/consultar), nunca com uma nova cobrança.
    status_provedor_efetivo = resultado.status
    if resultado.currency_id and resultado.currency_id.upper() != "BRL":
        # Defesa em profundidade: a loja só opera em reais. Mesmo que o
        # Mercado Pago tenha respondido "approved" numa moeda inesperada
        # (conta mal configurada), nunca conciliamos como se fosse BRL --
        # fica registrado como divergência, nunca confirma o pedido sozinho.
        logger.warning(
            "mercadopago_cartao_moeda_inesperada",
            extra={"evento": "mp_cartao_moeda_invalida", "moeda": resultado.currency_id, "pedido_id": payload.pedido_id},
        )
        status_provedor_efetivo = "rejected"
    status_interno_pagamento = STATUS_PROVEDOR_PARA_INTERNO.get(status_provedor_efetivo, "Recusado")
    status_interno_tentativa = {
        "Confirmado": "aprovado",
        "Aguardando": "pendente",
        "Recusado": "recusado",
        "Cancelado": "cancelado",
        "Estornado": "estornado",
    }.get(status_interno_pagamento, "recusado")
    agora2 = datetime.now().isoformat(timespec="seconds")

    with conectar() as conn:
        conn.execute(
            """
            UPDATE tentativas_pagamento
               SET provider_payment_id=?, status_interno=?, status_externo=?, bandeira=?,
                   motivo_recusa=?, atualizado_em=?
             WHERE id=?
            """,
            (
                resultado.id or None,
                status_interno_tentativa,
                resultado.status,
                resultado.payment_method_id,
                (resultado.status_detail[:200] if status_interno_pagamento == "Recusado" else None),
                agora2,
                tentativa_id,
            ),
        )
        registrar_auditoria(
            conn,
            "tentativa_pagamento",
            tentativa_id,
            "processar_cartao_mercadopago",
            "Cliente (Mercado Pago)",
            depois={"pedido_id": payload.pedido_id, "status_mp": resultado.status, "parcelas": payload.installments},
        )
        conn.commit()

    if resultado.status in STATUS_PROVEDOR_EM_ANALISE:
        # Pagamento ainda em análise no provedor: o pedido fica visível como
        # "em processamento" para o cliente, sem pedir que pague de novo
        # imediatamente. Mesma transição atômica usada pelo webhook (ver
        # backend/payment_webhook_routes.py) -- reaproveitada, não duplicada.
        with conectar() as conn:
            for status_de_origem in ("Aguardando pagamento", "Pagamento divergente"):
                if tentar_transicao_status_pagamento(conn, payload.pedido_id, status_de_origem, "Pagamento em análise"):
                    conn.commit()
                    break
                conn.rollback()

    resposta_pagamento = None
    if resultado.id:
        # Idempotency-Key determinística por (pagamento MP, status): se o
        # webhook para o MESMO evento chegar segundos depois (ordem não
        # garantida), converge para a mesma chave e é deduplicado, nunca
        # reprocessado nem duplicado.
        resposta_pagamento = registrar_pagamento(
            PagamentoIn(
                venda_id=payload.pedido_id,
                forma="Cartão de crédito (Mercado Pago)",
                valor=resultado.transaction_amount or total_final,
                status=status_interno_pagamento,
                observacao=f"Cartão de crédito via Mercado Pago, {payload.installments}x (status do provedor: {resultado.status})",
                usuario="Cliente (Mercado Pago)",
                identificador_evento=resultado.id,
            ),
            x_mistica_api_key=_chave_interna(),
            idempotency_key=f"webhook_mercadopago:{resultado.id}:{resultado.status}",
        )
        with conectar() as conn:
            conn.execute(
                "UPDATE tentativas_pagamento SET pagamento_id=?, atualizado_em=? WHERE id=?",
                (resposta_pagamento.get("id") if isinstance(resposta_pagamento, dict) else None, agora2, tentativa_id),
            )
            if status_interno_pagamento == "Confirmado" and isinstance(resposta_pagamento, dict) and resposta_pagamento.get("status_conciliacao") == "ok":
                conn.execute(
                    "UPDATE pedidos SET payment_provider='mercadopago', provider_payment_id=?, forma_pagamento=? WHERE id=?",
                    (resultado.id, f"Cartão de crédito {payload.installments}x (Mercado Pago)", payload.pedido_id),
                )
            conn.commit()

    resposta = {
        "ok": True,
        "pedido_id": payload.pedido_id,
        "tentativa_id": tentativa_id,
        "status": status_interno_tentativa,
        "aprovado": status_interno_tentativa == "aprovado",
        "mensagem": _mensagem_amigavel(status_provedor_efetivo, resultado.status_detail),
        "parcelas": payload.installments,
        "valor": total_final,
    }
    with conectar() as conn:
        concluir_chave_idempotente(conn, "pagamento_cartao_mp", idempotency_key, resposta)
        conn.commit()
    return resposta


@router.get("/tentativas/{pedido_id}", dependencies=[Depends(limitar_consulta_tentativas)])
def listar_tentativas_pedido(pedido_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    """Painel administrativo: histórico de tentativas de pagamento de um
    pedido (Mercado Pago e qualquer outro provedor futuro)."""
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM tentativas_pagamento WHERE pedido_id=? ORDER BY id DESC", (pedido_id,)
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/tentativas/{tentativa_id}/consultar", dependencies=[Depends(limitar_consulta_tentativas)])
def reconsultar_tentativa(tentativa_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Botão administrativo "consultar novamente no provedor": nunca marca o
    pedido como pago diretamente -- só atualiza o status_externo exibido no
    painel e, se o Mercado Pago já mostra aprovado, reaplica a MESMA
    confirmação usada pelo webhook/checkout (registrar_pagamento), com
    idempotência determinística, então uma reconsulta nunca duplica nada."""
    with conectar() as conn:
        tentativa = conn.execute("SELECT * FROM tentativas_pagamento WHERE id=?", (tentativa_id,)).fetchone()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if not tentativa["provider_payment_id"]:
        raise HTTPException(status_code=409, detail="Esta tentativa ainda não tem identificador do provedor.")

    try:
        resultado = consultar_pagamento(tentativa["provider_payment_id"])
    except MercadoPagoIndisponivel:
        raise HTTPException(status_code=503, detail="Mercado Pago indisponível no momento.")

    status_interno_pagamento = STATUS_PROVEDOR_PARA_INTERNO.get(resultado.status, "Aguardando")
    agora = datetime.now().isoformat(timespec="seconds")
    status_interno_tentativa = {
        "Confirmado": "aprovado",
        "Aguardando": "pendente",
        "Recusado": "recusado",
        "Cancelado": "cancelado",
        "Estornado": "estornado",
    }.get(status_interno_pagamento, "pendente")

    with conectar() as conn:
        conn.execute(
            "UPDATE tentativas_pagamento SET status_externo=?, status_interno=?, atualizado_em=? WHERE id=?",
            (resultado.status, status_interno_tentativa, agora, tentativa_id),
        )
        registrar_auditoria(
            conn,
            "tentativa_pagamento",
            tentativa_id,
            "reconsultar_provedor",
            sessao.get("usuario") or sessao.get("login") or "Admin",
            depois={"status_mp": resultado.status},
        )
        conn.commit()

    resposta_pagamento = registrar_pagamento(
        PagamentoIn(
            venda_id=int(tentativa["pedido_id"]),
            forma="Cartão de crédito (Mercado Pago)",
            valor=resultado.transaction_amount,
            status=status_interno_pagamento,
            observacao="Reconsulta administrativa do status no Mercado Pago",
            usuario=sessao.get("usuario") or sessao.get("login") or "Admin",
            identificador_evento=resultado.id,
        ),
        x_mistica_api_key=_chave_interna(),
        idempotency_key=f"webhook_mercadopago:{resultado.id}:{resultado.status}",
    )
    return {"ok": True, "status_provedor": resultado.status, "resultado": resposta_pagamento}
