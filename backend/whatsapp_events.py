"""Catálogo de eventos administrativos que geram notificação por WhatsApp,
mapeamento evento -> template e montagem das variáveis/payload sanitizado.

Nenhuma função aqui decide SE um evento deve ser emitido (isso é decidido
pelo chamador, no ponto exato da mudança de estado já confirmada no banco --
ver backend/payment_routes.py, backend/site_stock_routes.py etc.); este
módulo só sabe como transformar um contexto de pedido já sanitizado em
variáveis de template e num payload seguro para auditoria/painel.

Regra de privacidade (ver docs/admin/WHATSAPP_NOTIFICACOES.md): a mensagem
NUNCA inclui CPF, e-mail, telefone, endereço, nome completo do comprador,
status_detail bruto do provedor, payload de webhook, token ou segredo --
apenas número do pedido, valor, forma de pagamento (rótulo comercial já
sanitizado) e modalidade de entrega."""
from __future__ import annotations

from dataclasses import dataclass

from backend.whatsapp_flags import whatsapp_template_language, whatsapp_template_nome
from backend.whatsapp_provider import ComponenteTemplate

# Eventos administrativos suportados (Parte 6 do escopo). A ordem aqui
# reflete a ordem de prioridade/gravidade operacional.
EVENTO_PEDIDO_CRIADO = "PEDIDO_CRIADO"
EVENTO_PIX_GERADO = "PIX_GERADO"
EVENTO_PAGAMENTO_APROVADO = "PAGAMENTO_APROVADO"
EVENTO_PAGAMENTO_PENDENTE = "PAGAMENTO_PENDENTE"
EVENTO_PAGAMENTO_RECUSADO = "PAGAMENTO_RECUSADO"
EVENTO_PAGAMENTO_EXPIRADO = "PAGAMENTO_EXPIRADO"
EVENTO_PAGAMENTO_CANCELADO = "PAGAMENTO_CANCELADO"
EVENTO_PAGAMENTO_REEMBOLSADO = "PAGAMENTO_REEMBOLSADO"
EVENTO_CHARGEBACK_RECEBIDO = "CHARGEBACK_RECEBIDO"
EVENTO_FALHA_DE_RECONCILIACAO = "FALHA_DE_RECONCILIACAO"

EVENTOS_VALIDOS = {
    EVENTO_PEDIDO_CRIADO,
    EVENTO_PIX_GERADO,
    EVENTO_PAGAMENTO_APROVADO,
    EVENTO_PAGAMENTO_PENDENTE,
    EVENTO_PAGAMENTO_RECUSADO,
    EVENTO_PAGAMENTO_EXPIRADO,
    EVENTO_PAGAMENTO_CANCELADO,
    EVENTO_PAGAMENTO_REEMBOLSADO,
    EVENTO_CHARGEBACK_RECEBIDO,
    EVENTO_FALHA_DE_RECONCILIACAO,
}

# Rótulo comercial exibido no painel/relatório (nunca enviado como texto
# livre ao WhatsApp -- lá o texto vem 100% do template já aprovado pela
# Meta; isso é usado só para o histórico administrativo interno).
DESCRICAO_EVENTO = {
    EVENTO_PEDIDO_CRIADO: "Novo pedido recebido — aguardando pagamento",
    EVENTO_PIX_GERADO: "Pix gerado — aguardando pagamento",
    EVENTO_PAGAMENTO_APROVADO: "Pagamento aprovado",
    EVENTO_PAGAMENTO_PENDENTE: "Pagamento em análise",
    EVENTO_PAGAMENTO_RECUSADO: "Pagamento recusado",
    EVENTO_PAGAMENTO_EXPIRADO: "Pagamento expirado",
    EVENTO_PAGAMENTO_CANCELADO: "Pagamento cancelado",
    EVENTO_PAGAMENTO_REEMBOLSADO: "Pagamento reembolsado",
    EVENTO_CHARGEBACK_RECEBIDO: "Contestação de pagamento (chargeback)",
    EVENTO_FALHA_DE_RECONCILIACAO: "Falha na atualização de pagamento",
}

# Quais campos do contexto entram como variáveis do corpo do template, na
# ordem exata em que devem estar cadastradas no template aprovado (ver
# docs/admin/WHATSAPP_NOTIFICACOES.md para o texto sugerido de cada um).
_CAMPOS_POR_EVENTO: dict[str, tuple[str, ...]] = {
    EVENTO_PEDIDO_CRIADO: ("pedido_numero", "valor", "forma_pagamento", "entrega"),
    EVENTO_PIX_GERADO: ("pedido_numero", "valor"),
    EVENTO_PAGAMENTO_APROVADO: ("pedido_numero", "valor", "forma_pagamento", "entrega"),
    EVENTO_PAGAMENTO_PENDENTE: ("pedido_numero", "valor"),
    EVENTO_PAGAMENTO_RECUSADO: ("pedido_numero", "valor"),
    EVENTO_PAGAMENTO_EXPIRADO: ("pedido_numero", "valor"),
    EVENTO_PAGAMENTO_CANCELADO: ("pedido_numero", "valor"),
    EVENTO_PAGAMENTO_REEMBOLSADO: ("pedido_numero", "valor"),
    EVENTO_CHARGEBACK_RECEBIDO: ("pedido_numero", "valor"),
    EVENTO_FALHA_DE_RECONCILIACAO: ("pedido_numero",),
}


def _sanitizar_campo_texto(valor, limite: int = 60) -> str:
    texto = str(valor if valor is not None else "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite]


def _formatar_valor_brl(valor) -> str:
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "0,00"


@dataclass(frozen=True)
class ContextoEventoPedido:
    pedido_id: int
    valor: float = 0.0
    forma_pagamento: str = ""
    entrega: str = ""


def _campos_formatados(contexto: ContextoEventoPedido) -> dict[str, str]:
    return {
        "pedido_numero": str(int(contexto.pedido_id)),
        "valor": _formatar_valor_brl(contexto.valor),
        "forma_pagamento": _sanitizar_campo_texto(contexto.forma_pagamento, 40) or "Não identificado",
        "entrega": _sanitizar_campo_texto(contexto.entrega, 20) or "Não informado",
    }


def validar_evento(evento: str) -> str:
    evento_normalizado = str(evento or "").strip().upper()
    if evento_normalizado not in EVENTOS_VALIDOS:
        raise ValueError(f"Evento administrativo desconhecido: {evento!r}")
    return evento_normalizado


def montar_componentes_template(evento: str, contexto: ContextoEventoPedido) -> list[ComponenteTemplate]:
    evento = validar_evento(evento)
    campos = _campos_formatados(contexto)
    return [ComponenteTemplate(texto=campos[nome]) for nome in _CAMPOS_POR_EVENTO[evento]]


def montar_payload_sanitizado(evento: str, contexto: ContextoEventoPedido) -> dict:
    """Payload mínimo persistido em notification_outbox.payload_json --
    usado só para reprocessamento e exibição no histórico administrativo.
    Contém exatamente os mesmos campos enviados como variáveis de template,
    nunca PII do comprador."""
    evento = validar_evento(evento)
    campos = _campos_formatados(contexto)
    return {"event": evento, **{nome: campos[nome] for nome in _CAMPOS_POR_EVENTO[evento]}}


def template_para_evento(evento: str) -> tuple[str, str]:
    """Devolve (nome_do_template, idioma) configurados para o evento."""
    evento = validar_evento(evento)
    return whatsapp_template_nome(evento), whatsapp_template_language()


def entrega_legivel(forma_recebimento: str | None) -> str:
    valor = str(forma_recebimento or "").strip().lower()
    if valor == "entrega":
        return "Entrega"
    if valor == "retirada":
        return "Retirada"
    return "Não informado"
