# Checklist de Go Live — Fase C

Classificação de cada item conforme evidência encontrada nesta auditoria
(código, testes existentes/novos e documentação). `APROVADO COM RISCO`
significa que funciona, mas com uma limitação conhecida e aceitável para o
estágio atual do negócio. `BLOQUEADOR` significa que não deve vender sem
corrigir primeiro.

| Item | Classificação | Evidência / observação |
|---|---|---|
| Domínio (API + site) | APROVADO | `OFFICIAL_DOMAIN`/`API_URL`/`SERVER_URL` centralizados em `config.py`; sem hostname hardcoded solto em `backend/`. |
| HTTPS | APROVADO | HSTS enviado condicionalmente (`if request.url.scheme == "https"`), cookies `Secure` quando `request.url.scheme == "https"`. |
| Redirect HTTP→HTTPS | NÃO APLICÁVEL | Terminação TLS é feita pelo Render/GitHub Pages, fora do código da aplicação; não há servidor HTTP próprio para redirecionar. |
| CORS | APROVADO | `ORIGENS_PERMITIDAS` explícita por ambiente em `backend/api_security.py`, sem `*` em produção. |
| Cookies `Secure`/`HttpOnly` | APROVADO | `backend/panel_sessions.py` e `backend/aluno_auth.py` já setam `secure=` condicional ao esquema. |
| Headers de segurança (CSP, X-Content-Type-Options, Referrer-Policy, HSTS) | APROVADO COM RISCO | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS e `Cross-Origin-Resource-Policy` presentes (`backend/main.py::cabecalhos_seguranca`). **Falta CSP e `Permissions-Policy` explícitos** — não adicionados nesta fase por exigirem teste completo contra o site estático (risco de quebrar recursos externos, ex. fontes/CDN) fora do escopo desta auditoria de backend. Recomenda-se tratar em fase própria de front-end. |
| Workers/tarefas periódicas | APROVADO | `_expirar_pedidos_periodicamente` e `scheduler_backup` têm `try/except` por iteração (não morrem silenciosamente), backup usa lock exclusivo em disco (não duplica em múltiplos workers do mesmo host) e podem ser desligados via `BACKUP_ENABLED=false`. |
| Rate limiting | APROVADO COM RISCO | Login usa limite persistido em banco (`painel_login_tentativas`, sobrevive a restart/múltiplas instâncias). Demais rotas (`backend/rate_limit.py`) usam limite em memória — documentado explicitamente no próprio código como válido só para uma instância; consistente com o plano atual (`render.yaml`: um único serviço web). Se o serviço escalar para múltiplas instâncias, esse limite deixa de valer globalmente. |
| Banco de dados / persistência | APROVADO | `render.yaml` já declara `disk` montado em `/data` com `MISTICA_DB_PATH` apontando para ele, plano `starter` (disco pago funcional), e o startup loga explicitamente se o caminho não parecer persistente. |
| Backup | APROVADO | Backup automático diário com lock, checksum SHA-256, `PRAGMA integrity_check` antes de considerar válido, retenção configurável, réplica remota opcional (R2) desacoplada do backup local (falha remota não apaga nem invalida o local). |
| Restore / Disaster Recovery | APROVADO (após esta fase) | Antes desta auditoria não havia procedimento seguro de restore (só instrução manual de substituir o arquivo do banco). Adicionado `database/restore.py` + `scripts/restaurar_backup.py`: valida checksum/formato/integridade/tabelas essenciais numa cópia isolada, só então troca atomicamente e preserva o banco anterior para rollback. Coberto por 10 testes de regressão (`tests/test_restore_disaster_recovery.py`). |
| Health checks | APROVADO | `/api/health` (compatibilidade), `/api/health/live` (liveness) e `/api/health/ready` (readiness: banco acessível+gravável, migrations, disco) adicionados nesta fase, sem expor caminho/stacktrace. |
| Observabilidade / logs sanitizados | APROVADO | Logs de startup/erro já evitam caminho absoluto, stack trace ao público e segredos (`test_logs_startup_sanitizados.py`, `test_secrets_scan.py` pré-existentes). |
| Alertas | APROVADO COM RISCO | Monitoramento externo (UptimeRobot/Better Uptime) + workflow interno de healthcheck já documentados em `docs/admin/BACKUP_MONITORAMENTO_DEPLOY.md`. Não há alerta automatizado dedicado para "backup não executado" ou "fila de estornos pendente" além do que já existe no status administrativo — mitigação: checar manualmente `/api/admin/backup/status` no runbook pós-deploy. |
| Pagamento (Pix/Mercado Pago) | APROVADO COM RISCO | Idempotência e conciliação cobertas por testes pré-existentes (`test_pagamento_conciliacao.py`, `test_pagamento_tardio.py`). Dependência externa (Mercado Pago) sem timeout/retry configurado explicitamente nesta auditoria — ver seção de dependências externas do relatório final. |
| Pedido / estoque | APROVADO | Reserva/reposição atômica já coberta pela Fase B (PR #341) e testes de concorrência existentes. |
| Autenticação / sessão | APROVADO | Sessão por cookie HttpOnly, bloqueio de força bruta persistido em banco, expiração de sessão testada. |
| Painel administrativo | APROVADO | Protegido por sessão/chave de API; dashboard com `Cache-Control: no-store`. |
| Estorno via API não reflete `fluxo_caixa` (issue #335) | APROVADO COM RISCO | Não corrigido nesta fase (exige migração de schema, fora do escopo de produção/deploy). Risco é de **relatório financeiro impreciso**, não de perda de pedido/pagamento/estoque — não bloqueia vender. Ver triagem no relatório final. |
| Fechamento de caixa fora da transação final (issue #329) | APROVADO COM RISCO | Já documentado como janela de UX, não corrupção de dado; decisão de produto pendente, não bloqueia go-live. |
| Relatórios sem snapshot consistente (issue #336) | APROVADO COM RISCO | Afeta relatórios gerenciais (DRE), não a integridade transacional de venda/estoque/pagamento; não bloqueia vender. |
| Patches `str.replace` silenciosos (issue #337) | NÃO APLICÁVEL a este go-live | Afeta somente o build do instalador desktop Windows (`app_*_patch.py`), não a API/site em produção. |
| Performance (latência catálogo/checkout) | APROVADO COM RISCO | Sem regressão identificada nesta auditoria; carga moderada não executada nesta sessão (ver relatório final) — recomenda-se rodar antes do go-live definitivo. |
| SEO técnico / mobile | NÃO APLICÁVEL | Fora do escopo desta fase (produção/backend); já auditado em fases de front-end anteriores. |
| Rollback | APROVADO | Runbook (`docs/GO_LIVE_RUNBOOK_FASE_C.md`) cobre rollback de código (Render) e de banco (novo script de restore). |
| Operação diária | APROVADO | Runbook cobre checagens diárias mínimas (backup, health/ready, logs). |
