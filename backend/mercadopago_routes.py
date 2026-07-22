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
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.frete import UF_BRASIL, normalizar_uf
from backend.idempotency import (
    concluir_chave_idempotente,
    liberar_chave_idempotente,
    reivindicar_chave_idempotente,
)
from backend.logging_config import get_logger
from backend.mercadopago_client import MercadoPagoIndisponivel, criar_pagamento_cartao, consultar_pagamento
from backend.mercadopago_flags import (
    ambiente_mercadopago,
    diagnostico_credenciais_mercadopago,
    mercado_pago_habilitado,
    public_key_mercadopago,
)
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
from backend.pedido_comercial import (
    MENSAGEM_CARD_TOKEN_INVALIDO,
    STATUS_DETAIL_ALTO_RISCO,
    eh_card_token_invalido,
    mensagem_amigavel_pagamento,
    rotulo_forma_pagamento,
    rotulo_parcelas,
    sanitizar_status_detail,
)
from backend.rate_limit import limitar_requisicoes
from backend.whatsapp_events import EVENTO_PAGAMENTO_PENDENTE, ContextoEventoPedido, entrega_legivel
from backend.whatsapp_outbox import enfileirar_evento_whatsapp

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


class EnderecoCobrancaIn(BaseModel):
    """Endereço de cobrança do cartão -- enviado em payer.address (ver
    backend/mercadopago_client.py::criar_pagamento_cartao para a fonte
    oficial que confirma esse campo, não additional_info.payer.address);
    nunca é persistido (ver _resolver_endereco_cobranca), nunca bloqueia a
    cobrança se ausente (compatibilidade com integrações/testes que não
    enviam este campo)."""

    usar_mesmo_da_entrega: bool = True
    cep: Optional[str] = Field(default=None, max_length=12)
    rua: Optional[str] = Field(default=None, max_length=200)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=120)
    bairro: Optional[str] = Field(default=None, max_length=120)
    cidade: Optional[str] = Field(default=None, max_length=120)
    uf: Optional[str] = Field(default=None, max_length=8)

    @field_validator("uf")
    @classmethod
    def _validar_uf(cls, valor):
        if valor is None or not str(valor).strip():
            return None
        uf = normalizar_uf(valor)
        if uf not in UF_BRASIL:
            raise ValueError("UF inválida.")
        return uf

    @field_validator("cep")
    @classmethod
    def _validar_cep(cls, valor):
        if valor is None or not str(valor).strip():
            return None
        digitos = "".join(ch for ch in str(valor) if ch.isdigit())
        if len(digitos) != 8:
            raise ValueError("CEP inválido: informe 8 dígitos.")
        return digitos


def _nome_comprador_valido(texto: str) -> bool:
    """Aceita apenas letras (com acentos, qualquer script Unicode), espaço,
    apóstrofo e hífen -- cobre nomes compostos, partículas ("de", "da") e
    nomes de uma única palavra, sem admitir dígitos, HTML ou caracteres de
    controle. Nunca usado para inferir/derivar nome a partir de outro
    campo -- só valida o que o comprador digitou explicitamente."""
    return bool(texto) and all(ch.isalpha() or ch in " '-" for ch in texto)


def _normalizar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()


class PayerIn(BaseModel):
    email: EmailStr
    # Nome/sobrenome do COMPRADOR (payer.first_name/last_name da Payments
    # API) -- coletados por campos explícitos do checkout, nunca derivados de
    # "Nome impresso no cartão" (cardholderName, titular do cartão, pode ser
    # uma pessoa diferente) nem divididos automaticamente de um nome
    # completo. `nome` é obrigatório (é o dado mínimo real do comprador);
    # `sobrenome` é opcional -- nomes civis legítimos de uma única palavra
    # nunca são bloqueados nem preenchidos com valor inventado.
    nome: str = Field(min_length=1, max_length=60)
    sobrenome: Optional[str] = Field(default=None, max_length=60)
    documento_tipo: Optional[str] = Field(default="CPF", max_length=10)
    documento_numero: Optional[str] = Field(default=None, max_length=20)
    endereco_cobranca: Optional[EnderecoCobrancaIn] = None

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, valor):
        limpo = _normalizar_espacos(valor)
        if not limpo or not _nome_comprador_valido(limpo):
            raise ValueError("Nome inválido: use apenas letras, espaços, hífen ou apóstrofo.")
        return limpo[:60]

    @field_validator("sobrenome")
    @classmethod
    def _validar_sobrenome(cls, valor):
        if valor is None:
            return None
        limpo = _normalizar_espacos(valor)
        if not limpo:
            return None
        if not _nome_comprador_valido(limpo):
            raise ValueError("Sobrenome inválido: use apenas letras, espaços, hífen ou apóstrofo.")
        return limpo[:60]


_DEVICE_ID_PADRAO = re.compile(r"^[A-Za-z0-9._-]{8,160}$")


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
    # Device ID coletado pelo script oficial do Mercado Pago no navegador
    # (https://www.mercadopago.com/v2/security.js), encaminhado ao provedor
    # no header X-meli-session-id (ver criar_pagamento_cartao) -- NUNCA
    # persistido, NUNCA logado, NUNCA usado como Idempotency-Key. Opcional:
    # a ausência (script bloqueado/timeout no navegador) nunca impede o
    # pagamento, só reduz um sinal adicional de antifraude do provedor.
    # max_length generoso (nunca o formato final aceito) -- rejeitar a
    # requisição inteira por um Device ID grande demais bloquearia o
    # pagamento; o validator abaixo descarta silenciosamente qualquer valor
    # fora do formato esperado (incluindo tamanho) sem levantar erro.
    device_id: Optional[str] = Field(default=None, max_length=1000)
    payer: PayerIn

    @field_validator("device_id")
    @classmethod
    def _validar_device_id(cls, valor):
        if valor is None:
            return None
        valor = valor.strip()
        if not valor:
            return None
        # Formato conservador (alfanumérico + . _ -, sem espaços/CRLF que
        # poderiam corromper o header HTTP encaminhado ao provedor) -- valor
        # fora desse formato (incluindo tamanho fora de 8-160) é descartado
        # silenciosamente, nunca rejeita a tentativa de pagamento por causa
        # disso.
        if not _DEVICE_ID_PADRAO.match(valor):
            return None
        return valor


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


# Intervalo mínimo antes de aceitar uma nova tentativa de cartão para o
# mesmo pedido depois de uma recusa de alto risco (ver
# backend/pedido_comercial.py::STATUS_DETAIL_ALTO_RISCO) -- nunca tentamos
# contornar o antifraude do provedor; só evitamos martelar novas tentativas
# em sequência contra o mesmo sinal de risco. Não é um bloqueio permanente:
# outro cartão ou o Pix continuam disponíveis a qualquer momento.
COOLDOWN_ALTO_RISCO_SEGUNDOS = 120


def _cooldown_alto_risco_restante(conn, pedido_id: int, agora: str) -> int:
    """Segundos restantes de cooldown, ou 0 se nenhuma recusa de alto risco
    recente existir para este pedido. Consulta só a última tentativa
    (nenhuma tabela nova, nenhum dado persistido além do que
    tentativas_pagamento já grava)."""
    ultima = conn.execute(
        """
        SELECT status_interno, motivo_recusa, atualizado_em FROM tentativas_pagamento
         WHERE pedido_id=? AND provedor='mercadopago' ORDER BY id DESC LIMIT 1
        """,
        (pedido_id,),
    ).fetchone()
    if not ultima or ultima["status_interno"] != "recusado":
        return 0
    motivo = str(ultima["motivo_recusa"] or "").strip().lower()
    if motivo not in STATUS_DETAIL_ALTO_RISCO:
        return 0
    try:
        decorrido = (datetime.fromisoformat(agora) - datetime.fromisoformat(ultima["atualizado_em"])).total_seconds()
    except ValueError:
        return 0
    restante = COOLDOWN_ALTO_RISCO_SEGUNDOS - int(decorrido)
    return max(0, restante)


def _itens_additional_info(conn, pedido_id: int) -> Optional[list]:
    """Monta additional_info.items a partir de pedidos_itens (produto,
    quantidade e valor unitário JÁ calculados pelo backend na criação do
    pedido -- nunca confia em preço/quantidade vindos do cliente). Só os
    campos documentados pelo schema oficial (id/title/quantity/unit_price;
    ver commonTypes.ts do mercadopago/sdk-nodejs) -- sem category_id/
    description/picture_url/warranty inventados, porque este catálogo não
    tem esses dados estruturados hoje. Retorna None se o pedido não tiver
    itens ou se algum item não tiver quantidade/preço válidos (nunca envia
    um item com dado incoerente)."""
    linhas = conn.execute(
        "SELECT codigo_p, nome_p, quantidade, valor_unitario FROM pedidos_itens WHERE pedido_id=? ORDER BY id",
        (pedido_id,),
    ).fetchall()
    if not linhas:
        return None
    itens = []
    for linha in linhas:
        codigo = str(linha["codigo_p"] or "").strip()
        titulo = str(linha["nome_p"] or "").strip()
        quantidade = int(linha["quantidade"] or 0)
        valor_unitario = float(linha["valor_unitario"] or 0)
        if not codigo or not titulo or quantidade <= 0 or valor_unitario <= 0:
            return None
        itens.append(
            {
                "id": codigo[:60],
                "title": titulo[:256],
                "quantity": quantidade,
                "unit_price": round(valor_unitario, 2),
            }
        )
    return itens or None


def _resolver_endereco_cobranca(pedido, endereco: Optional[EnderecoCobrancaIn]) -> Optional[dict]:
    """Monta o dict devolvido a criar_pagamento_cartao(billing_address=...),
    que o coloca em payer.address -- ÚNICOS campos documentados pelos SDKs
    oficiais do Mercado Pago para o endereço completo do pagador
    (zip_code/street_name/street_number/neighborhood/city/federal_unit; ver
    a fonte primária citada em backend/mercadopago_client.py::
    criar_pagamento_cartao), nunca inventa propriedade nova. 'Usar o mesmo
    endereço da entrega' só é aceito quando o pedido é de fato de entrega e
    já tem endereço gravado (pedidos.endereco_*, Fase 3 -- PR #386); do
    contrário, exige os campos explícitos desta requisição. Nunca persiste o
    endereço de cobrança em nenhuma tabela -- ele só existe na memória do
    processo pelo tempo desta requisição."""
    if endereco is None:
        return None
    forma_recebimento = str(pedido["forma_recebimento"] or "")
    if endereco.usar_mesmo_da_entrega and forma_recebimento == "entrega":
        cep, rua, numero = pedido["endereco_cep"], pedido["endereco_rua"], pedido["endereco_numero"]
        bairro, cidade, uf = pedido["endereco_bairro"], pedido["endereco_cidade"], pedido["endereco_uf"]
    else:
        cep, rua, numero = endereco.cep, endereco.rua, endereco.numero
        bairro, cidade, uf = endereco.bairro, endereco.cidade, endereco.uf
    if not (cep and rua and numero and cidade and uf):
        return None
    return {
        "zip_code": cep,
        "street_name": rua,
        "street_number": numero,
        "neighborhood": bairro or "",
        "city": cidade,
        "federal_unit": uf,
    }


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
                """
                SELECT id, total_final, status, pix_txid, forma_recebimento,
                       endereco_cep, endereco_rua, endereco_numero, endereco_bairro,
                       endereco_cidade, endereco_uf
                  FROM pedidos WHERE id=?
                """,
                (payload.pedido_id,),
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

            cooldown_restante = _cooldown_alto_risco_restante(conn, payload.pedido_id, agora)
            if cooldown_restante > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"Por segurança, aguarde {cooldown_restante}s antes de tentar novamente com cartão, tente outro cartão ou escolha Pix.",
                )

            endereco_cobranca = _resolver_endereco_cobranca(pedido, payload.payer.endereco_cobranca)
            itens_additional_info = _itens_additional_info(conn, payload.pedido_id)
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
            billing_address=endereco_cobranca,
            additional_info_items=itens_additional_info,
            device_id=payload.device_id,
            payer_first_name=payload.payer.nome,
            payer_last_name=payload.payer.sobrenome,
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

    logger.info(
        "mercadopago_cartao_resultado",
        extra={
            "evento": "mp_cartao_resultado",
            "pedido_id": payload.pedido_id,
            "tentativa_id": tentativa_id,
            "status_interno": status_interno_tentativa,
            "status_provedor": resultado.status,
            "status_detail_provedor": resultado.status_detail[:200] if resultado.status_detail else None,
            "payment_method_id": resultado.payment_method_id,
            "installments": payload.installments,
            "ambiente": ambiente_mercadopago(),
            **diagnostico_credenciais_mercadopago(),
        },
    )

    with conectar() as conn:
        conn.execute(
            """
            UPDATE tentativas_pagamento
               SET provider_payment_id=?, status_interno=?, status_externo=?, bandeira=?, payment_type_id=?,
                   motivo_recusa=?, atualizado_em=?
             WHERE id=?
            """,
            (
                resultado.id or None,
                status_interno_tentativa,
                resultado.status,
                resultado.payment_method_id,
                resultado.payment_type_id,
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
        with conectar() as conn:
            for status_de_origem in ("Aguardando pagamento", "Pagamento divergente"):
                if tentar_transicao_status_pagamento(conn, payload.pedido_id, status_de_origem, "Pagamento em análise"):
                    try:
                        pedido_row = conn.execute("SELECT forma_recebimento FROM pedidos WHERE id=?", (payload.pedido_id,)).fetchone()
                        enfileirar_evento_whatsapp(
                            conn, evento=EVENTO_PAGAMENTO_PENDENTE, pedido_id=payload.pedido_id,
                            sufixo_idempotencia="em_analise",
                            contexto=ContextoEventoPedido(
                                pedido_id=payload.pedido_id, valor=resultado.transaction_amount or total_final,
                                entrega=entrega_legivel(pedido_row["forma_recebimento"] if pedido_row else None),
                            ),
                        )
                    except Exception:
                        pass
                    conn.commit()
                    break
                conn.rollback()

    forma_rotulo = rotulo_forma_pagamento(resultado.payment_type_id, resultado.payment_method_id)
    parcelas_rotulo = rotulo_parcelas(payload.installments)
    forma_pagamento_texto = f"{forma_rotulo}, {parcelas_rotulo}"
    status_detail_sanitizado = sanitizar_status_detail(resultado.status_detail)

    resposta_pagamento = None
    if resultado.id:
        resposta_pagamento = registrar_pagamento(
            PagamentoIn(
                venda_id=payload.pedido_id,
                forma=forma_pagamento_texto,
                valor=resultado.transaction_amount or total_final,
                status=status_interno_pagamento,
                observacao=f"{forma_rotulo} via Mercado Pago, {parcelas_rotulo} (status do provedor: {resultado.status})",
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
                    """
                    UPDATE pedidos
                       SET payment_provider='mercadopago', provider_payment_id=?, forma_pagamento=?,
                           payment_type_id=?, payment_method_id=?, parcelas=?, status_detail_sanitizado=?,
                           email=COALESCE(email, ?), data_aprovacao=COALESCE(data_aprovacao, ?)
                     WHERE id=?
                    """,
                    (
                        resultado.id, forma_pagamento_texto,
                        resultado.payment_type_id, resultado.payment_method_id, payload.installments,
                        status_detail_sanitizado, payload.payer.email, agora2, payload.pedido_id,
                    ),
                )
            conn.commit()

    # card_token_id inválido/já usado/expirado (código 3003, ver
    # backend/pedido_comercial.py::eh_card_token_invalido) nunca é uma
    # recusa de crédito -- é um erro de integração (o CardToken do SDK é
    # descartável, de uso único) que o cliente resolve gerando um token novo
    # no navegador. Sinalizado com HTTP 422 + "codigo" interno sanitizado
    # (nunca o código/mensagem bruta do provedor) para o frontend nunca
    # tratar isso como uma recusa comum de cartão.
    token_invalido = eh_card_token_invalido(resultado.status, resultado.status_detail, resultado.causa_codigos)
    mensagem = MENSAGEM_CARD_TOKEN_INVALIDO if token_invalido else mensagem_amigavel_pagamento(status_provedor_efetivo, resultado.status_detail)

    resposta = {
        "ok": not token_invalido,
        "pedido_id": payload.pedido_id,
        "tentativa_id": tentativa_id,
        "status": status_interno_tentativa,
        "aprovado": status_interno_tentativa == "aprovado",
        "mensagem": mensagem,
        "codigo": "cartao_token_invalido" if token_invalido else None,
        "parcelas": payload.installments,
        "valor": total_final,
    }
    with conectar() as conn:
        concluir_chave_idempotente(conn, "pagamento_cartao_mp", idempotency_key, resposta)
        conn.commit()
    if token_invalido:
        return JSONResponse(status_code=422, content=resposta)
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

    forma_rotulo = rotulo_forma_pagamento(resultado.payment_type_id, resultado.payment_method_id)
    parcelas_reconsulta = max(1, int(resultado.installments or tentativa["parcelas"] or 1))
    forma_pagamento_texto = f"{forma_rotulo}, {rotulo_parcelas(parcelas_reconsulta)}"

    with conectar() as conn:
        conn.execute(
            "UPDATE tentativas_pagamento SET status_externo=?, status_interno=?, payment_type_id=COALESCE(?, payment_type_id), bandeira=COALESCE(?, bandeira), parcelas=?, atualizado_em=? WHERE id=?",
            (resultado.status, status_interno_tentativa, resultado.payment_type_id, resultado.payment_method_id, parcelas_reconsulta, agora, tentativa_id),
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
            forma=forma_pagamento_texto,
            valor=resultado.transaction_amount,
            status=status_interno_pagamento,
            observacao="Reconsulta administrativa do status no Mercado Pago",
            usuario=sessao.get("usuario") or sessao.get("login") or "Admin",
            identificador_evento=resultado.id,
        ),
        x_mistica_api_key=_chave_interna(),
        idempotency_key=f"webhook_mercadopago:{resultado.id}:{resultado.status}",
    )
    if status_interno_pagamento == "Confirmado" and isinstance(resposta_pagamento, dict) and resposta_pagamento.get("status_conciliacao") == "ok":
        with conectar() as conn:
            conn.execute(
                """
                UPDATE pedidos
                   SET payment_provider='mercadopago', provider_payment_id=?, forma_pagamento=?,
                       payment_type_id=?, payment_method_id=?, parcelas=?, data_aprovacao=COALESCE(data_aprovacao, ?)
                 WHERE id=?
                """,
                (resultado.id, forma_pagamento_texto, resultado.payment_type_id, resultado.payment_method_id, parcelas_reconsulta, agora, int(tentativa["pedido_id"])),
            )
            conn.commit()
    return {"ok": True, "status_provedor": resultado.status, "resultado": resposta_pagamento}
