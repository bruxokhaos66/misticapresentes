# Runbook de Go Live — Fase C (Produção, Recuperação e Operação)

Este runbook cobre o procedimento operacional de deploy, verificação pós-deploy,
rollback e resposta a incidentes da API (`misticapresentes-api`, Render) e do
site estático (GitHub Pages). Complementa (não substitui)
`docs/admin/BACKUP_MONITORAMENTO_DEPLOY.md`.

## Antes do deploy

1. Confirmar backup recente e íntegro:
   - `GET /api/admin/backup/status` (sessão de admin ou chave de API) — checar
     `ultimo_backup`, `integridade: "ok"`, `ultimo_erro: null`.
   - Se o último backup automático tiver mais de 24h ou `status != "ok"`,
     rodar `POST /api/backup/manual` antes de prosseguir.
2. Confirmar variáveis de ambiente no Render (Dashboard → Environment):
   `APP_ENV=production`, `MISTICA_DB_PATH=/data/...`, `BACKUP_ENABLED=true`,
   `BACKUP_DIRECTORY=/data/backups`, chaves de API/sync configuradas.
3. Confirmar que o plano do serviço é `starter` (ou superior) — no plano
   `free` o disco `/data` não é provisionado e o banco volta vazio a cada
   sleep/redeploy (ver comentário em `render.yaml`).
4. Rodar a suíte de testes localmente (`pytest`) e garantir que os PRs
   anteriores (Fase A/B) continuam verdes — nenhuma regressão introduzida.
5. Revisar migrations pendentes: `database/migrations.py::init_db()` é
   idempotente e roda automaticamente no startup (`lifespan`), então não há
   passo manual de migration — mas vale ler o diff em busca de novas tabelas
   antes de confiar cegamente nisso.
6. Confirmar que existe rollback disponível: deploy anterior saudável visível
   em **Render → Events/Deploys**, e ao menos um backup validado no disco.

## Durante o deploy

1. Acompanhar os logs de build/deploy no Render em tempo real.
2. Assim que o novo processo subir, checar os logs de inicialização
   (`startup_persistencia`, `startup_concluido`) — confirmar
   `"persistente": true` e `"banco_ok": true`/`"disco_ok": true`.
3. Checar `/api/health/live` (processo vivo) e, em seguida,
   `/api/health/ready` (banco acessível, gravável, migrations aplicadas,
   disco persistente saudável) — só considerar o deploy "no ar" quando
   `ready` retornar `200`.
4. Confirmar que os workers periódicos subiram: nenhum log de exceção em
   `_expirar_pedidos_periodicamente` / `scheduler_backup` nos primeiros
   minutos.
5. Fazer uma primeira requisição de leitura simples
   (`GET /api/produtos/{id}` de um produto conhecido) para confirmar que a
   API responde de ponta a ponta, não só o health check.

## Depois do deploy

1. **Compra teste completa**: criar um pedido de teste no site (produto de
   baixo valor), confirmar que o estoque é reservado, o pedido aparece no
   painel e o status muda corretamente ao longo do fluxo.
2. **Pix teste**: gerar uma cobrança Pix de teste (valor simbólico) e
   confirmar que o webhook de confirmação chega e o pedido muda de status
   sem duplicar (idempotência do webhook já coberta por
   `tests/test_pagamento_*`).
3. **Estoque**: conferir que a baixa/reposição de estoque do pedido teste
   bate com o esperado (`/api/estoque/baixo`, painel de produtos).
4. **Painel**: login no painel administrativo, dashboard carrega números
   coerentes, sessão expira/renova como esperado.
5. **Backup**: confirmar que o primeiro backup agendado após o deploy roda
   sem erro (`/api/admin/backup/status`).
6. **Logs**: revisar logs de erro/autenticação das primeiras horas em busca
   de padrões anormais (tentativas de login repetidas, exceções não
   tratadas).
7. **Alertas**: confirmar que o monitor externo de uptime
   (UptimeRobot/Better Uptime, ver `BACKUP_MONITORAMENTO_DEPLOY.md`) está
   verde e que `.github/workflows/healthcheck.yml` não abriu issue de API
   fora do ar.

## Rollback

### Quando fazer rollback

- `health/ready` não estabiliza em `200` nos primeiros minutos após deploy.
- Erros 5xx anormais na primeira hora, muito acima do baseline.
- Regressão funcional confirmada na compra/Pix teste pós-deploy.
- Corrupção ou inacessibilidade do banco detectada logo após o deploy.

### Como fazer

- **Rollback de código**: Render → Deploys → escolher o deploy anterior
  saudável → **Rollback to this deploy** (ou reverter o commit em `main` e
  deixar o `autoDeploy` disparar um novo deploy corrigido).
- **Rollback de banco** (só se o problema for de dado, não só de código):
  usar `scripts/restaurar_backup.py --rollback --confirmar` se o problema
  apareceu logo após um restore recente, ou
  `scripts/restaurar_backup.py --arquivo <backup_anterior_ao_incidente> --confirmar`
  para voltar a um snapshot conhecido bom. Sempre validar em dry-run
  primeiro (sem `--confirmar`).
- **Comunicação**: registrar o incidente (issue no GitHub ou canal
  operacional interno) com horário, sintoma, ação tomada e resultado —
  mesmo que resolvido rapidamente, para alimentar a auditoria periódica.

## Incidentes

| Cenário | Ação imediata |
|---|---|
| API fora do ar | Checar `/api/health/live`; se nem isso responde, checar status do Render (build falhou, crash loop). Ver logs de `startup_concluido`. |
| Banco corrompido | `PRAGMA integrity_check` via `/api/diagnostico/sistema` (autenticado) ou script local; se falhar, restaurar do último backup íntegro com `scripts/restaurar_backup.py`. |
| Backup falhou | Ver `ultimo_erro` em `/api/admin/backup/status`; rodar `POST /api/backup/manual` manualmente enquanto a causa raiz (espaço em disco, permissão) é corrigida. |
| Pix pago sem pedido | Conferir logs do webhook Pix e `tests/test_pagamento_conciliacao.py`; reconciliar manualmente via painel antes de estornar no Mercado Pago. |
| Pedido duplicado | Checar `tests/test_checkout_concurrency.py`/`test_order_tracking_idempotency.py` — o fluxo já é idempotente por `Idempotency-Key`; duplicidade indica cliente/integração não enviando a chave, não falha do servidor. |
| Estoque incorreto | Consultar `movimentacao_estoque` para reconstruir o histórico do produto afetado antes de qualquer ajuste manual. |
| Login indisponível | Checar `painel_login_tentativas` (bloqueio por rate limit) e `/api/health/ready` (banco acessível). |
| Disco cheio | `/api/diagnostico/sistema` reporta `classificacao: "critico"`; liberar espaço (backups antigos além da retenção) ou aumentar o disco no Render antes que escritas comecem a falhar. |

## Observações sobre o que este runbook cobre

Este runbook descreve o **procedimento operacional**. Ele não substitui a
execução real de carga/Lighthouse/Playwright completos antes de um go-live —
ver `docs/CHECKLIST_GO_LIVE_FASE_C.md` para o que foi efetivamente executado
nesta auditoria e o que ainda precisa ser rodado manualmente antes da
liberação final.
