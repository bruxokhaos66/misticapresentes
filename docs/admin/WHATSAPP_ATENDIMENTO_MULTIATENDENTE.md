# Central Multiatendente — perfis, fila, assunção e transferência

Esta é a segunda etapa da Central de Atendimento WhatsApp (depois de
`docs/WHATSAPP_CLOUD_API.md`, que cobre a Cloud API e a Central original,
administrador-apenas). Aqui documentamos o que foi adicionado por cima dela:
perfis `supervisor_atendimento`/`vendedor`, fila (`waiting`/`assigned`/
`resolved`), assunção atômica (claim), liberação, transferência,
finalização/reabertura e histórico de auditoria.

**Fora do escopo desta etapa** (ficam para PRs futuras): catálogo de
produtos, envio de produtos, links rastreáveis, PWA, notificações push, IA,
comissões, métricas comerciais avançadas, WebSocket/SSE, vínculo automático
com cliente, distribuição automática de conversas.

## 1. Papéis e permissões

Três perfis (coluna `usuarios.perfil`, mesma tabela do painel/POS —
`vendedor` já existia; `supervisor_atendimento` é novo):

| Ação                              | adm | supervisor_atendimento | vendedor |
|------------------------------------|:---:|:-----------------------:|:--------:|
| Ver todas as conversas / fila      | ✅  | ✅                       | fila + próprias |
| Assumir conversa livre             | ✅  | ✅                       | ✅ |
| Responder conversa própria         | ✅  | ✅                       | ✅ |
| Responder conversa de outro        | ✅* | ✅*                      | ❌ |
| Liberar/transferir conversa própria| ✅  | ✅                       | ✅ (para outro vendedor, se `ATENDIMENTO_ALLOW_SELLER_TRANSFER`) |
| Liberar/transferir qualquer conversa | ✅ | ✅                     | ❌ |
| Finalizar/reabrir qualquer conversa| ✅  | ✅ (reabrir também)      | finalizar só a própria |
| Gerenciar vendedores (habilitar, limite, suspender, perfil) | ✅ | ✅ (não cria/edita adm) | ❌ |
| Ver histórico/auditoria da conversa| ✅  | ✅                       | ❌ |

`*` só quando `ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN=false` (padrão:
`true`, ou seja, mesmo adm/supervisor precisam assumir antes de responder,
para consistência da fila).

Toda autorização é revalidada **no backend**, a cada chamada, direto no
banco (nunca confia só no perfil cacheado na sessão nem em botão escondido
no frontend) — ver `backend/atendimento_repository.py::exigir_atendente` e
`autorizado_para_conversa`.

## 2. Dados do atendente

Reaproveita `usuarios` (nenhuma tabela nova de usuário). Colunas
adicionadas, todas prefixadas `atendimento_` para nunca colidir com o uso
existente da tabela pelo POS/painel:

- `atendimento_enabled` (bool) — precisa estar ligado para o
  supervisor/vendedor acessar a Central operacionalmente (adm sempre pode).
- `atendimento_status` — `online`/`ausente`/`ocupado`/`offline` (exibição;
  nunca decide sozinho se alguém pode assumir conversa).
- `atendimento_max_active_conversations` — limite individual; `NULL` cai no
  padrão de `ATENDIMENTO_MAX_ACTIVE_CONVERSATIONS`.
- `atendimento_last_activity_at`, `atendimento_suspended_at`.

Usuário inativo (`usuarios.ativo=0`), suspenso (`atendimento_suspended_at`
preenchido) ou com `atendimento_enabled=0` nunca assume/responde conversa —
checado no banco a cada chamada.

## 3. Modelo de fila

Colunas adicionadas em `whatsapp_conversations`: `assigned_user_id`,
`assigned_at`, `assignment_version`, `queue_status`
(`waiting`/`assigned`/`resolved`), `resolved_at`, `resolved_by`,
`last_agent_activity_at`.

`queue_status` é **independente** do `status` legado (`open`/`pending`/
`resolved`/`archived`) — os dois convivem: o `status` legado continua
existindo para o fluxo administrador-apenas (`ATENDIMENTO_SELLERS_ENABLED=
false`); `queue_status` é a fonte de verdade da fila multiatendente.

Backfill (migração aditiva, sem `DROP`, sem perda de dado): conversas com
`status` legado `resolved`/`archived` viram `queue_status='resolved'`;
todas as outras nascem `waiting`, sem atendente. Nenhuma mensagem ou
conversa é apagada.

## 4. Assunção atômica (claim)

`POST /api/admin/whatsapp/conversations/{id}/claim`

```sql
UPDATE whatsapp_conversations
   SET assigned_user_id=?, assigned_at=?, assignment_version=assignment_version+1, queue_status='assigned'
 WHERE id=? AND assigned_user_id IS NULL AND queue_status='waiting' AND resolved_at IS NULL
```

O `rowcount` da própria transação decide quem venceu — o modo WAL do
SQLite serializa escritores, então não existe janela de corrida real entre
duas chamadas concorrentes. A resposta distingue: sucesso, já assumida por
outro (`409 already_claimed`), conversa encerrada (`409
conversation_resolved`), limite atingido (`409 limit_reached`), suspenso/
desabilitado (`403`), sem permissão (`403`). Nunca devolve dado pessoal do
outro atendente além do necessário.

## 5. Limite de conversas

`ATENDIMENTO_MAX_ACTIVE_CONVERSATIONS` (padrão) pode ser sobrescrito por
`usuarios.atendimento_max_active_conversations`. A contagem e a assunção
rodam na **mesma transação**: se o claim colocar o atendente acima do
limite (corrida entre duas abas, por exemplo), a reivindicação é revertida
antes do commit e o cliente recebe `409 limit_reached` — a conversa nunca
fica "presa" num estado intermediário.

## 6. Transferência

`POST /api/admin/whatsapp/conversations/{id}/transfer` — controle otimista
por `assignment_version` (opcional no corpo; se enviado e desatualizado,
`409 version_conflict`). Adm/supervisor transferem qualquer conversa aberta
para qualquer atendente ativo/habilitado; vendedor só transfere conversa
**própria** para outro **vendedor** ativo, e só se
`ATENDIMENTO_ALLOW_SELLER_TRANSFER=true`. Nunca para o próprio usuário,
nunca para conversa encerrada, nunca ultrapassando o limite do destino.

## 7. Finalização / reabertura

- `POST /conversations/{id}/resolve` — adm/supervisor em qualquer conversa;
  vendedor só na própria. `assigned_user_id` é **preservado** (histórico),
  só `queue_status`/`status` mudam.
- `POST /conversations/{id}/reopen` — só adm/supervisor_atendimento. Volta
  para `waiting` **sem** atendente (nunca reatribui automaticamente).
- Mensagem nova do cliente numa conversa encerrada: reabre automaticamente
  para `waiting` (nunca atribui a ninguém), registra `auto_reopen` no
  histórico, preserva toda a conversa/mensagens anteriores (a mesma
  `conversation_id` continua sendo usada — ver
  `backend/whatsapp_inbox_repository.py::obter_ou_criar_conversa`).

## 8. Controle de envio

Antes de qualquer envio (`POST /conversations/{id}/messages`):
sessão válida → perfil permitido → `ATENDIMENTO_SELLERS_ENABLED` →
conversa aberta → pertence ao usuário (salvo adm/supervisor quando
`ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN=false`) → `assignment_version`
(se enviado) → janela de 24h/template → `Idempotency-Key` obrigatória (já
existia). Tentativa de envio sem assumir é registrada no histórico como
`send_denied`. Com a flag desligada, o fluxo é idêntico ao anterior a esta
PR (só adm, sem exigir assunção).

## 9. Histórico / auditoria

Tabela `atendimento_assignment_history` (imutável — só `INSERT`, nunca
`UPDATE`/`DELETE`): `claim`, `release`, `transfer`, `resolve`, `reopen`,
`auto_reopen`, `send_denied`. Nunca grava conteúdo de mensagem, telefone
completo, token ou payload bruto da Meta — só ids, motivo (texto curto
sanitizado) e versões. Consulta: `GET
/conversations/{id}/assignment-history` (só adm/supervisor).

## 10. Flags (todas desligadas/no padrão mais conservador por padrão)

| Variável | Padrão | Efeito |
|---|---|---|
| `ATENDIMENTO_SELLERS_ENABLED` | `false` | Interruptor mestre. Desligada = fluxo idêntico ao pré-existente. |
| `ATENDIMENTO_MAX_ACTIVE_CONVERSATIONS` | `5` | Limite padrão por atendente. |
| `ATENDIMENTO_PRESENCE_TIMEOUT_SECONDS` | `120` | Só exibição de presença. |
| `ATENDIMENTO_ALLOW_SELLER_TRANSFER` | `true` | Vendedor transferir conversa própria p/ outro vendedor. |
| `ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN` | `true` | Exige assunção também para adm/supervisor. |

## 11. Rollout gradual

- **Etapa A** — deploy com `ATENDIMENTO_SELLERS_ENABLED=false`; validar que
  o fluxo administrador-apenas continua idêntico.
- **Etapa B** — ligar a flag; habilitar `atendimento_enabled=1` para um
  vendedor de teste, limite 2; validar fila, claim e resposta.
- **Etapa C** — adicionar um segundo vendedor; validar concorrência
  (claim duplo) e transferência.
- **Etapa D** — liberar para a equipe inteira.

**Rollback**: `ATENDIMENTO_SELLERS_ENABLED=false` e reiniciar. O fluxo
administrador legado volta a funcionar imediatamente. Nunca reverter a
migração, nunca apagar `atendimento_assignment_history`/atribuições —
tudo fica preservado para quando a flag for ligada de novo.

## 12. Roteiro de teste manual

1. Em homologação, definir `ATENDIMENTO_SELLERS_ENABLED=true` e reiniciar.
2. No painel "Vendedores" da Central (aba visível só para adm/supervisor),
   habilitar atendimento para dois vendedores de teste.
3. Enviar uma mensagem de um telefone externo real (ou simular via
   webhook) para o número configurado.
4. Confirmar que a conversa aparece na aba **Fila** para os dois vendedores.
5. Abrir duas sessões (dois navegadores/abas, um login por vendedor).
6. Clicar **Assumir** quase simultaneamente nas duas sessões.
7. Confirmar que só uma venceu (a outra recebe uma mensagem clara de
   "já foi assumida por outro atendente").
8. Responder pelo vencedor — deve funcionar.
9. Confirmar que o outro vendedor não consegue responder (403) nem ver a
   conversa na aba "Minhas conversas".
10. Transferir a conversa para o segundo vendedor (modal "Transferir").
11. Responder pelo novo responsável.
12. Finalizar a conversa.
13. Enviar uma nova mensagem do mesmo telefone externo.
14. Confirmar que a conversa reaparece na fila (aba **Fila**), sem
    atendente atribuído.

## 13. Limitações conhecidas desta etapa

- Sem distribuição automática de conversas — só fila manual + assunção.
- Sem WebSocket/SSE — a lista/mensagens ainda usam polling (mesmo intervalo
  de antes).
- Presença (`atendimento_status`) é só exibição; não bloqueia nem libera
  atribuição automaticamente.
- Vínculo com cliente/pedido continua manual (por ID), como antes desta
  etapa.
