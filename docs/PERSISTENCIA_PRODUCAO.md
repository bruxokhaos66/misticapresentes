# Persistência em produção — arquitetura, deploy, rollback e checklist

Auditoria da Fase 1 (PR 4) sobre como o banco de dados da API (`backend.main:app`, deployado no Render conforme `render.yaml`) sobrevive a redeploys, reinícios e troca de instância. Complementa `docs/API_SQLITE_PERSISTENTE.md` (guia de configuração passo a passo) e `docs/BACKUP_SQLITE_CONSISTENTE.md` (backup/restauração consistentes).

## 1. Onde o banco vive hoje

- O banco é SQLite, aberto em `database/connection.py` e `backend/database.py`, sempre a partir de `config.DB_PATH`.
- `config.carregar_db_path()` prioriza, nesta ordem: `MISTICA_DB_PATH` → `DATABASE_PATH` → um caminho salvo em `mistica_config_rede.json` → o padrão `~/Documents/mistica_gestao_v20.db` (pensado para o app desktop, **efêmero** em qualquer host de nuvem).
- `render.yaml` já declara um **Persistent Disk** (`disk: name: mistica-dados, mountPath: /data, sizeGB: 1`) e define `MISTICA_DB_PATH=/data/mistica_gestao_v20.db` como variável do serviço, exigindo o plano `starter` (planos `free` do Render não suportam disco persistente).
- No startup (`backend/main.py::_verificar_persistencia_banco`, chamada pelo `lifespan`), a aplicação confere se `MISTICA_DB_PATH`/`DATABASE_PATH` está definida **e** aponta para um prefixo típico de disco montado (`/data`, `/var/data`, `/mnt`) e registra um log (`INFO` se parece persistente, `WARNING` caso contrário) — o log nunca inclui o caminho nem o diretório, só o booleano `persistente`.

## 2. Classificação da persistência: o que está confirmado vs. o que ainda exige verificação no Render real

Esta auditoria é sobre o **repositório** (código e configuração versionada). Ela não tem acesso ao painel do Render nem ao serviço implantado, então a afirmação de que "o banco sobrevive" é dividida em duas categorias, e nenhuma delas deve ser lida como a outra:

### CONFIGURAÇÃO DO REPOSITÓRIO COMPATÍVEL COM PERSISTÊNCIA (confirmado por código/config versionados)

- `render.yaml` declara um `disk` (`mistica-dados`, `mountPath: /data`, `sizeGB: 1`) no serviço `misticapresentes-api`.
- `render.yaml` declara `MISTICA_DB_PATH=/data/mistica_gestao_v20.db` como `envVars` do mesmo serviço.
- `config.carregar_db_path()` prioriza `MISTICA_DB_PATH` (e `DATABASE_PATH`) antes de qualquer caminho efêmero.
- `database/migrations.py::init_db()` só cria/altera schema (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN` tolerante), nunca apaga tabelas ou dados existentes.
- O backup usa `Connection.backup()` (não cópia de arquivo), seguro mesmo com o banco em `WAL` (ver `docs/BACKUP_SQLITE_CONSISTENTE.md`).

**Isso comprova que, se o serviço realmente implantado usar este `render.yaml` como Blueprint e este código, a persistência está corretamente configurada.** Isso **não** comprova, por si só, que o serviço em produção está de fato configurado assim hoje.

### AINDA EXIGE CONFIRMAÇÃO NO PAINEL/PRODUÇÃO (não verificável a partir do repositório)

- Que o serviço implantado no Render está de fato usando o Blueprint (`render.yaml`) atual, e não uma configuração manual antiga/divergente criada antes dele existir.
- Que o disco `mistica-dados` está realmente provisionado e anexado ao serviço (o Render permite remover ou desanexar um disco pelo painel sem que isso apareça no repositório).
- Que o plano ativo do serviço é `starter` ou superior (um downgrade para `free` no painel não é visível aqui).
- Que a variável `MISTICA_DB_PATH` está de fato presente no serviço real, com o valor esperado (alguém pode ter editado/removido pelo painel).
- Que o deploy atualmente ativo está realmente lendo e escrevendo em `/data` (só é confirmável observando `GET /api/health` e os logs do serviço real).
- Que os dados sobrevivem a um **redeploy real** (só é confirmável executando o roteiro da seção 7 no ambiente de homologação/produção, com autorização).
- Que existem backups armazenados **fora** da mesma instância/disco (hoje, os backups gerados por `/api/backup/manual` e `/api/backup/download` ficam no mesmo host; não há confirmação de cópia externa).

**Conclusão desta auditoria:** a configuração versionada no repositório é **compatível com persistência real** (não há lacuna de código a corrigir), mas a afirmação "o banco sobrevive em produção" só pode ser dada como comprovada depois de uma verificação no serviço real (painel do Render + o roteiro da seção 7). Por isso nenhuma mudança de infraestrutura foi feita nesta auditoria — o achado é de verificação operacional pendente, não de código a corrigir.

## 3. Observabilidade adicionada nesta auditoria

- `GET /api/health` — resposta mínima e fixa, pensada para consumo por monitores automáticos:
  ```json
  {"status": "ok", "service": "mistica-api", "version": "0.3.8", "database": "available"}
  ```
  Quando o banco ou a pasta do banco não está acessível, responde **HTTP 503** com `{"status": "error", "service": "mistica-api", "version": "...", "database": "unavailable"}` — nunca com o motivo detalhado, caminho ou stack trace. A checagem de disco usada aqui é só leitura de permissão (`os.access`), sem criar/remover arquivo a cada chamada, para não gerar I/O repetido a partir de monitores externos de alta frequência.
- `GET /api/version` — retorna só `app`, `version`, `build` (identificador curto e sanitizado, de `MISTICA_BUILD_ID` ou `RENDER_GIT_COMMIT`, nunca branch/usuário/URL) e `release_date` (de `MISTICA_BUILD_DATE`, opcional). Nenhum comando Git é executado por requisição.
- `GET /api/diagnostico/sistema` (autenticado, já existia) — a autenticação é verificada **antes** de qualquer checagem de banco/disco; sem chave válida, a resposta é só o erro genérico de autenticação. Com chave válida, retorna `banco: {acessivel, arquivo_existe, pasta_existe}` (sem caminho absoluto — o campo `caminho` foi removido nesta auditoria) e `disco: {acessivel, escrita_ok, escrita_motivo, classificacao, espaco_livre_percentual, espaco_livre_bytes, espaco_total_bytes}`, com `classificacao` em `"saudavel"`/`"atencao"`/`"critico"` conforme limiares configuráveis (`MISTICA_DISCO_LIMIAR_ATENCAO_PERCENT`, `MISTICA_DISCO_LIMIAR_CRITICO_PERCENT`, padrão `20`/`10`). Erros de leitura de tabela são logados internamente (`logger.exception`, sem chegar à resposta) e sinalizados só como `teve_erro: true`.
- `backend/infra_diagnostics.py` (novo) — concentra as checagens seguras: `banco_acessivel` (leitura simples), `disco_diretorio_disponivel` (checagem leve, sem escrita, usada pelo `/api/health` público), `escrita_disco_segura` (teste real de criação/remoção de arquivo, com defesa contra symlink/traversal, usado só pelo diagnóstico autenticado), `espaco_disco_bytes` e `classificar_espaco_livre`.
- Log de startup — `_verificar_persistencia_banco` (nível `INFO`/`WARNING`, sem caminho) e uma nova linha `INFO "inicializacao concluida"` em `lifespan` com `versao`, `ambiente`, `banco_ok`, `disco_ok` e `duracao_ms` — nenhum dos dois inclui caminho absoluto, variável de ambiente, segredo ou stack trace (coberto por `tests/test_logs_startup_sanitizados.py`).

## 4. Procedimento de deploy

1. Merge na `main` dispara `autoDeploy: true` no Render (serviço `misticapresentes-api`).
2. O Render executa `pip install -r requirements.txt` e sobe `uvicorn backend.main:app`.
3. No `lifespan`, `init_db()` roda as migrações idempotentes (`database/migrations.py`) contra o arquivo em `/data/mistica_gestao_v20.db` — nenhuma tabela existente é apagada; apenas `CREATE TABLE IF NOT EXISTS` e `ALTER TABLE ADD COLUMN` tolerantes a coluna já existente.
4. Confirme o deploy com `GET /api/health` (deve responder HTTP 200 e `"status": "ok"`) e `GET /api/version` (deve refletir o `build` esperado).
5. Se `GET /api/health` responder **HTTP 503**, **não considere o deploy concluído** — verifique os logs de startup (`evento: startup_persistencia` e `evento: startup_concluido`) antes de liberar tráfego/anunciar a atualização.

## 5. Procedimento de rollback

1. No painel do Render, use **Deploys → selecionar o deploy anterior → Rollback** (ou reverta o commit na `main` e deixe o `autoDeploy` disparar).
2. O rollback troca apenas o código/processo; o Persistent Disk (`/data`) **não é recriado nem revertido** — os dados gravados pela versão mais nova continuam no banco após o rollback de código (a confirmar na prática conforme a seção 2).
3. Se o rollback for necessário por uma migração de schema problemática, avalie se a migração é compatível com versões anteriores do código antes de reverter (migrações em `database/migrations.py` só adicionam colunas/tabelas, nunca removem, então isso normalmente não é um problema).
4. Confirme com `GET /api/version` que o `build` retornou ao esperado.

## 6. Procedimento de restauração (a partir de backup)

Ver `docs/BACKUP_SQLITE_CONSISTENTE.md` para o mecanismo completo de backup/restauração (usa `Connection.backup()`, não cópia de arquivo, e valida `PRAGMA integrity_check` antes de aceitar qualquer snapshot). Resumo operacional:

1. Baixe o snapshot mais recente via `GET /api/backup/download` (autenticado) ou localize o mais recente listado em `GET /api/backup/status`.
2. Confira o checksum SHA-256 (header `X-Backup-Checksum-Sha256` ou arquivo `.sha256` ao lado do backup local).
3. Pare o serviço (ou coloque em manutenção), substitua o arquivo em `/data/mistica_gestao_v20.db` pelo snapshot validado, reinicie o serviço.
4. Confirme com `GET /api/diagnostico/sistema` (autenticado) que `teve_erro` é `false` e as tabelas batem com o esperado antes de liberar tráfego.

## 7. Roteiro manual de homologação (teste de sobrevivência operacional)

**Não deve ser executado em produção automaticamente por este PR.** É um roteiro para ser seguido manualmente, com autorização explícita, no ambiente de homologação (ou em produção em janela controlada), para transformar a classificação da seção 2 de "compatível" em "confirmado no serviço real":

1. Consultar `GET /api/version` e anotar o `build` atual.
2. Criar um registro fictício claramente identificável (ex.: um cliente de teste com nome `TESTE-PERSISTENCIA-<data>`), usando a API autenticada.
3. Confirmar que o registro foi persistido (consultar de volta pela API).
4. Gerar um backup manual (`POST /api/backup/manual`) e guardá-lo fora da instância (download local).
5. Realizar um redeploy controlado (ex.: um commit vazio ou "Manual Deploy" no painel do Render).
6. Consultar novamente o registro fictício criado no passo 2.
7. Verificar que o identificador (`id`) do registro é o mesmo de antes do redeploy (não um registro novo com dados coincidentes).
8. Validar que o backup baixado no passo 4 abre e passa em `PRAGMA integrity_check` como arquivo separado (fora da instância).
9. Remover o registro fictício de forma auditada (log/anotação de quem removeu e quando), confirmando que a remoção não afetou dados reais.

Só depois de concluir este roteiro no serviço real é que a persistência em produção pode ser classificada como **confirmada**, não apenas **compatível pela configuração do repositório**.

## 8. Requisitos para produção

- Plano do serviço Render: `starter` ou superior (obrigatório para Persistent Disk) — **a confirmar no painel**, ver seção 2.
- Variáveis obrigatórias configuradas no painel do Render: ver `docs/VARIAVEIS_AMBIENTE.md`.
- Disco (`mistica-dados`) montado em `/data` com espaço suficiente (`sizeGB: 1` hoje) — acompanhar `classificacao` (`saudavel`/`atencao`/`critico`) de `/api/diagnostico/sistema` conforme o volume de dados cresce.
- Backups periódicos: hoje são manuais/sob demanda via `/api/backup/manual`, armazenados na mesma instância. Para produção comercial recorrente, ver a pendência registrada na seção 9 (fora do escopo deste PR).

## 9. Pendência registrada (fora do escopo deste PR)

Backup automático recorrente com armazenamento **externo** à instância (cron externo ou GitHub Action chamando `POST /api/backup/manual` e enviando o resultado para um destino fora do Render) não foi implementado aqui — exige desenho próprio para segredo de autenticação do cron, retenção, custo de armazenamento externo, notificação de falha e proteção contra criação excessiva de backups. Deve ser tratado como issue/PR separado, não incluído nesta auditoria de persistência.

## 10. Checklist operacional

- [ ] `GET /api/health` responde HTTP 200 com `"status": "ok"` e `"database": "available"`.
- [ ] `GET /api/version` reflete o `build` esperado do deploy.
- [ ] Log de startup mostra `evento: startup_persistencia, persistente: true`.
- [ ] Log de startup mostra `evento: startup_concluido` com `banco_ok: true, disco_ok: true`.
- [ ] `GET /api/diagnostico/sistema` (autenticado) mostra `teve_erro: false`, tabelas principais com contagens condizentes com o esperado (não zeradas após um deploy) e `disco.classificacao` diferente de `"critico"`.
- [ ] Plano do serviço no Render confirmado como `starter` ou superior (verificação manual no painel).
- [ ] `MISTICA_DB_PATH` confirmada no painel do Render, apontando para `/data/...` (verificação manual).
- [ ] Backup manual recente disponível (`GET /api/backup/status`).
- [ ] Roteiro da seção 7 executado ao menos uma vez em homologação/produção controlada, com resultado registrado.
