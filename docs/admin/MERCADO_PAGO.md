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

## Diagnóstico interno de tentativas (status/status_detail)

Além do painel, cada tentativa de cartão gera um log estruturado
(`mercadopago_cartao_resultado`, `backend/mercadopago_routes.py`) com
`status`/`status_detail` do provedor, `payment_method_id`, `installments`
e um diagnóstico heurístico de ambiente das credenciais — nunca token,
número do cartão, CVV, CPF ou e-mail. Ver
`backend/mercadopago_flags.diagnostico_credenciais_mercadopago()`: os
prefixos `TEST-`/`APP_USR-` são só um INDÍCIO (a documentação oficial
admite variação conforme a solução), nunca uma prova — o diagnóstico
sinaliza `possible_environment_mismatch`/`credential_environment_confidence:
"low"`, nunca afirma certeza nem bloqueia o pagamento. A confirmação real
de que Public Key e Access Token pertencem à mesma aplicação/ambiente só
existe olhando o painel do Mercado Pago
(https://www.mercadopago.com.br/developers/panel).

## Endereço de cobrança (reformulação do checkout)

`POST /api/payments/mercadopago/card` aceita `payer.endereco_cobranca`
opcional (`backend/mercadopago_routes.py::EnderecoCobrancaIn`):
`usar_mesmo_da_entrega` (bool) + `cep/rua/numero/complemento/bairro/cidade/uf`.

- Quando `usar_mesmo_da_entrega=true` e o pedido é de entrega, reaproveita
  `pedidos.endereco_*` (já gravado na criação do pedido, Fase 3 — PR #386) —
  nunca duplicado, nunca reescrito.
- Caso contrário (retirada, ou entrega com o campo desmarcado), usa os
  campos explícitos desta requisição, com a mesma validação de CEP (8
  dígitos)/UF (`backend/frete.py::UF_BRASIL`) já usada no endereço de
  entrega.
- Nunca é persistido em nenhuma tabela — existe só na memória do processo
  pelo tempo da requisição (`_resolver_endereco_cobranca`).
- Enviado ao Mercado Pago em **`payer.address`** (campos `zip_code`/
  `street_name`/`street_number`/`neighborhood`/`city`/`federal_unit`) —
  **nunca** em `additional_info.payer.address`, que nos SDKs oficiais é um
  schema reduzido (só `zip_code`/`street_name`/`street_number`, sem
  `neighborhood`/`city`/`federal_unit`) usado para dado comportamental do
  pagador (par de `first_name`/`last_name`/`registration_date`), não para
  endereço de cobrança completo.
  - **Fonte primária** (revisão de homologação da PR #388 — a
    documentação HTML oficial retornou 403 por bloqueio do proxy desta
    sessão; confirmado por clone direto do GitHub dos dois SDKs oficiais do
    próprio Mercado Pago): `mercadopago/sdk-nodejs`,
    `src/clients/payment/create/types.ts` (`PayerRequest.address:
    AddressRequest`, que estende `Address` com `neighborhood`/`city`/
    `federal_unit`) e `src/clients/payment/commonTypes.ts`
    (`PayerAdditionalInfo.address: Address`, sem esses três campos);
    `mercadopago/sdk-dotnet`,
    `src/MercadoPago/Client/Payment/PaymentPayerRequest.cs` (`Address:
    PaymentPayerAddressRequest`) e
    `PaymentAdditionalInfoPayerRequest.cs` (`Address: AddressRequest`,
    base, sem os três campos extras).
  - Uma versão anterior desta integração (primeiro commit da PR #388)
    enviava para `additional_info.payer.address` — corrigido na revisão de
    homologação após confirmação na fonte primária acima; ver
    `tests/test_mercadopago_cartao.py::
    test_billing_address_no_client_mercadopago_usa_payer_address`.
- Ausente quando o cliente não informa endereço de cobrança —
  comportamento idêntico ao existente antes desta mudança (compatibilidade
  total).

## Mensagens amigáveis por status_detail + cooldown de alto risco

`backend/pedido_comercial.py::mensagem_amigavel_pagamento` mapeia
`status_detail` do Mercado Pago (e a mensagem de validação bruta de uma
rejeição na criação, ex. `"Invalid user identification number"`) para texto
em português nunca técnico — ver a tabela `_MENSAGENS_STATUS_DETAIL` no
próprio módulo. `status_detail` fora do mapa cai numa mensagem genérica de
recusa, nunca um código exposto ao cliente.

Recusas de sinal de risco/antifraude (`cc_rejected_high_risk`,
`cc_rejected_blacklist`, `cc_rejected_max_attempts` —
`STATUS_DETAIL_ALTO_RISCO`) aplicam um cooldown de
`COOLDOWN_ALTO_RISCO_SEGUNDOS` (120s) antes de aceitar uma nova tentativa de
cartão para o mesmo pedido (`backend/mercadopago_routes.py::
_cooldown_alto_risco_restante`, HTTP 429 enquanto ativo) — nunca tenta
contornar o antifraude do provedor; outro cartão ou o Pix continuam
disponíveis a qualquer momento, sem cooldown algum.

## Cartões de teste (sandbox) — cenários oficiais

Fonte: [Cartões de teste](https://www.mercadopago.com.br/developers/pt/docs/checkout-api/integration-test/test-cards)
e [Contas de teste](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/test/accounts)
(Mercado Pago Developers).

Em sandbox, o **nome do titular** informado decide o resultado simulado —
não importa qual cartão de teste é usado com ele:

| Titular | Resultado simulado | `status_detail` típico |
|---|---|---|
| `APRO` | Aprovado | `accredited` |
| `OTHE` | Recusado (erro geral) | `cc_rejected_other_reason` |
| `CONT` | Pendente | — |
| `CALL` | Recusado (precisa autorizar) | `cc_rejected_call_for_authorize` |
| `FUND` | Recusado (saldo insuficiente) | `cc_rejected_insufficient_amount` |
| `SECU` | Recusado (CVV inválido) | `cc_rejected_bad_filled_security_code` |
| `EXPI` | Recusado (validade inválida) | `cc_rejected_bad_filled_date` |
| `FORM` | Recusado (erro de preenchimento) | `cc_rejected_bad_filled_other` |

CPF de teste associado: `12345678909`. Cartão de teste Visa usado na
validação desta revisão: `4235 6477 2802 5682`, CVV `123`, validade
`11/30` — dado público de teste do próprio Mercado Pago, nunca um cartão
real.

**A reprovação registrada na imagem de validação usava o titular `OTHE`
— pelo comportamento documentado acima, isso é uma reprovação ESPERADA do
cenário de teste, não evidência de bug no fluxo de cartão.** Para validar
aprovação em sandbox, o cenário correto é repetir o mesmo cartão com o
titular `APRO`. Ver `tests/test_mercadopago_cartao.py` (`test_cenario_
oficial_APRO_simula_pagamento_aprovado` e `test_cenario_oficial_OTHE_
simula_recusa_esperada_do_cartao_de_teste`) para os testes automatizados
que documentam e travam o comportamento do nosso backend diante de cada
um desses dois cenários.
