# Backup, monitoramento e deploy/rollback

Este documento cobre a operação contínua da Fase 5 (qualidade contínua) que
depende de infraestrutura externa ou de decisão manual: monitoramento com
alerta, backup automático fora do servidor e rollback de deploy.

## Backup automático fora do Render

O disco do Render (plano free) não é persistente entre deploys/reinícios, então
um backup salvo apenas em `BACKUP_DIR` no próprio servidor pode ser perdido.
Para ter uma cópia fora do servidor, foi criado:

- `GET /api/backup/download` (protegido por `X-Mistica-Api-Key`): gera uma
  cópia fresca do banco (`config.DB_PATH`) e devolve o arquivo `.db` para
  download.
- `.github/workflows/backup-diario.yml`: roda todo dia, chama esse endpoint e
  guarda o arquivo como *artifact* do GitHub Actions (retenção de 30 dias).

### Configuração necessária (uma vez)

1. No repositório GitHub, vá em **Settings → Secrets and variables → Actions**.
2. Adicione o secret `MISTICA_SITE_API_KEY` com o mesmo valor configurado no
   Render como `MISTICA_SITE_API_KEY` (ou `MISTICA_SYNC_KEY`).
3. Opcional: adicione a variável `MISTICA_API_URL` se a URL da API não for
   `https://api.misticaesotericos.com.br`.

### Como restaurar um backup

1. Baixe o artifact mais recente em **Actions → Backup diário do banco →
   (execução) → Artifacts**.
2. Pare a API (ou coloque em manutenção).
3. Substitua o arquivo apontado por `DB_PATH` pelo `.db` baixado.
4. Reinicie a API e confira `/api/status`.

## Monitoramento e alertas (UptimeRobot / Better Uptime)

A decisão foi usar um serviço externo gratuito de uptime, então a configuração
final precisa ser feita manualmente por quem tem acesso à conta de e-mail/
WhatsApp que deve receber o alerta. Passo a passo:

1. Crie uma conta gratuita em [UptimeRobot](https://uptimerobot.com/) ou
   [Better Uptime](https://betteruptime.com/).
2. Crie um monitor **HTTP(s)** para o site público:
   `https://www.misticaesotericos.com.br/` — esperado `200`.
3. Crie um segundo monitor para a API:
   `https://api.misticaesotericos.com.br/api/health` — esperado `200` e
   corpo contendo `"status":"online"`.
4. Configure o intervalo de checagem (5 min no plano gratuito é o normal).
5. Configure o canal de alerta (e-mail e, se disponível no plano, WhatsApp/SMS).
6. Guarde o link do status público (opcional) para compartilhar com a equipe.

Como reforço dentro do próprio repositório, existe também
`.github/workflows/healthcheck.yml`: roda a cada 15 minutos, chama
`/api/health`, e se a API não responder `200` abre (ou reaproveita) uma issue
`🔴 API fora do ar` no GitHub. Quando a API volta a responder, a issue é
fechada automaticamente na próxima execução. Isso é um reforço, não substitui
o UptimeRobot — o GitHub Actions pode atrasar minutos para rodar e não avisa
por e-mail/WhatsApp por padrão.

## Deploy e rollback manual

O deploy continua automático e direto a partir de `main`:

- **Site estático (GitHub Pages)**: workflow `deploy-pages.yml`, publica a
  cada push em `main` depois de validar os arquivos essenciais.
- **API (Render)**: `render.yaml` com `autoDeploy: true` — todo push em
  `main` dispara um novo deploy.

Não há ambiente de homologação separado hoje. Se um deploy quebrar algo em
produção, o rollback é manual:

### Rollback do site (GitHub Pages)

1. Acesse **Actions → Publicar site no GitHub Pages**.
2. Encontre a última execução **boa** (antes da mudança problemática).
3. Clique em **Re-run all jobs** nessa execução antiga — isso publica de novo
   o conteúdo daquele commit no GitHub Pages.
4. Alternativa: `git revert <commit-problemático>` e dar push em `main`, o
   que aciona um novo deploy automático já corrigido.

### Rollback da API (Render)

1. No painel do Render, abra o serviço `misticapresentes-api`.
2. Vá em **Events** ou **Deploys**.
3. Encontre o deploy anterior que estava saudável.
4. Use a opção **Rollback to this deploy** (ou **Redeploy**) desse item.
5. Confirme com `GET /api/health` que a versão voltou a responder.

Se o problema exigir também restaurar dados (não só código), siga a seção de
restauração de backup acima antes de liberar o acesso normal.
