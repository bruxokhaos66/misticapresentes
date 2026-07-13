# Variáveis de ambiente — API (`backend/main.py`)

Mapeamento de todas as variáveis lidas pelo backend em produção (`backend/`, `database/`, `config.py`). Nunca coloque valores reais neste documento nem no repositório — só em `Environment` no Render (ou equivalente).

## Obrigatórias em produção

| Variável | Descrição | Exemplo |
|---|---|---|
| `APP_ENV` | Ambiente de execução. Controla CORS e o campo `ambiente` de `/api/health` e `/api/version`. | `production` |
| `MISTICA_DB_PATH` | Caminho do arquivo SQLite dentro do disco persistente montado (ver `render.yaml`). Sem ela, o banco cai em `~/Documents`, que é **efêmero** em produção. | `/data/mistica_gestao_v20.db` |
| `MISTICA_SITE_API_KEY` | Chave usada pelo site e integrações servidor-a-servidor para gravar/ler dados protegidos da API (produtos, vendas, clientes, backup, diagnóstico). | `chave-longa-aleatoria` |
| `MISTICA_ADMIN_PASSWORD` | Senha do usuário `admin` criado/redefinido automaticamente no startup. Sem ela, nenhum admin automático é criado. | `senha-forte-aleatoria` |
| `MISTICA_PIX_KEY` | Chave Pix usada para gerar o payload de cobrança no checkout. | `chave-pix-da-loja` |

## Opcionais em produção (têm padrão seguro)

| Variável | Descrição | Obrigatória | Exemplo |
|---|---|---|---|
| `MISTICA_SYNC_KEY` | Fallback legado de `MISTICA_SITE_API_KEY` (aceito nas mesmas rotas). | Não | `chave-legada` |
| `DATABASE_PATH` | Alias legado de `MISTICA_DB_PATH` (mesma função). | Não | `/data/mistica_gestao_v20.db` |
| `DATABASE_URL` | Reservada para uma futura migração para PostgreSQL. Hoje não altera o SQLite. | Não | *(vazio)* |
| `MISTICA_LOG_LEVEL` | Nível do logging estruturado em JSON. | Não | `INFO` |
| `MISTICA_PIX_NOME` | Nome do recebedor no payload Pix. Padrão: `MISTICA PRESENTES`. | Não | `MISTICA PRESENTES` |
| `MISTICA_PIX_CIDADE` | Cidade do recebedor no payload Pix. Padrão: `PINHALZINHO`. | Não | `PINHALZINHO` |
| `MISTICA_PIX_WEBHOOK_SECRET` | Segredo para validar o webhook de confirmação de pagamento Pix. | Recomendada | `segredo-webhook` |
| `MISTICA_MINUTOS_EXPIRACAO_PEDIDO` | Minutos até um pedido "Aguardando pagamento" expirar e repor estoque. Padrão: `30`. | Não | `30` |
| `MISTICA_LOGIN_WINDOW_MINUTES` | Janela (minutos) de contagem de tentativas de login do painel. Padrão: `10`. | Não | `10` |
| `MISTICA_LOGIN_MAX_ATTEMPTS` | Tentativas de login permitidas na janela acima antes de atrasar/bloquear. Padrão: `5`. | Não | `5` |
| `MISTICA_LOGIN_MAX_DELAY_SECONDS` | Atraso máximo (segundos) aplicado a tentativas de login repetidas. Padrão: `2`. | Não | `2` |
| `MISTICA_DEFAULT_PANEL_PASSWORD` | Senha padrão usada ao sincronizar um novo usuário do painel sem senha definida. | Não | `senha-temporaria` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON da conta de serviço do Google usada para upload no Google Drive (cursos/músicas). Sem ela, o upload cai automaticamente para armazenamento local em disco. | Não | `{"type": "service_account", ...}` |
| `GOOGLE_DRIVE_FOLDER_CURSOS` | ID da pasta do Google Drive para materiais de curso, quando `GOOGLE_SERVICE_ACCOUNT_JSON` está configurada. | Não | `1AbCdEfGhIjKlMnOpQrSt` |
| `GOOGLE_DRIVE_FOLDER_MUSICAS` | ID da pasta do Google Drive para músicas de ambiente, quando `GOOGLE_SERVICE_ACCOUNT_JSON` está configurada. | Não | `1XyZ9876543210AbCdEf` |
| `RENDER_GIT_COMMIT` | Preenchida automaticamente pelo Render com o commit do deploy atual; exposta (truncada) em `/api/version`. | Não (automática) | `a1b2c3d4e5f6` |
| `MISTICA_BUILD_DATE` | Data do build, exposta em `/api/version`, se você quiser rastrear manualmente. | Não | `2026-07-13` |
| `MISTICA_RELEASE` | Identificador de release exposto em `/api/version`. Sem ela, usa a versão declarada em `backend/main.py`. | Não | `release-2026.07.1` |

## Apenas desenvolvimento/rede local (`api/main.py`, `MisticaLauncher.py`)

Estas variáveis controlam a API local usada na loja física (rede interna) e o app desktop — não são usadas pela API pública do site.

| Variável | Descrição | Exemplo |
|---|---|---|
| `MISTICA_API_TOKEN` | Token da API local (rede da loja/painel mobile). | `token-rede-local` |
| `MISTICA_ALLOWED_ORIGINS` | Origens CORS permitidas para a API local, separadas por vírgula. | `http://localhost,http://127.0.0.1` |
| `MISTICA_SERVER_PORT` | Porta da API local quando executada fora do Render. | `8000` |
| `MISTICA_PASSWORD_SALT` | Sal usado para hash de senha em ferramentas locais/desktop. | `sal-aleatorio` |

## Como configurar no Render

Vá em **Environment** no serviço `misticapresentes-api` e cadastre cada chave acima com o valor real (nunca no `.env.example` nem em commits). Veja `.env.example` neste repositório para o formato de referência (sem valores reais) e `render.yaml` para as variáveis já declaradas como parte do serviço.
