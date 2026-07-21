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


# Mensagem amigável por status_detail (nunca o código técnico é mostrado ao
# cliente, nunca culpa o cliente, nunca afirma "cartão sem limite" sem
# confirmação do provedor). Cobre os cenários oficiais de sandbox já
# documentados em docs/admin/MERCADO_PAGO.md (tabela de cartões de teste) mais
# os pedidos explícitos de diagnóstico (CPF inválido, alto risco). Chave é
# comparada em minúsculas contra o status_detail devolvido pelo Mercado Pago
# OU contra a mensagem bruta de validação de uma rejeição na CRIAÇÃO do
# pagamento (4xx, ver mercadopago_client.py::criar_pagamento_cartao) — as
# duas fontes preenchem o mesmo campo ResultadoPagamentoMP.status_detail.
_MENSAGENS_STATUS_DETAIL = {
    "cc_rejected_bad_filled_security_code": "O código de segurança (CVV) informado está incorreto. Confira o código impresso no cartão e tente novamente.",
    "cc_rejected_bad_filled_date": "A validade informada está incorreta. Confira o mês/ano impresso no cartão e tente novamente.",
    "cc_rejected_bad_filled_other": "Alguns dados do cartão não foram reconhecidos. Revise o número, a validade e o código de segurança.",
    "cc_rejected_bad_filled_card_number": "O número do cartão informado é inválido. Confira os dígitos e tente novamente.",
    "cc_rejected_call_for_authorize": "O banco emissor pediu para você autorizar este pagamento diretamente com ele antes de tentar novamente.",
    "cc_rejected_insufficient_amount": "O cartão não tem limite disponível para este valor. Tente outro cartão, outro número de parcelas ou o Pix.",
    "cc_rejected_high_risk": "O pagamento não foi autorizado por critérios de segurança. Aguarde antes de tentar novamente, utilize outro cartão ou escolha Pix.",
    "cc_rejected_blacklist": "O pagamento não foi autorizado por critérios de segurança. Utilize outro cartão ou escolha Pix.",
    "cc_rejected_max_attempts": "Foram feitas várias tentativas com este cartão. Aguarde alguns minutos, tente outro cartão ou escolha Pix.",
    "cc_rejected_duplicated_payment": "Já existe um pagamento recente com estes mesmos dados. Verifique se o pedido já foi pago antes de tentar de novo.",
    "cc_rejected_card_disabled": "Este cartão está desabilitado para compras online. Entre em contato com o banco emissor ou tente outro cartão.",
    "cc_rejected_card_error": "Não foi possível validar este cartão agora. Tente novamente em instantes ou escolha Pix.",
    "cc_rejected_invalid_installments": "O número de parcelas escolhido não é aceito para este cartão. Selecione outra opção de parcelamento.",
    "cc_rejected_other_reason": "Não foi possível aprovar o pagamento com este cartão. Revise os dados, tente outro cartão ou escolha Pix.",
    "invalid user identification number": "Não foi possível validar o CPF informado. Revise o documento e tente novamente.",
    "invalid_identification_number": "Não foi possível validar o CPF informado. Revise o documento e tente novamente.",
}

# status_detail cujo motivo é sinal de risco/antifraude — nunca tentamos
# contornar automaticamente; a única ação segura é um intervalo mínimo antes
# de aceitar uma nova tentativa de cartão para o mesmo pedido (ver
# backend/mercadopago_routes.py::_cooldown_alto_risco_ativo).
STATUS_DETAIL_ALTO_RISCO = {"cc_rejected_high_risk", "cc_rejected_blacklist", "cc_rejected_max_attempts"}


def mensagem_amigavel_pagamento(status: str, status_detail: str | None) -> str:
    """Mensagem neutra para o cliente sobre o resultado de uma tentativa de
    cartão -- nunca expõe status/status_detail bruto do provedor. `status`
    decide o caso geral (aprovado/pendente/recusado/cancelado); quando
    recusado, `status_detail` refina a mensagem para os motivos conhecidos
    (tabela acima); qualquer motivo não mapeado cai na mensagem genérica de
    recusa, nunca um código técnico."""
    if status == "approved":
        return "Pagamento aprovado."
    if status in {"pending", "in_process", "authorized", "in_mediation"}:
        return "Pagamento em análise. Você será avisado assim que for confirmado."
    if status == "cancelled":
        return "Pagamento cancelado."
    if status == "rejected":
        chave = str(status_detail or "").strip().lower()
        return _MENSAGENS_STATUS_DETAIL.get(chave, "Não foi possível aprovar o pagamento com este cartão. Revise os dados, tente outro cartão ou escolha Pix.")
    return "Não foi possível concluir o pagamento agora. Tente novamente ou escolha Pix."
