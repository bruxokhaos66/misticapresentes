# Persistência em produção — arquitetura, deploy, rollback e checklist

Auditoria da Fase 1 (PR 4) sobre como o banco de dados da API (`backend.main:app`, deployado no Render conforme `render.yaml`) sobrevive a redeploys, reinícios e troca de instância. Complementa `docs/API_SQLITE_PERSISTENTE.md` (guia de configuração passo a passo) e `docs/BACKUP_SQLITE_CONSISTENTE.md` (backup/restauração consistentes).

## 1. Onde o banco vive hoje

- O banco é SQLite, aberto em `database/connection.py` e `backend/database.py`, sempre a partir de `config.DB_PATH`.
- `config.carregar_db_path()` prioriza, nesta ordem: `MISTICA_DB_PATH` → `DATABASE_PATH` → um caminho salvo em `mistica_config_rede.json` → o padrão `~/Documents/mistica_gestao_v20.db` (pensado para o app desktop, **efêmero** em qualquer host de nuvem).
- `render.yaml` já declara um **Persistent Disk** (`disk: name: mistica-dados, mountPath: /data, sizeGB: 1`) e define `MISTICA_DB_PATH=/data/mistica_gestao_v20.db` como variável do serviço, exigindo o plano `starter` (planos `free` do Render não suportam disco persistente).
- No startup (`backend/main.py::_verificar_persistencia_banco`, chamada pelo `lifespan`), a aplicação confere se `MISTICA_DB_PATH`/`DATABASE_PATH` está definida **e** aponta para um prefixo típico de disco montado (`/data`, `/var/data`, `/mnt`) e registra um log de alerta (`WARNING`) se não estiver — sem nunca logar o caminho completo, só o diretório.

## 2. O banco realmente sobrevive?

Com a configuração atual do repositório (`render.yaml` com `disk` + `MISTICA_DB_PATH=/data/...` no plano `starter`):

| Cenário | Sobrevive? | Por quê |
|---|---|---|
| Redeploy (novo build/release) | **Sim** | O Persistent Disk é remontado no mesmo `mountPath` para o novo processo; o arquivo `.db` não faz parte da imagem de build. |
| Restart/crash do processo | **Sim** | O disco não é recriado; o SQLite reabre o mesmo arquivo (`WAL` consolidado via `PRAGMA journal_mode=WAL` + `Connection.backup()` nos backups, ver `docs/BACKUP_SQLITE_CONSISTENTE.md`). |
| Troca de instância/host (o Render pode mover o serviço para outra máquina) | **Sim, dentro do mesmo serviço** | O Persistent Disk do Render é uma entidade de rede associada ao serviço, não ao container/host específico — ele é remontado onde o serviço rodar. |
| Downgrade do serviço para o plano `free` | **Não** | O plano `free` do Render não oferece Persistent Disk; o filesystem volta a ser efêmero e o próximo redeploy/sleep apaga o banco. Isto está documentado como comentário de alerta no próprio `render.yaml`. |
| `MISTICA_DB_PATH` removida/alterada por engano no painel do Render | **Não** | `carregar_db_path()` cai de volta em `~/Documents`, efêmero no host de nuvem. O log de startup emite `WARNING "banco pode estar em disco EFEMERO"` para isso ser detectável nos logs do Render antes de virar perda de pedidos. |

**Conclusão objetiva:** com a configuração já versionada em `render.yaml`, o banco **é persistente** nos três cenários mais comuns (redeploy, restart, troca de instância), condicionado a manter o serviço no plano `starter` (ou superior) e a variável `MISTICA_DB_PATH` intacta. O único risco real remanescente é operacional/humano: alguém alterar o plano ou remover a variável de ambiente pelo painel do Render sem revisar este documento. Nenhuma mudança de infraestrutura foi necessária nesta auditoria — o item 1 do escopo pede para **não alterar produção quando não há risco de código**, e não havia.

## 3. Observabilidade adicionada nesta auditoria

- `GET /api/health` — agora informa `status`, `app`, `version`, `ambiente`, `uptime_segundos`, `banco_acessivel` e `disco_acessivel` (booleans), sem caminhos, variáveis ou stack trace. Fica `status: "degradado"` (ainda com HTTP 200, para não quebrar monitores como UptimeRobot) quando banco ou disco falham a verificação ativa.
- `GET /api/version` — agora informa `commit` (de `RENDER_GIT_COMMIT`, truncado), `ambiente`, `build_data` e `release`, além de `app`/`version` já existentes.
- `GET /api/diagnostico/sistema` (autenticado, já existia) — passou a incluir `disco: {acessivel, espaco_livre_bytes, espaco_total_bytes, espaco_usado_bytes}`, calculados por `shutil.disk_usage`, sem novas exposições de caminho (o campo `banco.caminho` já existia e continua restrito a quem tem a chave de API administrativa).
- `backend/infra_diagnostics.py` (novo) — funções puras e seguras (`banco_acessivel`, `disco_acessivel`, `espaco_disco_bytes`) reaproveitadas pelos três endpoints acima, sem duplicar lógica de checagem de banco/disco.
- Log de startup — `backend/main.py::lifespan` agora emite uma linha `INFO "inicializacao concluida"` com `versao`, `ambiente`, `banco_ok`, `disco_ok` e `duracao_ms`, além do `WARNING` de persistência que já existia.

## 4. Procedimento de deploy

1. Merge na `main` dispara `autoDeploy: true` no Render (serviço `misticapresentes-api`).
2. O Render executa `pip install -r requirements.txt` e sobe `uvicorn backend.main:app`.
3. No `lifespan`, `init_db()` roda as migrações idempotentes (`database/migrations.py`) contra o arquivo em `/data/mistica_gestao_v20.db` — nenhuma tabela existente é apagada; apenas `CREATE TABLE IF NOT EXISTS` e `ALTER TABLE ADD COLUMN` tolerantes a coluna já existente.
4. Confirme o deploy com `GET /api/health` (deve responder `"status": "online"`) e `GET /api/version` (deve refletir o novo `commit`).
5. Se `GET /api/health` responder `"status": "degradado"`, **não considere o deploy concluído** — verifique os logs de startup (`evento: startup_persistencia` e `evento: startup_concluido`) antes de liberar tráfego/anunciar a atualização.

## 5. Procedimento de rollback

1. No painel do Render, use **Deploys → selecionar o deploy anterior → Rollback** (ou reverta o commit na `main` e deixe o `autoDeploy` disparar).
2. O rollback troca apenas o código/processo; o Persistent Disk (`/data`) **não é recriado nem revertido** — os dados gravados pela versão mais nova continuam no banco após o rollback de código.
3. Se o rollback for necessário por uma migração de schema problemática, avalie se a migração é compatível com versões anteriores do código antes de reverter (migrações em `database/migrations.py` só adicionam colunas/tabelas, nunca removem, então isso normalmente não é um problema).
4. Confirme com `GET /api/version` que o `commit`/`version` retornou ao esperado.

## 6. Procedimento de restauração (a partir de backup)

Ver `docs/BACKUP_SQLITE_CONSISTENTE.md` para o mecanismo completo de backup/restauração (usa `Connection.backup()`, não cópia de arquivo, e valida `PRAGMA integrity_check` antes de aceitar qualquer snapshot). Resumo operacional:

1. Baixe o snapshot mais recente via `GET /api/backup/download` (autenticado) ou localize o mais recente listado em `GET /api/backup/status`.
2. Confira o checksum SHA-256 (header `X-Backup-Checksum-Sha256` ou arquivo `.sha256` ao lado do backup local).
3. Pare o serviço (ou coloque em manutenção), substitua o arquivo em `/data/mistica_gestao_v20.db` pelo snapshot validado, reinicie o serviço.
4. Confirme com `GET /api/diagnostico/sistema` (autenticado) que as contagens de tabelas batem com o esperado antes de liberar tráfego.

## 7. Requisitos para produção

- Plano do serviço Render: `starter` ou superior (obrigatório para Persistent Disk).
- Variáveis obrigatórias configuradas no painel do Render: ver `docs/VARIAVEIS_AMBIENTE.md`.
- Disco (`mistica-dados`) montado em `/data` com espaço suficiente (`sizeGB: 1` hoje; acompanhar `espaco_livre_bytes` de `/api/diagnostico/sistema` conforme o volume de dados cresce).
- Backups periódicos: hoje são manuais/sob demanda via `/api/backup/manual`; para produção comercial recorrente, agende uma chamada periódica (cron externo ou GitHub Actions) para esse endpoint.

## 8. Checklist operacional

- [ ] `GET /api/health` responde `"status": "online"` (banco e disco acessíveis).
- [ ] `GET /api/version` reflete o commit esperado do deploy.
- [ ] Log de startup mostra `evento: startup_persistencia, persistente: true`.
- [ ] Log de startup mostra `evento: startup_concluido` com `banco_ok: true, disco_ok: true`.
- [ ] `GET /api/diagnostico/sistema` (autenticado) mostra as tabelas principais com contagens condizentes com o esperado (não zeradas após um deploy).
- [ ] Plano do serviço no Render continua `starter` ou superior.
- [ ] `MISTICA_DB_PATH` continua configurada e apontando para `/data/...` no painel do Render.
- [ ] Backup manual recente disponível (`GET /api/backup/status`).
