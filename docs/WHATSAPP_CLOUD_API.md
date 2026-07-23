# Central de Atendimento WhatsApp (Cloud API oficial da Meta)

Recebe mensagens de clientes pelo WhatsApp, guarda a conversa e permite que
um administrador responda pelo painel (`central-atendimento.html`),
vinculando a conversa a um cliente e a um pedido já existentes.

**Escopo:** só o número comercial já conectado e em produção no WhatsApp
Manager da Meta. Nenhuma automação de WhatsApp Web, Selenium, navegador
controlado, link `wa.me` ou API não-oficial é usada em nenhum ponto desta
implementação.

**Estado atual:** desligado por padrão em qualquer ambiente (inclusive
produção), via `WHATSAPP_CLOUD_ENABLED=false`. Ativar exige concluir o
checklist completo deste documento.

Este recurso é **separado** das notificações administrativas de pedido/
pagamento já existentes (`docs/admin/WHATSAPP_NOTIFICACOES.md`,
`WHATSAPP_NOTIFICATIONS_ENABLED`): as duas flags são independentes, cada
fluxo tem sua própria tabela de idempotência, e nenhum dos dois lê/escreve
nas tabelas do outro. Os dois reaproveitam as mesmas credenciais da Meta
(mesmo número, mesmo app), porque é a mesma conta WhatsApp Business.

---

## 1. Arquitetura

```
Cliente envia mensagem no WhatsApp
        │
        ▼
POST /api/webhooks/whatsapp  (Meta Cloud API)
        │  1. valida assinatura HMAC (X-Hub-Signature-256)
        │  2. lê o corpo bruto, valida tamanho, só então faz parse do JSON
        ▼
backend/whatsapp_inbox_service.py::processar_webhook_mensagens
        │  reivindica o evento em whatsapp_webhook_events (idempotência)
        ▼
backend/whatsapp_inbox_repository.py
        │  upsert de contato → conversa → mensagem
        ▼
SQLite: whatsapp_contacts / whatsapp_conversations / whatsapp_messages
        │
        ▼
GET /api/admin/whatsapp/conversations (painel, sessão admin)
        │
        ▼
central-atendimento.html / central-atendimento.js
```

Envio de resposta pelo painel:

```
POST /api/admin/whatsapp/conversations/{id}/messages  (sessão admin + Idempotency-Key)
        │
        ▼
backend/whatsapp_provider.py::MetaWhatsAppCloudProvider
        │  send_inbox_text (dentro da janela de 24h) OU send_template
        ▼
Graph API da Meta — POST .../messages
```

Mídia recebida (imagem/documento/áudio/vídeo/sticker): só os **metadados**
(`media_id`, `mime_type`, legenda) são salvos no recebimento. O arquivo em si
só é baixado sob demanda, quando um administrador abre a mídia no painel
(`GET /api/admin/whatsapp/media/{message_id}`), nunca automaticamente —
minimização de dados e menor superfície de risco.

### Separação do webhook de notificações administrativas

`POST /api/webhooks/whatsapp` é o **mesmo endpoint** usado pelos callbacks de
status de entrega das notificações administrativas
(`docs/admin/WHATSAPP_NOTIFICACOES.md`) — a Meta só permite um webhook por
app/número, então o mesmo corpo de requisição pode conter `statuses`
(processados por `_aplicar_status_entrega`, inalterado) e `messages`
(processados por `processar_webhook_mensagens`, só quando
`WHATSAPP_CLOUD_ENABLED=true`). As duas idempotências, tabelas e feature
flags permanecem completamente independentes.

---

## 2. Domínio público da API (confirmado, não presumido)

O site estático (GitHub Pages, `CNAME`) fica em `misticaesotericos.com.br` /
`www.misticaesotericos.com.br`. O backend (FastAPI, Render) é um serviço
**separado**, publicado sob um subdomínio próprio: `site-config.js` define

```
apiBaseUrl: "https://api.misticaesotericos.com.br"
```

`render.yaml` declara o serviço Render como `misticapresentes-api`
(`startCommand: uvicorn backend.main:app`), com o domínio customizado
`api.misticaesotericos.com.br` apontado para ele — o domínio público real do
backend não é o domínio do site.

### URL exata do webhook

```
https://api.misticaesotericos.com.br/api/webhooks/whatsapp
```

Se o DNS de `api.misticaesotericos.com.br` ainda não estiver propagado/
configurado no Render no momento da ativação, o serviço também responde pela
URL padrão do Render (formato `https://<nome-do-serviço>.onrender.com`,
visível no dashboard do Render em **Settings → domínio padrão** do serviço
`misticapresentes-api`) — use-a apenas como fallback temporário de teste,
nunca como configuração definitiva no painel da Meta.

---

## 3. Variáveis de ambiente

Todas nascem vazias/desligadas — ver `.env.example` para a lista comentada
completa. Resumo:

Reaproveitadas das notificações administrativas (mesma conta Meta):
`WHATSAPP_GRAPH_API_VERSION`, `WHATSAPP_PHONE_NUMBER_ID`,
`WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` (aceita também o alias
`WHATSAPP_WEBHOOK_VERIFY_TOKEN`, mesmo significado — preencha só um dos
dois).

Novas, específicas da Central de Atendimento:

| Variável | Padrão | Efeito |
|---|---|---|
| `WHATSAPP_CLOUD_ENABLED` | `false` | Liga/desliga a Central de Atendimento (mensagens recebidas). Fail-closed: com `false`, nenhuma mensagem é persistida, mas o handshake GET continua funcionando. |
| `WHATSAPP_WEBHOOK_MAX_BODY_BYTES` | `1048576` | Corpo máximo aceito no POST do webhook, antes do parse do JSON. |
| `WHATSAPP_MEDIA_MAX_BYTES` | `10485760` | Tamanho máximo aceito para uma mídia baixada. |
| `WHATSAPP_MEDIA_STORAGE_DIR` | `/data/uploads/whatsapp` | Diretório de mídia — aponte para o disco persistente do Render. |
| `WHATSAPP_MEDIA_RETENTION_DAYS` | `90` | Retenção de mídia (dias). |
| `WHATSAPP_WEBHOOK_EVENT_RETENTION_DAYS` | `30` | Retenção dos eventos brutos do webhook (dias). |
| `WHATSAPP_NOTIFICATION_SOUND_ENABLED` | `true` | Controla só o som local do painel — nunca a permissão de notificação do navegador (essa é sempre pedida por um clique explícito do administrador). |
| `WHATSAPP_INBOX_TEMPLATES` | (vazio) | Templates aprovados para responder fora da janela de 24h, formato `nome:idioma,nome2:idioma2`. |

Comportamento fail-closed: com `WHATSAPP_CLOUD_ENABLED=true` mas alguma
variável obrigatória (`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_APP_SECRET`, verify token) ausente, `whatsapp_cloud_inbox_habilitado()`
retorna `false` — o recurso não funciona parcialmente, e o painel mostra
"desabilitada/não configurada" em vez de um erro genérico. A inicialização
do FastAPI nunca falha por causa disso.

---

## 4. Segurança do webhook

- **GET** (`hub.mode`, `hub.verify_token`, `hub.challenge`): só devolve o
  challenge quando `hub.mode == "subscribe"` **e** o token bate em tempo
  constante (`secrets.compare_digest`) com `WHATSAPP_VERIFY_TOKEN`. Qualquer
  outra condição → 403. O verify token nunca é logado.
- **POST**: lê o corpo bruto antes de decodificar JSON; corpo acima de
  `WHATSAPP_WEBHOOK_MAX_BODY_BYTES` → 413; assinatura ausente/inválida
  (`X-Hub-Signature-256: sha256=<HMAC-SHA256(corpo, WHATSAPP_APP_SECRET)>`,
  comparada em tempo constante) → 401; só então o JSON é parseado. Payload
  inválido → 400. Erros nunca retornam detalhe interno.
- **Idempotência**: cada mensagem é reivindicada em
  `whatsapp_webhook_events` por `meta_message_id` (fallback: hash SHA-256
  canônico do bloco da mensagem). Reenvio do mesmo evento pela Meta nunca
  duplica mensagem, conversa ou notificação — é apenas contado como
  duplicado.
- Nenhum log de produção grava telefone completo, texto da mensagem, token,
  app secret, verify token ou payload bruto.

---

## 5. Privacidade, retenção e LGPD

**Finalidade dos dados:** permitir que a equipe da loja responda mensagens de
clientes pelo WhatsApp dentro do painel administrativo, vinculando o
atendimento a pedidos/clientes já cadastrados.

**Quem pode acessar:** só administradores autenticados
(`backend.panel_sessions.exigir_perfil("adm")`) — nenhum endpoint desta
seção aceita a chave de API estática usada por integrações servidor-a-
servidor.

**Retenção:**
- Mensagens/conversas: sem expiração automática (registro de atendimento,
  preservado como pedidos/clientes já são).
- Eventos brutos do webhook (`whatsapp_webhook_events`): `expires_at`
  calculado a partir de `WHATSAPP_WEBHOOK_EVENT_RETENTION_DAYS`; a limpeza
  periódica é responsabilidade de uma rotina administrativa futura (não
  implementada nesta mudança — ver "Limitações").
- Mídia em disco: `WHATSAPP_MEDIA_RETENTION_DAYS`; a exclusão automática
  também é uma limitação em aberto (ver abaixo).

**Limitação de criptografia em repouso (documentada, não contornada):** este
projeto não tem infraestrutura própria de gerenciamento de chaves (KMS/HSM).
Implementar criptografia de campo caseira seria pior que não ter nenhuma
(falsa sensação de segurança, chave provavelmente ficaria no mesmo lugar que
o dado). Por isso o telefone é armazenado em texto, no mesmo nível de
proteção que `clientes.telefone` já usa hoje neste projeto — acesso restrito
a administradores autenticados, nunca exposto por rota pública — e toda
exibição no painel usa os últimos 4 dígitos (`phone_last4`) em vez do número
completo. Se o projeto adotar um KMS gerenciado (ex.: AWS KMS, GCP KMS) no
futuro, esta é a lacuna a fechar primeiro.

**Exclusão/anonimização:** hoje é manual (acesso direto ao banco por quem já
tem essa responsabilidade sobre `clientes`/`pedidos`); não há endpoint
dedicado de "esquecer contato" nesta primeira entrega.

---

## 6. Como testar com um número externo

1. Ative `WHATSAPP_CLOUD_ENABLED=true` e confirme `GET /api/admin/whatsapp/status`
   → `webhook_ready: true`.
2. Configure o webhook no painel da Meta (seção 8 abaixo) e assine o campo
   `messages`.
3. Envie uma mensagem de um número de celular real para o número comercial.
4. Confira em `central-atendimento.html` se a conversa aparece com contador
   de não lidas.
5. Responda pelo painel (só texto livre se a mensagem do cliente tiver
   chegado há menos de 24h; caso contrário, escolha um template aprovado).
6. Confirme no celular do cliente que a resposta chegou.

---

## 7. Troubleshooting

| Sintoma | Causa provável |
|---|---|
| `GET /api/webhooks/whatsapp` devolve 403 na verificação da Meta | `WHATSAPP_VERIFY_TOKEN`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN` divergente do cadastrado no painel da Meta. |
| Mensagens chegam na Meta mas não aparecem no painel | `WHATSAPP_CLOUD_ENABLED` ainda `false`, ou alguma variável obrigatória ausente (`GET /api/admin/whatsapp/status` mostra `configuration_errors`). |
| Envio de texto livre falha com pedido de template | Conversa fora da janela de 24h desde a última mensagem do cliente — normal, use um template aprovado (`WHATSAPP_INBOX_TEMPLATES`). |
| Mídia não abre no painel | Verifique `WHATSAPP_MEDIA_STORAGE_DIR` (disco persistente montado?) e `WHATSAPP_MEDIA_MAX_BYTES`. |
| 401 em qualquer rota `/api/admin/whatsapp/*` | Sessão administrativa expirada — o painel redireciona ao login automaticamente. |

---

## 8. Configuração manual na Meta

Preencha exatamente estes campos no painel da Meta (Meta for Developers →
seu app → WhatsApp → Configuração):

- **URL de retorno de chamada (Callback URL):**
  `https://api.misticaesotericos.com.br/api/webhooks/whatsapp`
- **Token de verificação:** o mesmo valor colocado em
  `WHATSAPP_VERIFY_TOKEN`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN` no Render (gere uma
  string aleatória longa — nunca reutilize uma senha existente).
- **Campo do webhook a assinar:** `messages`.
- **Aplicativo:** o app já conectado ao número comercial em produção.
- **Conta do WhatsApp Business (WABA):** a mesma já usada pelas notificações
  administrativas (`WHATSAPP_BUSINESS_ACCOUNT_ID`).
- **Número:** o número comercial já conectado e em produção.

## Variáveis para configurar no Render

Só os **nomes** — nunca os valores reais neste repositório:

```
WHATSAPP_CLOUD_ENABLED
WHATSAPP_WEBHOOK_VERIFY_TOKEN (ou reaproveitar WHATSAPP_VERIFY_TOKEN)
WHATSAPP_WEBHOOK_MAX_BODY_BYTES
WHATSAPP_MEDIA_MAX_BYTES
WHATSAPP_MEDIA_STORAGE_DIR
WHATSAPP_MEDIA_RETENTION_DAYS
WHATSAPP_WEBHOOK_EVENT_RETENTION_DAYS
WHATSAPP_NOTIFICATION_SOUND_ENABLED
WHATSAPP_INBOX_TEMPLATES
```

(As demais — `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` — já existem no Render para as
notificações administrativas; reaproveite-as.)

---

## 9. Plano de ativação

1. **Etapa A** — deploy do código com `WHATSAPP_CLOUD_ENABLED=false`;
   confirmar migrations aplicadas e que loja/pedidos/pagamentos continuam
   normais.
2. **Etapa B** — configurar as variáveis no Render, reiniciar; validar
   `GET /api/webhooks/whatsapp` (handshake) e que o painel administrativo
   continua exigindo login.
3. **Etapa C** — cadastrar o webhook na Meta, assinar `messages`, testar com
   um telefone externo (seção 6), confirmar persistência e resposta pelo
   painel.
4. **Etapa D** — ativar para uso contínuo da equipe; monitorar
   `GET /api/admin/whatsapp/status` (`pending_events`, `last_error_at`).

## 10. Rollback

- Definir `WHATSAPP_CLOUD_ENABLED=false` — mensagens novas param de ser
  persistidas; conversas/mensagens já salvas **não são apagadas**.
- Nenhuma migration é revertida (todas são aditivas — `CREATE TABLE IF NOT
  EXISTS`).
- Se necessário, remova/pause a assinatura do webhook no painel da Meta
  (isso não afeta as notificações administrativas de pedido/pagamento, que
  usam o mesmo endpoint mas uma flag independente).

---

## 11. Limitações conhecidas desta primeira entrega

- Atualização do painel é por **polling** (a cada alguns segundos), não SSE/
  WebSocket — mais simples de operar no plano atual do Render, sem
  infraestrutura adicional; pode ser revisitado se o volume de conversas
  simultâneas crescer.
- Não há endpoint dedicado de limpeza/anonimização automática de
  `whatsapp_webhook_events`/mídia expirada — os campos `expires_at`/retenção
  estão no lugar, mas a rotina de expurgo em si fica para uma iteração
  seguinte.
- `GET /api/admin/whatsapp/templates` lê só a lista configurada em
  `WHATSAPP_INBOX_TEMPLATES` (nunca consulta a Graph API em tempo real) —
  mantenha essa lista sincronizada manualmente com os templates aprovados no
  painel da Meta.
- Vínculo cliente/pedido é manual (por ID, decidido pelo administrador) —
  não há resolução automática por telefone nesta entrega inicial, para evitar
  vincular por engano quando o mesmo número aparecer em mais de um
  cadastro.
