from __future__ import annotations

"""Modelo comercial unificado de pedidos (Pix + cartão).

Este módulo NÃO cria nenhuma tabela nova nem duplica a conciliação
financeira já existente em backend/payment_routes.py — ele só define, num
lugar único, o vocabulário comercial (status de atendimento, rótulo de
forma de pagamento) usado tanto pelos pontos que gravam pedidos.status_pedido
quanto pela futura tela administrativa unificada.

Situação financeira (pedidos.status, ver backend/payment_routes.py) e
situação comercial (pedidos.status_pedido, definida aqui) são
propositalmente independentes: um pedido pode estar com pagamento aprovado e
ainda "em preparação" há dias, e as duas nunca são confundidas.
"""

# Situação comercial (atendimento) do pedido — nunca confundir com a
# situação financeira (pedidos.status / backend/payment_routes.py::
# STATUS_PAGAMENTO). Um pedido novo criado pelo checkout começa em 'novo'
# independente da forma de pagamento; a confirmação financeira (Pix ou
# cartão, manual ou via webhook) sempre o avança para 'confirmado' — nunca
# além disso automaticamente, pois preparo/envio/conclusão são decisões
# operacionais humanas.
STATUS_PEDIDO_COMERCIAL = {
    "novo",
    "confirmado",
    "em_preparacao",
    "pronto_retirada",
    "enviado",
    "concluido",
    "cancelado",
}

# Rótulo amigável para exibição no painel (Parte 6 do pedido de unificação).
ROTULO_STATUS_PEDIDO_COMERCIAL = {
    "novo": "Novo",
    "confirmado": "Confirmado",
    "em_preparacao": "Em preparação",
    "pronto_retirada": "Pronto para retirada",
    "enviado": "Enviado",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}

FORMAS_RECEBIMENTO = {"retirada", "entrega"}

# payment_type_id do Mercado Pago -> rótulo em português. Qualquer
# payment_type_id fora deste mapa (ou ausente) é exibido de forma neutra por
# rotulo_forma_pagamento, nunca adivinhado como "crédito" por padrão.
_ROTULO_TIPO_PAGAMENTO = {
    "credit_card": "Crédito",
    "debit_card": "Débito",
    "ticket": "Boleto",
    "bank_transfer": "Transferência",
    "account_money": "Saldo Mercado Pago",
}

# payment_method_id (bandeira) do Mercado Pago -> nome de exibição. Valores
# fora do mapa usam o próprio payment_method_id capitalizado, nunca são
# ocultados.
_ROTULO_BANDEIRA = {
    "visa": "Visa",
    "master": "Mastercard",
    "elo": "Elo",
    "amex": "Amex",
    "hipercard": "Hipercard",
    "diners": "Diners",
    "pix": "Pix",
}


def rotulo_forma_pagamento(payment_type_id: str | None, payment_method_id: str | None) -> str:
    """Rótulo comercial real (ex.: "Crédito · Visa", "Débito · Mastercard"),
    construído SEMPRE a partir de payment_type_id/payment_method_id
    devolvidos pelo Mercado Pago — nunca inferido pelo número de parcelas.
    Quando o provedor ainda não informou o tipo (ex.: tentativa em
    processamento), devolve um rótulo neutro em vez de assumir crédito."""
    tipo = _ROTULO_TIPO_PAGAMENTO.get(str(payment_type_id or "").strip().lower())
    bandeira_bruta = str(payment_method_id or "").strip().lower()
    bandeira = _ROTULO_BANDEIRA.get(bandeira_bruta) or (bandeira_bruta.title() if bandeira_bruta else None)

    if not tipo:
        return f"Cartão · {bandeira} (Mercado Pago)" if bandeira else "Método ainda não identificado (Mercado Pago)"
    return f"{tipo} · {bandeira}" if bandeira else f"{tipo} (Mercado Pago)"


def rotulo_parcelas(parcelas: int | None) -> str:
    n = int(parcelas or 1)
    return "À vista" if n <= 1 else f"{n}x"


def sanitizar_status_detail(status_detail: str | None, limite: int = 200) -> str | None:
    """status_detail do Mercado Pago é um código genérico do provedor (ex.:
    "cc_rejected_bad_filled_security_code"), nunca dado de cartão/pessoal —
    ainda assim, nunca gravamos sem truncar/limpar caracteres de controle,
    por princípio de defesa em profundidade em qualquer campo vindo de
    fora."""
    texto = str(status_detail or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite] or None
