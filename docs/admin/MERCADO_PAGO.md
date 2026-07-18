# Mercado Pago — pagamento com cartão de crédito

Integração do cartão de crédito via Mercado Pago, preservando o Pix manual
já existente (`backend/pix.py`, `docs/admin/PIX_BACKEND.md`). Os dois
provedores coexistem: o cliente escolhe no checkout, o pedido é sempre o
mesmo independente do método escolhido.

## Arquitetura

- `backend/mercadopago_flags.py` — feature flags e credenciais (nunca expõe
  o Access Token fora do backend).
- `backend/mercadopago_client.py` — chamadas HTTP à API REST do Mercado
  Pago (`POST /v1/payments`, `GET /v1/payments/{id}`), via `httpx` (já uma
  dependência pinada do backend — não foi necessário adicionar o SDK
  `mercadopago` em Python).
- `backend/mercadopago_provider.py` — implementação de
  `backend.payment_providers.PaymentProvider` (validação de assinatura
  HMAC do webhook + consulta server-to-server do pagamento).
- `backend/mercadopago_routes.py` — rotas públicas/administrativas:
  - `GET /api/payments/mercadopago/config` — estado seguro para o
    checkout (habilitado + Public Key).
  - `POST /api/payments/mercadopago/card` — cria a cobrança do cartão para
    um pedido já existente.
  - `GET /api/payments/mercadopago/tentativas/{pedido_id}` — painel admin.
  - `POST /api/payments/mercadopago/tentativas/{id}/consultar` — painel
    admin, reconsulta o status no provedor.
- `backend/payment_webhook_routes.py` — despacha `POST
  /api/webhooks/pagamentos/mercadopago` para o provider acima, reaproveitando
  **a mesma** `backend.payment_routes.registrar_pagamento` usada pelo Pix
  (nunca uma cópia paralela da conciliação/baixa de estoque).

A confirmação de pagamento (conciliação de valor, transição de status,
baixa de estoque) é sempre feita por `registrar_pagamento` — o mesmo
caminho usado pelo webhook Pix, pela confirmação manual do painel e agora
pelo cartão. Cartão e Pix nunca duplicam essa lógica.

## Fluxo do cartão

1. O cliente cria o pedido pelo mesmo caminho já usado pelo Pix
   (`POST /api/checkout/pedidos` via `window.misticaCriarPedido`), que já
   devolve `pix_txid` (usado também como identificador seguro de acesso ao
   pedido para o cartão) e `total_final` autoritativo.
2. O frontend tokeniza o cartão com o SDK oficial do Mercado Pago
   (`MercadoPago.js v2`, `cardForm`) — número, validade e CVV nunca chegam
   ao nosso servidor.
3. `POST /api/payments/mercadopago/card` recebe só o token + metadados
   (parcelas, e-mail, CPF), recalcula o valor a partir de
   `pedidos.total_final` (nunca confia em valor vindo do cliente), cria uma
   linha em `tentativas_pagamento` e chama o Mercado Pago com
   `X-Idempotency-Key` própria.
4. Se aprovado: chama `registrar_pagamento` (mesma função do Pix) para
   confirmar o pedido e baixar estoque. Se pendente: pedido vai para
   "Pagamento em análise". Se recusado: pedido continua "Aguardando
   pagamento", permitindo nova tentativa com outro cartão.

## Webhook

`POST /api/webhooks/pagamentos/mercadopago` (cadastrar esta URL completa no
painel do Mercado Pago, ex. `https://api.misticaesotericos.com.br/api/webhooks/pagamentos/mercadopago`):

1. Valida a assinatura `x-signature`/`x-request-id` (HMAC-SHA256 com
   `MERCADO_PAGO_WEBHOOK_SECRET`).
2. Nunca confia no corpo do webhook: consulta o pagamento
   server-to-server (`GET /v1/payments/{id}`) para obter status/valor reais.
3. Idempotência dupla: `webhook_eventos` (evento = pagamento+status, único
   por provedor) e a `Idempotency-Key` determinística passada a
   `registrar_pagamento`.
4. Estados fora de ordem (ex.: notificação de "pending" chegando depois de
   "approved") nunca regridem um pedido já confirmado — a mesma regra que
   já protegia o Pix (`STATUS_PEDIDO_JA_CONFIRMADO`/`_classificar_conciliacao`).

## Feature flag e disponibilidade

Com `MERCADO_PAGO_ENABLED=false` (padrão) ou sem `MERCADO_PAGO_ACCESS_TOKEN`/
`MERCADO_PAGO_PUBLIC_KEY` configurados:

- `GET /api/payments/mercadopago/config` responde `{"enabled": false}`.
- O checkout nunca mostra a opção de cartão (o botão fica `hidden`).
- `POST /api/payments/mercadopago/card` responde 503, nunca 500.
- O webhook responde 501 ("provedor não configurado"), igual a um provedor
  nunca registrado.

## Variáveis de ambiente

Ver `.env.example`:

```
MERCADO_PAGO_ENABLED=false
MERCADO_PAGO_ENVIRONMENT=production
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_WEBHOOK_SECRET=
```

## Banco de dados

Nova tabela `tentativas_pagamento` (uma linha por tentativa de cobrança,
várias por pedido, nunca mais de uma aprovada — garantido pela transição
atômica de `pedidos.status`, não por esta tabela). Índices novos em
`pedidos(pix_txid)` e `pedidos(provider_payment_id)`. Migração 100%
aditiva (`CREATE TABLE IF NOT EXISTS`/`ALTER TABLE` tolerante), sem
alterar dados existentes.

## Painel administrativo

`admin-pedidos-pix.html`/`.js` (não duplicado — estendido): cada pedido
mostra o provedor quando não é o Pix manual, e um botão "Ver tentativas de
pagamento" lista todas as tentativas (Mercado Pago e futuros provedores)
com status, parcelas, motivo de recusa sanitizado e botão para reconsultar
o status diretamente no Mercado Pago.
