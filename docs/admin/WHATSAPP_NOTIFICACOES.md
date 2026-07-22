# Notificações administrativas por WhatsApp

Sistema de alertas internos por WhatsApp para a administração da Mística:
sempre que um pedido é criado, um Pix é gerado, ou o pagamento de um pedido
muda de estado (aprovado, recusado, em análise, expirado, cancelado,
reembolsado, chargeback), a administração recebe uma mensagem no WhatsApp.

**Escopo:** só notificações **internas para os administradores**. Nenhuma
mensagem é enviada ao cliente/comprador — isso está fora do escopo desta
implementação (ver seção "Fora do escopo").

**Estado atual:** desligado por padrão em qualquer ambiente (inclusive
produção), via `WHATSAPP_NOTIFICATIONS_ENABLED=false`. Ativar exige concluir
o checklist completo deste documento.

---

## 1. Arquitetura

```
Pedido/pagamento criado ou alterado
        │  (dentro da MESMA transação de banco)
        ▼
notification_outbox (SQLite) — padrão Outbox transacional
        │  (worker separado, depois do commit)
        ▼
backend/whatsapp_worker.py
        │
        ▼
WhatsAppProvider (backend/whatsapp_provider.py)
        │
        ▼
WhatsApp Business Platform / Cloud API (Meta) — POST .../messages
```

Princípios:

- A lógica financeira (`backend/payment_routes.py::registrar_pagamento`,
  `backend/site_stock_routes.py`, `backend/preorder_checkout.py`,
  `backend/payment_webhook_routes.py`, `backend/mercadopago_routes.py`,
  `backend/order_status_routes.py::expirar_pedidos_pendentes`) **nunca**
  chama a rede do WhatsApp diretamente. Cada ponto de mudança de estado só
  grava uma linha em `notification_outbox`, **na mesma transação** da
  mudança de estado (`backend/whatsapp_outbox.py::enfileirar_evento_whatsapp`).
- Se o WhatsApp estiver fora do ar, mal configurado ou desligado: o pedido
  continua funcionando, o pagamento continua sendo registrado, o webhook do
  Mercado Pago continua respondendo normalmente. A notificação fica
  pendente (ou marcada `skipped_disabled`) para nova tentativa/ativação
  futura — nunca bloqueia nem falha o fluxo comercial.
- Um worker separado (`backend/whatsapp_worker.py`) processa a fila depois
  do commit, de forma assíncrona.

### Sem Redis/Celery/RQ nesta infraestrutura

Auditoria: o backend roda como um único serviço web no Render, sobre
SQLite, sem fila externa (Redis, Celery, RQ) e sem worker separado — a
única tarefa assíncrona hoje é uma `asyncio.create_task` em processo
(`backend/main.py::_expirar_pedidos_periodicamente`), rodando a cada 60s
sobre o próprio SQLite.

**Duas opções arquiteturais foram consideradas para o processamento do
outbox:**

1. **Tarefa periódica em processo** (adotada nesta PR) — mesmo padrão já em
   produção para expiração de pedidos: `backend/whatsapp_worker.py` expõe
   `iniciar_tarefa_periodica_worker()`, criada no `lifespan` de
   `backend/main.py` **somente se `whatsapp_habilitado()`** for verdadeiro.
   Roda a cada 30s, processa um lote limitado (CAS por linha via coluna
   `status`), nunca bloqueia requisições HTTP.
   - Vantagem: zero infraestrutura nova, consistente com o padrão já
     validado em produção, outbox persistido no SQLite (nunca só em
     memória) garante que nada se perde num restart.
   - Limitação conhecida: compartilha o processo web — um pico de latência
     no envio ao WhatsApp (respeitando timeout configurado) não bloqueia
     requisições porque roda em uma task assíncrona separada, mas ainda
     compete pelo mesmo event loop.
2. **Processo/worker dedicado** — `backend/whatsapp_worker.py` também é
   executável como processo separado: `python -m backend.whatsapp_worker
   --loop`. Pode virar um segundo serviço no Render (Background Worker) ou
   um Cron Job, sem nenhuma mudança de código, apontando para o mesmo banco
   (disco persistente compartilhado).

**Recomendação:** manter a opção 1 (tarefa periódica em processo) enquanto o
volume de notificações for baixo — é a opção mais simples e já validada
neste código-base. Migrar para a opção 2 (processo dedicado) se o volume
crescer a ponto de a Fase de produção mostrar contenção real; a troca é
apenas operacional (variável de ambiente + serviço novo no Render), o
código do worker já suporta os dois modos sem alteração.

### Classificação de segurança para a infraestrutura atual

`render.yaml` sobe um único serviço web (`startCommand: uvicorn
backend.main:app ...`, sem `--workers`) no plano `starter`, sem
configuração de autoscaling — hoje **uma única instância de processo**.
Nessa condição, **segura**: `_worker_periodico` só é criado quando
`whatsapp_habilitado()` é verdadeiro, encerra corretamente no shutdown
(cancelado e aguardado junto das demais tarefas do `lifespan`, mesmo padrão
de `tarefa_expiracao`), nunca mantém uma transação de banco aberta durante
o `sleep` (cada ciclo abre e fecha sua própria conexão dentro de
`processar_lote_outbox`) e roda em lote limitado (20 por ciclo, a cada 30s).

Duas ressalvas relevantes encontradas na homologação desta PR (ambas
corrigidas nesta mesma branch, ver changelog no topo do arquivo/PR):

1. **Bloqueio do event loop**: `processar_lote_outbox()` é síncrona e faz
   chamadas HTTP bloqueantes (`httpx.Client`, não `AsyncClient`) — chamada
   direta dentro da corrotina periódica bloquearia o único event loop do
   processo pela duração do lote inteiro sempre que a Meta estiver lenta,
   travando **toda e qualquer outra requisição em andamento no mesmo
   processo, inclusive o webhook do Mercado Pago**. Corrigido com
   `asyncio.to_thread` (mesmo padrão já usado em `backend/main.py` para
   `shutdown_remote_uploads`).
2. **Corrida em ações administrativas**: `reprocessar`/`cancelar` liam o
   status e faziam um `UPDATE` condicional sem checar `rowcount` — uma
   corrida perdida contra o worker (ou outra ação administrativa
   concorrente) fazia a rota responder sucesso mesmo sem ter mudado nada.
   Corrigido checando `rowcount` e respondendo 409 nesse caso.

**Múltiplas instâncias (não é o caso hoje, mas avaliado):** o CAS por linha
(`UPDATE ... WHERE id=? AND status=?`) é seguro sob SQLite mesmo com dois
processos escrevendo no mesmo arquivo (SQLite serializa escritores) — duas
instâncias nunca processariam a MESMA linha ao mesmo tempo. Só que, na
prática, múltiplas instâncias **não são suportadas por esta arquitetura
como um todo**, independentemente desta feature: o banco é SQLite num
único Persistent Disk do Render, que só pode estar montado em uma instância
por vez — o restante do backend (não só as notificações WhatsApp) já
pressupõe uma única instância. Migrar para múltiplas instâncias exigiria
antes uma migração de banco (ex.: Postgres) que está totalmente fora do
escopo desta PR. Classificação: **segura para a infraestrutura atual (uma
única instância); a arquitetura de banco já impede múltiplas instâncias
hoje, então esse risco não é específico desta feature.**

---

## 2. Eventos administrativos

| Evento | Quando dispara | Ponto no código |
|---|---|---|
| `PEDIDO_CRIADO` | Checkout público cria um pedido válido (site ou sob encomenda), aguardando pagamento | `backend/site_stock_routes.py`, `backend/preorder_checkout.py` |
| `PIX_GERADO` | Pix (manual, copia-e-cola) gerado com sucesso para o pedido | idem acima |
| `PAGAMENTO_APROVADO` | Conciliação de valor **exata** confirma o pagamento (Pix manual, webhook Pix, cartão Mercado Pago, webhook Mercado Pago — todos passam pelo mesmo ponto) | `backend/payment_routes.py::_aplicar_resultado_confirmacao` |
| `PAGAMENTO_PENDENTE` | Pagamento entra em análise no provedor (`pending`/`in_process`/`authorized`/`in_mediation`) | `backend/payment_webhook_routes.py`, `backend/mercadopago_routes.py` |
| `PAGAMENTO_RECUSADO` | Pagamento recusado | `backend/payment_routes.py::registrar_pagamento` / `atualizar_status_pagamento` |
| `PAGAMENTO_EXPIRADO` | Pedido expira automaticamente sem confirmação (prazo `expira_em` vencido) | `backend/order_status_routes.py::expirar_pedidos_pendentes` |
| `PAGAMENTO_CANCELADO` | Pagamento marcado cancelado | `backend/payment_routes.py` |
| `PAGAMENTO_REEMBOLSADO` | Estorno sem indicação de contestação | `backend/payment_routes.py` |
| `CHARGEBACK_RECEBIDO` | Estorno originado de `charged_back` no provedor (contestação) | `backend/payment_webhook_routes.py` → `PagamentoIn.origem_estorno="chargeback"` |
| `FALHA_DE_RECONCILIACAO` | Falha real/persistente ao aplicar um evento de webhook já validado (não um erro de negócio normal, que nunca gera este evento) | `backend/payment_webhook_routes.py` |

Cada evento tem um texto **claramente distinto** — "Novo pedido" nunca dá a
entender que o pagamento já foi aprovado; a distinção entre
`PAGAMENTO_APROVADO` (pago) e `PEDIDO_CRIADO`/`PIX_GERADO`/`PAGAMENTO_PENDENTE`
(ainda não pago) é sempre explícita no template. A administração **não deve
preparar/entregar o pedido apenas com base em `PEDIDO_CRIADO`**.

`FALHA_DE_NOTIFICACAO` (item 11 do escopo original) não é enviado **pelo
próprio WhatsApp** quando o WhatsApp falha — ele fica visível no painel
administrativo (`notification_outbox.status='permanently_failed'`, GET
`/api/admin/whatsapp-notificacoes`) e nos logs estruturados sanitizados.

---

## 3. Provider e API oficial

Único provider real: **WhatsApp Business Platform / Cloud API** (Meta),
implementado em `backend/whatsapp_provider.py::MetaWhatsAppCloudProvider`.

- Endpoint: `POST https://graph.facebook.com/{versao}/{phone_number_id}/messages`
- Autenticação: `Authorization: Bearer <WHATSAPP_ACCESS_TOKEN>` (System User
  Token de longa duração — nunca o token de usuário de teste de 24h em
  produção)
- Formato de envio: **mensagem de template** (`type: template`) — a única
  forma suportada oficialmente para notificações fora da janela de
  atendimento de 24h (o caso normal aqui: um evento de pagamento pode
  ocorrer a qualquer momento, sem conversa ativa do cliente).
- Callback de status: `POST /api/webhooks/whatsapp` — assinado com
  `X-Hub-Signature-256` (HMAC-SHA256 do corpo bruto com `WHATSAPP_APP_SECRET`).
- Verificação do webhook: `GET /api/webhooks/whatsapp` (`hub.mode`,
  `hub.verify_token`, `hub.challenge`), conforme `WHATSAPP_VERIFY_TOKEN`.

**IMPORTANTE — confirme antes de ativar em produção:**
`WHATSAPP_GRAPH_API_VERSION` tem um padrão de conveniência em
`backend/whatsapp_flags.py::GRAPH_API_VERSION_PADRAO`, mas a Meta
descontinua versões antigas periodicamente. Confira a versão atualmente
recomendada em
[developers.facebook.com/docs/graph-api/changelog](https://developers.facebook.com/docs/graph-api/changelog)
e configure `WHATSAPP_GRAPH_API_VERSION` explicitamente antes de ativar.
Revise também, na documentação oficial vigente
([developers.facebook.com/docs/whatsapp/cloud-api](https://developers.facebook.com/docs/whatsapp/cloud-api)):
formato de envio de template, regras da janela de atendimento de 24h,
formato dos callbacks de status, limites de mensagens/dia e códigos de erro
— o código foi implementado seguindo o comportamento documentado no momento
desta mudança, mas a Meta pode alterar detalhes.

Há também `DisabledWhatsAppProvider` (provider nulo, usado sempre que
`WHATSAPP_NOTIFICATIONS_ENABLED=false` ou a configuração está incompleta) —
permite desenvolvimento/testes sem nenhuma chamada externa.

**Nunca implementado, propositalmente:** automação de WhatsApp Web,
Selenium, navegador controlado, link `wa.me`, ou qualquer API não-oficial.

---

## 4. Variáveis de ambiente

Ver `.env.example` (seção "Notificações administrativas por WhatsApp") para
a lista completa comentada. Resumo:

| Variável | Obrigatória para ativar | Descrição |
|---|---|---|
| `WHATSAPP_NOTIFICATIONS_ENABLED` | — | `true`/`false`, desligado por padrão |
| `WHATSAPP_PROVIDER` | — | `meta_cloud` (padrão) ou `disabled` |
| `WHATSAPP_GRAPH_API_VERSION` | recomendado | confirme na doc oficial antes de ativar |
| `WHATSAPP_PHONE_NUMBER_ID` | sim | painel da Meta |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | não (informativo) | painel da Meta |
| `WHATSAPP_ACCESS_TOKEN` | sim | System User Token |
| `WHATSAPP_APP_SECRET` | sim | valida callbacks de status |
| `WHATSAPP_VERIFY_TOKEN` | sim | handshake do webhook |
| `WHATSAPP_ADMIN_RECIPIENTS` | sim | números administrativos, separados por vírgula |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | não | padrão `55`, só completa números de 10-11 dígitos |
| `WHATSAPP_REQUEST_TIMEOUT_SECONDS` | não | padrão `10` |
| `WHATSAPP_MAX_RETRIES` | não | padrão `5` |
| `WHATSAPP_RETRY_BASE_SECONDS` | não | padrão `60` |
| `WHATSAPP_TEMPLATE_LANGUAGE` | não | padrão `pt_BR` |
| `WHATSAPP_TEMPLATE_ADMIN_*` (10 variáveis) | sim | nome exato de cada template aprovado |
| `WHATSAPP_ADMIN_PAINEL_URL` | não | reservado, só HTTPS |

A ativação efetiva (`whatsapp_habilitado()`) exige a flag ligada, o provider
`meta_cloud` **e** toda a validação de `validar_configuracao_whatsapp()`
passando (todas as credenciais, ao menos 1 destinatário válido, os 10
templates configurados). Config incompleta nunca derruba a API — só
mantém o recurso efetivamente desligado, de forma auditável (ver
`GET /api/admin/whatsapp-notificacoes/status`).

**Nunca logado/exposto:** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`,
`WHATSAPP_VERIFY_TOKEN`, número de telefone completo, payload bruto do
provedor.

---

## 5. Configuração no painel da Meta (Fase 1 — não executada nesta PR)

1. Criar/usar um app em [developers.facebook.com](https://developers.facebook.com/),
   produto **WhatsApp**.
2. Configurar o WhatsApp Business Account e vincular/registrar o número de
   telefone comercial (verificação por SMS/chamada).
3. Anotar `Phone Number ID` e `WhatsApp Business Account ID` (Configuração
   da API).
4. Gerar um **System User Token** de longa duração com a permissão
   `whatsapp_business_messaging` (Business Settings > System Users) — não
   usar o token de teste de 24h em produção.
5. Cadastrar os **10 templates** (Gerenciador do WhatsApp > Modelos de
   mensagem), categoria **Utilidade** (nunca marketing — nenhuma promoção
   misturada com aviso transacional), idioma `pt_BR`. Texto sugerido de
   cada um (variáveis na ordem `{{1}}`, `{{2}}`, ...):

   - `admin_novo_pedido`: "🛒 Novo pedido recebido\n\nPedido: #{{1}}\nValor: R$ {{2}}\nPagamento: {{3}}\nEntrega: {{4}}\nStatus: aguardando pagamento"
   - `admin_pix_gerado`: "📲 Pix gerado\n\nPedido: #{{1}}\nValor: R$ {{2}}\nStatus: aguardando pagamento"
   - `admin_pagamento_aprovado`: "✅ Pagamento aprovado\n\nPedido: #{{1}}\nValor: R$ {{2}}\nPagamento: {{3}}\nEntrega: {{4}}\nStatus: pago"
   - `admin_pagamento_pendente`: "⏳ Pagamento em análise\n\nPedido: #{{1}}\nValor: R$ {{2}}\nStatus: aguardando confirmação"
   - `admin_pagamento_recusado`: "❌ Pagamento recusado\n\nPedido: #{{1}}\nValor: R$ {{2}}\nSituação: pagamento não aprovado"
   - `admin_pagamento_expirado`: "⌛ Pagamento expirado\n\nPedido: #{{1}}\nValor: R$ {{2}}"
   - `admin_pagamento_cancelado`: "🚫 Pagamento cancelado\n\nPedido: #{{1}}\nValor: R$ {{2}}"
   - `admin_pagamento_reembolsado`: "↩️ Pagamento reembolsado\n\nPedido: #{{1}}\nValor: R$ {{2}}"
   - `admin_chargeback`: "⚠️ Contestação de pagamento\n\nPedido: #{{1}}\nValor: R$ {{2}}\nAção: verifique o pedido no painel administrativo"
   - `admin_falha_reconciliacao`: "🚨 Falha na atualização de pagamento\n\nPedido: #{{1}}\nAção: conferir no painel administrativo"

6. **Aguardar aprovação** de cada template (pode levar minutos a horas).
   Enquanto um template não estiver aprovado, o envio correspondente falha
   de forma **permanente e isolada** (`notification_outbox.status =
   'permanently_failed'`, `last_error_code` como `http_400`/similar) — nunca
   trava os demais eventos, nunca afeta o pedido/pagamento.
7. Configurar o webhook: URL `https://<seu-dominio>/api/webhooks/whatsapp`,
   Verify Token = o mesmo valor de `WHATSAPP_VERIFY_TOKEN`, inscrever-se no
   campo `messages` (para receber `statuses`).
8. Copiar o `App Secret` (Configurações do app > Básico) para
   `WHATSAPP_APP_SECRET`.

---

## 6. Ativação no Render (Fase 2 — não executada nesta PR)

1. Cadastrar todas as variáveis `WHATSAPP_*` no Environment do serviço
   (nunca no `render.yaml`, que só declara os nomes com `sync: false`).
2. Manter `WHATSAPP_NOTIFICATIONS_ENABLED=false` no primeiro deploy — valida
   que a aplicação sobe normalmente com a configuração nova presente mas
   ainda inativa.
3. Deploy controlado (`autoDeploy` já configurado no `render.yaml`).
4. Validar `GET /api/admin/whatsapp-notificacoes/status` (autenticado) —
   deve mostrar `configuration_valid: true` e nenhum erro em
   `configuration_errors`.
5. Confirmar que a migration (`notification_outbox`,
   `whatsapp_status_eventos`) foi aplicada — automático no próximo
   `conectar()` (ver `database/migrations.py::init_db`), sem passo manual.
6. Só então mudar `WHATSAPP_NOTIFICATIONS_ENABLED=true` (novo deploy ou
   apenas reinício, conforme suporte do Render a variáveis sem rebuild) —
   isso também inicia a tarefa periódica do worker (ver seção 1).

---

## 7. Teste seguro / homologação (Fase 3 — não executada nesta PR)

1. Usar um número de teste (WhatsApp Test Number, disponível no painel da
   Meta para desenvolvimento) como destinatário em `WHATSAPP_ADMIN_RECIPIENTS`
   antes de usar um número real.
2. Criar um pedido real de baixo valor (ou usar o ambiente de sandbox do
   Mercado Pago) e confirmar, na ordem:
   - `notification_outbox` recebe uma linha `PEDIDO_CRIADO` com
     `status='pending'`;
   - dentro de até 30s (ciclo do worker), a linha vira `status='sent'` com
     `provider_message_id` preenchido;
   - o número de teste recebe a mensagem;
   - o callback de status (`POST /api/webhooks/whatsapp`) atualiza a linha
     para `delivered`/`read` quando a Meta os enviar;
   - `GET /api/admin/whatsapp-notificacoes?order_id=<id>` mostra o
     histórico completo, sem duplicidade.
3. Reenviar deliberadamente o mesmo webhook do Mercado Pago (ou clicar
   "reconsultar" no painel) e confirmar que **nenhuma segunda mensagem** é
   enviada (idempotência).

---

## 8. Ativação em produção (Fase 4 — não executada nesta PR)

1. Trocar `WHATSAPP_ADMIN_RECIPIENTS` do número de teste para os números
   reais da administração.
2. Criar **um único** pedido de teste real de baixo valor.
3. Confirmar `PEDIDO_CRIADO` e, em seguida, `PIX_GERADO` ou
   `PAGAMENTO_APROVADO` (conforme o método escolhido) chegam ao WhatsApp.
4. Verificar o painel (`GET /api/admin/whatsapp-notificacoes`) e os logs
   estruturados (sanitizados, sem PII) confirmando o envio.

## 9. Monitoramento (Fase 5 — contínua)

Acompanhar via `GET /api/admin/whatsapp-notificacoes/status`:
`queue_counts` (fila por status), `oldest_pending_created_at` (idade da
mensagem pendente mais antiga), e via `GET /api/admin/whatsapp-notificacoes`
(histórico com filtro por `status=permanently_failed`) para identificar
falhas recorrentes, rate limit (`last_error_code` começando com
`rate_limited`) ou duplicidade.

---

## 10. Idempotência

Chave determinística por linha do outbox:

```
whatsapp:pedido:<pedido_id>:<evento_em_minusculo>:<sufixo>[:<referencia_destinatario>]
```

- `PEDIDO_CRIADO`/`PIX_GERADO`: sufixo fixo (`unico`) ou o `txid` do Pix —
  nunca repete para o mesmo pedido.
- `PAGAMENTO_APROVADO`/`RECUSADO`/`CANCELADO`/`REEMBOLSADO`/`CHARGEBACK_RECEBIDO`:
  sufixo é o `id` da linha de `pagamentos` recém-inserida — cada tentativa
  real de pagamento sempre insere uma linha nova (nunca reaproveitada em um
  replay, que é interceptado antes disso pela camada de Idempotency-Key já
  existente em `backend/idempotency.py`), então nunca colide entre
  tentativas diferentes nem duplica a mesma.
- `PAGAMENTO_PENDENTE`: sufixo fixo (`em_analise`) — a transição de status
  que dispara este evento (`Aguardando pagamento`/`Pagamento divergente` →
  `Pagamento em análise`) já é uma transição atômica de ocorrência única.
- `PAGAMENTO_EXPIRADO`: sufixo fixo (`unico`) por pedido.
- `FALHA_DE_RECONCILIACAO`: sufixo é o `evento_id` do webhook do provedor.

A constraint `UNIQUE(idempotency_key)` em `notification_outbox` faz o
`INSERT OR IGNORE` correspondente nunca duplicar — webhook repetido,
reconsulta administrativa e retry do worker no mesmo evento sempre recaem
na mesma linha.

Nenhuma chave usa CPF, e-mail, telefone, nome ou qualquer PII do comprador.

### Garantia real de entrega: dois níveis distintos

A idempotência acima garante que **o evento nunca é enfileirado duas vezes**
(nível de enfileiramento/outbox) — isso é `exactly once` de fato, garantido
pela constraint `UNIQUE(idempotency_key)` do próprio banco.

Isso é diferente de garantir que **a mensagem nunca é enviada duas vezes**
pela Cloud API (nível de envio). A Cloud API da Meta **não oferece** (na
documentação oficial atual) uma chave de idempotência aceita pelo endpoint
`POST /{phone_number_id}/messages` para deduplicar envios do lado do
servidor da Meta — ao contrário de outras integrações deste sistema (ex.:
`X-Idempotency-Key` do Mercado Pago), não há como pedir à Meta "não envie
de novo se eu já pedi este envio antes".

Existe uma janela real, embora estreita, de possível duplicidade: entre
`provider.send_template()` retornar `ok=True` (a Meta já aceitou a
mensagem e devolveu `provider_message_id`) e `_marcar_sucesso` gravar esse
resultado na linha do outbox (`backend/whatsapp_worker.py::_processar_linha`),
um crash do processo deixaria a linha em `status='processing'`. Depois do
timeout de lock (5 min, `_LOCK_TIMEOUT_SEGUNDOS`), outro ciclo do worker
reivindica essa linha novamente e **reenvia a mesma mensagem** — porque,
do ponto de vista do outbox, ela nunca foi confirmada como enviada.

Classificação honesta: **at least once** no nível de envio para o cenário
de crash nessa janela específica (baixa probabilidade — a janela é uma
única instrução Python seguida de um `UPDATE` local, tipicamente
sub-milissegundo — mas não nula); **effectively once** no caminho feliz
(sem crash). Esta implementação **não** garante *exactly once* de ponta a
ponta e a documentação/painel não devem afirmar isso. Não foi implementada
nenhuma mitigação adicional (ex.: persistir o `provider_message_id`
imediatamente após a resposta da Meta em uma escrita separada anterior à
transição de status, reduzindo — mas não eliminando — a janela) nesta PR;
se o volume de produção justificar, é um endurecimento futuro possível sem
mudança de arquitetura.

---

## 11. Retry, backoff e classificação de erros

Erros do provedor são classificados em `backend/whatsapp_provider.py`:

- **Transitórios** (`WhatsAppEnvioTransitorio`): timeout, erro de conexão,
  HTTP 429 (respeita `Retry-After` quando presente), 500/502/503/504.
- **Permanentes** (`WhatsAppEnvioPermanente`): token inválido (401),
  permissão ausente (403), template/payload/número inválido (400/404),
  configuração incompleta.

Backoff exponencial com jitter (`backend/whatsapp_worker.py::
_proximo_intervalo_segundos`): tentativa 1 ≈ `WHATSAPP_RETRY_BASE_SECONDS`
(padrão 60s), dobra a cada tentativa, teto de 1h, jitter de até 25%. Depois
de `WHATSAPP_MAX_RETRIES` tentativas, a linha vira `permanently_failed` —
nunca reprocessada automaticamente; fica visível no painel para
reprocessamento manual explícito (`POST
/api/admin/whatsapp-notificacoes/{id}/reprocessar`), que nunca cria uma
linha duplicada (reabre a mesma linha).

Lock de processamento (`status='processing'`, `locked_at`/`locked_by`)
expira após 5 minutos sem conclusão — outro ciclo do worker recupera a
linha automaticamente (proteção contra crash do worker no meio do
processamento).

---

## 12. Privacidade e LGPD

Mensagens contêm apenas: número interno do pedido, valor, forma de
pagamento (rótulo comercial), modalidade de entrega e o status do evento.
**Nunca incluem**: CPF, e-mail, telefone do cliente, endereço, nome do
comprador, `status_detail` bruto do Mercado Pago, payload de webhook,
token/segredo, dados de cartão.

`notification_outbox.payload_json` guarda exatamente as mesmas variáveis
enviadas ao template (nunca mais que isso) — é o que alimenta o
reprocessamento e o histórico administrativo.

Destinatários administrativos nunca aparecem completos em log ou painel:
`backend/whatsapp_flags.py::mascarar_numero_whatsapp` mascara para o
formato `55*******8888`; o outbox em si nunca guarda o número, apenas uma
referência hash não-reversível (`backend/whatsapp_outbox.py::
_referencia_destinatario`), resolvida de volta ao número real só no
momento do envio, a partir da configuração *atual* — remover um número de
`WHATSAPP_ADMIN_RECIPIENTS` automaticamente impede envios pendentes para
ele (falha permanente `recipient_no_longer_configured`, nunca envia).

---

## 13. Rollback

1. `WHATSAPP_NOTIFICATIONS_ENABLED=false` — efeito imediato no próximo
   deploy/reinício: a tarefa periódica do worker para de ser criada,
   nenhuma nova notificação é enviada. Pedidos, pagamentos e o webhook do
   Mercado Pago continuam funcionando sem qualquer alteração de
   comportamento.
2. Inspecionar a fila: `GET /api/admin/whatsapp-notificacoes?status=pending`.
3. Cancelar pendentes manualmente se necessário: `POST
   /api/admin/whatsapp-notificacoes/{id}/cancelar` (só linhas
   `pending`/`retry`).
4. Corrigir a configuração (token rotacionado, template renomeado etc.) via
   variáveis de ambiente.
5. Reprocessar seletivamente eventos específicos que falharam
   permanentemente: `POST /api/admin/whatsapp-notificacoes/{id}/reprocessar`.
6. Retomar: `WHATSAPP_NOTIFICATIONS_ENABLED=true` novamente.

Nenhuma migration desta mudança remove ou renomeia dados existentes — só
adiciona as tabelas `notification_outbox` e `whatsapp_status_eventos`
(`CREATE TABLE IF NOT EXISTS`, idempotente).

### Crescimento da tabela e retenção

`notification_outbox` cresce indefinidamente com o tempo (uma ou mais
linhas por evento administrativo, por destinatário) — **esta PR não
implementa nenhuma retenção/expurgo automático** das linhas já concluídas
(`sent`/`delivered`/`read`/`cancelled`/`permanently_failed`). Impacto
estimado é baixo no volume esperado desta loja (poucas notificações por
pedido, não por visita/request), mas é um crescimento não limitado que uma
operação de longo prazo deve monitorar. Nenhuma exclusão foi implementada
sem autorização explícita — se necessário no futuro, deve ser uma decisão
operacional separada (ex.: um job de expurgo por idade, mantendo sempre um
período mínimo para auditoria), não parte desta fundação.

---

## 14. Rotação de token

1. Gerar um novo System User Token no painel da Meta.
2. Atualizar `WHATSAPP_ACCESS_TOKEN` no Render.
3. Reiniciar o serviço (ou aguardar o próximo deploy).
4. Revogar o token antigo no painel da Meta.

Nenhum token é persistido no banco de dados nesta implementação — sempre
lido da variável de ambiente do processo em tempo real.

---

## 15. Limites conhecidos

- Limite de mensagens/dia da conta (Meta) — não gerenciado ativamente pelo
  código; um HTTP 429 é tratado como erro transitório com retry/backoff.
- Templates não aprovados bloqueiam permanentemente o evento correspondente
  até a aprovação — nunca envia texto livre como substituto.
- A tarefa periódica em processo (opção 1, seção 1) compartilha o mesmo
  processo web; sob volume muito alto, considerar a opção 2 (processo
  dedicado), já suportada pelo mesmo código sem alteração.
- `WHATSAPP_ADMIN_PAINEL_URL` está reservada na configuração mas nenhum
  template desta PR inclui link — adicionar apenas com decisão de negócio
  explícita, sempre HTTPS e sem dado pessoal na URL.
- **Sem alerta proativo.** Observabilidade é só *pull* (`GET
  /api/admin/whatsapp-notificacoes/status` e o histórico) — não existe
  nenhum mecanismo desta PR que avise ativamente um administrador (e-mail,
  push, outro canal) se o worker parar, a fila crescer, a configuração
  ficar inválida, templates forem rejeitados, o token expirar, houver rate
  limit sustentado ou locks abandonados se acumularem. Detectar essas
  condições hoje depende de alguém consultar o endpoint de status
  periodicamente (manual) ou de ferramentas externas de monitoramento
  configuradas fora desta implementação. Também não há nenhuma métrica no
  formato Prometheus/OpenMetrics — só os campos já citados na seção de
  Monitoramento, expostos apenas via API autenticada.
- **Garantia de entrega**: `effectively once` no caminho feliz, `at least
  once` num crash na janela estreita entre a Meta aceitar o envio e o
  outbox local gravar isso — ver seção 10, "Garantia real de entrega".
  Nunca `exactly once` de ponta a ponta.
- **Sem UI de painel.** Só a API REST administrativa existe nesta PR — ver
  seção 17 ("Fora do escopo").
- **Sem detector proativo de drift.** `FALHA_DE_RECONCILIACAO` só dispara
  quando uma falha real e persistente já ocorreu no processamento de um
  webhook validado (ver tabela de eventos, seção 2) — não existe, nesta
  PR, nenhuma varredura periódica que compare o estado local dos pedidos
  contra o estado real no Mercado Pago para detectar divergência
  silenciosa ao longo do tempo (ex.: um pagamento aprovado no provedor que
  nunca chegou a refletir localmente por um motivo não coberto pelos
  caminhos de erro já tratados). Implementar esse detector é trabalho
  futuro deliberadamente fora do escopo desta fundação.
- **Sem retenção automática de `notification_outbox`.** Ver "Crescimento
  da tabela e retenção", seção 13.

---

## 16. Checklist de produção

- [ ] App Meta criado, WhatsApp Business Account vinculado, número
      verificado
- [ ] `WHATSAPP_PHONE_NUMBER_ID` / `WHATSAPP_BUSINESS_ACCOUNT_ID` anotados
- [ ] System User Token gerado com permissão `whatsapp_business_messaging`
- [ ] 10 templates cadastrados, categoria Utilidade, idioma `pt_BR`
- [ ] Todos os 10 templates **aprovados** pela Meta
- [ ] Webhook cadastrado (`/api/webhooks/whatsapp`), verify token conferido
- [ ] `WHATSAPP_APP_SECRET` cadastrado
- [ ] `WHATSAPP_ADMIN_RECIPIENTS` com os números reais da administração
      (nunca números de clientes)
- [ ] Todas as variáveis cadastradas no Render com
      `WHATSAPP_NOTIFICATIONS_ENABLED=false`
- [ ] Deploy validado, `GET /api/admin/whatsapp-notificacoes/status` mostra
      `configuration_valid: true`
- [ ] Teste com número de teste da Meta concluído com sucesso (envio +
      delivered + histórico + sem duplicidade)
- [ ] `WHATSAPP_NOTIFICATIONS_ENABLED=true` ativado
- [ ] Pedido de teste real único confirmado ponta a ponta
- [ ] Monitoramento inicial (fila, falhas, rate limit) acompanhado por pelo
      menos alguns dias

---

## 17. Fora do escopo desta implementação

- Mensagens para o cliente (confirmação, rastreamento, pedido de avaliação).
- Recuperação de carrinho abandonado.
- Marketing, campanhas, promoções.
- Qualquer envio fora de templates transacionais (Utilidade).
- Armazenamento de token/segredo no painel administrativo (frontend) — as
  credenciais continuam exclusivamente em variáveis de ambiente do
  servidor.
- **Tela visual do painel administrativo.** Esta PR entrega somente a API
  REST administrativa (`backend/whatsapp_admin_routes.py`: histórico,
  status operacional, reprocessar, cancelar), autenticada e testada — não
  uma página HTML/JS própria nem uma seção nova dentro de
  `admin-pedidos.html` (ou equivalente) para o operador navegar
  visualmente. Consumir esses endpoints em alguma tela existente/nova do
  painel é trabalho de frontend ainda não feito; até lá, a operação só
  consegue inspecionar/agir sobre a fila via chamada direta à API (ou uma
  ferramenta como `curl`/Postman autenticada). Revisão visual/de
  acessibilidade (desktop, mobile, teclado, `aria-live`, layout shift) não
  se aplica por não haver UI para revisar.
