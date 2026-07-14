# Variáveis de ambiente — API (`backend/main.py`)

Mapeamento de todas as variáveis lidas pelo backend (`backend/`, `database/`, `config.py`) e pela API local de rede (`api/main.py`). Nunca coloque valores reais neste documento nem no repositório — só em `Environment` no Render (ou equivalente). Todos os exemplos abaixo são fictícios.

Colunas: **Finalidade**, **Obrigatória?**, **Ambiente aplicável**, **Exemplo fictício**, **Comportamento quando ausente**, **Contém dado sensível?**.

## Persistência do banco (críticas para não perder dados)

| Variável | Finalidade | Obrigatória? | Ambiente | Exemplo | Comportamento se ausente | Sensível? |
|---|---|---|---|---|---|---|
| `MISTICA_DB_PATH` | Caminho do arquivo SQLite dentro do disco persistente montado (ver `render.yaml`, `mountPath: /data`). | **Sim**, em produção (ou `DATABASE_PATH` como alternativa) | Produção | `/data/mistica_gestao_v20.db` | O banco cai em `~/Documents`, que é **efêmero** em qualquer host de nuvem — próximo redeploy/restart apaga todos os pedidos. `/api/health` reporta `database: "unavailable"`/`503` se o caminho resultante não puder ser aberto; o log de startup emite `WARNING` se o caminho não parecer um disco montado. | Não (é só um caminho de arquivo) |
| `DATABASE_PATH` | Alias legado de `MISTICA_DB_PATH` (mesma função, usado só se `MISTICA_DB_PATH` não estiver definida). | Não, exceto se `MISTICA_DB_PATH` também estiver ausente — nesse caso a ausência de **ambas** tem o mesmo efeito descrito acima. | Produção | `/data/mistica_gestao_v20.db` | Mesmo efeito de `MISTICA_DB_PATH` ausente, caso ela também não esteja definida. | Não |
| `DATABASE_URL` | Reservada para uma futura migração para PostgreSQL. Hoje **não** altera onde o SQLite grava. | Não | Todos | *(vazio)* | Nenhum efeito — o SQLite continua usando `MISTICA_DB_PATH`/`DATABASE_PATH`. | Não |
| `MISTICA_DISCO_LIMIAR_ATENCAO_PERCENT` | Percentual de espaço livre em disco abaixo do qual `/api/diagnostico/sistema` classifica como `"atencao"`. | Não (padrão `20`) | Produção | `20` | Usa o padrão conservador `20`. | Não |
| `MISTICA_DISCO_LIMIAR_CRITICO_PERCENT` | Percentual de espaço livre em disco abaixo do qual `/api/diagnostico/sistema` classifica como `"critico"`. | Não (padrão `10`) | Produção | `10` | Usa o padrão conservador `10`. | Não |

## Obrigatórias em produção (fora de persistência)

| Variável | Finalidade | Obrigatória? | Ambiente | Exemplo | Comportamento se ausente | Sensível? |
|---|---|---|---|---|---|---|
| `APP_ENV` | Ambiente de execução; controla a lista de origens CORS permitidas e o campo `ambiente` do log de startup (`evento: startup_concluido`). O valor é normalizado (espaços removidos, minúsculas) e validado contra `production`/`development`; qualquer outro valor (typo, ex.: `prod`, `Produção`) cai no fallback seguro `development` e gera um `WARNING` (`evento: app_env_invalido`) sem expor o valor configurado. | **Sim**, definida como `production` no `render.yaml` do serviço | Produção | `production` | Cai em `development` (fallback local), liberando origens de CORS mais permissivas (pensadas para localhost) — inadequado em produção. Confirme o valor efetivo no log de startup (`ambiente: "production"`); `/api/version` e `/api/health` não expõem esse campo. | Não |
| `MISTICA_SITE_API_KEY` | Chave usada pelo site e integrações servidor-a-servidor para gravar/ler dados protegidos da API (produtos, vendas, clientes, backup, diagnóstico). | Sim (ou `MISTICA_SYNC_KEY` como alternativa) | Produção | `chave-longa-aleatoria-fake` | Todas as rotas protegidas por chave de API respondem `403`; se **nenhuma** das duas variáveis estiver configurada, essas rotas ficam inacessíveis mesmo com chave correta (erro `503` pedindo configuração). | **Sim** — é um segredo de acesso |
| `MISTICA_ADMIN_PASSWORD` | Senha do usuário `admin` criado/redefinido automaticamente no startup. | Sim | Produção | `senha-forte-fake` | Nenhum admin automático é criado/redefinido; um `admin` pré-existente continua com a senha antiga. | **Sim** |
| `MISTICA_PIX_KEY` | Chave Pix usada para gerar o payload de cobrança no checkout. | Sim | Produção | `chave-pix-fake` | O payload Pix é gerado com chave vazia — pagamentos não chegam à conta correta. | **Sim** |

## Opcionais em produção (têm padrão seguro)

| Variável | Finalidade | Obrigatória? | Ambiente | Exemplo | Comportamento se ausente | Sensível? |
|---|---|---|---|---|---|---|
| `MISTICA_SYNC_KEY` | Fallback legado de `MISTICA_SITE_API_KEY` (aceito nas mesmas rotas). | Não | Produção | `chave-legada-fake` | Só `MISTICA_SITE_API_KEY` vale. | **Sim** |
| `MISTICA_LOG_LEVEL` | Nível do logging estruturado em JSON. | Não (padrão `INFO`) | Todos | `INFO` | Usa `INFO`. | Não |
| `MISTICA_PIX_NOME` | Nome do recebedor no payload Pix. | Não (padrão `MISTICA PRESENTES`) | Produção | `MISTICA PRESENTES` | Usa o padrão. | Não |
| `MISTICA_PIX_CIDADE` | Cidade do recebedor no payload Pix. | Não (padrão `PINHALZINHO`) | Produção | `PINHALZINHO` | Usa o padrão. | Não |
| `MISTICA_PIX_WEBHOOK_SECRET` | Segredo para validar o webhook de confirmação de pagamento Pix. | Recomendada | Produção | `segredo-webhook-fake` | O webhook aceita confirmações sem validar a assinatura — recomenda-se fortemente configurar em produção. | **Sim** |
| `MISTICA_MINUTOS_EXPIRACAO_PEDIDO` | Minutos até um pedido "Aguardando pagamento" expirar e repor estoque. | Não (padrão `30`) | Produção | `30` | Usa `30`. | Não |
| `MISTICA_LOGIN_WINDOW_MINUTES` | Janela (minutos) de contagem de tentativas de login do painel. | Não (padrão `10`) | Produção | `10` | Usa `10`. | Não |
| `MISTICA_LOGIN_MAX_ATTEMPTS` | Tentativas de login permitidas na janela acima antes de atrasar/bloquear. | Não (padrão `5`) | Produção | `5` | Usa `5`. | Não |
| `MISTICA_LOGIN_MAX_DELAY_SECONDS` | Atraso máximo (segundos) aplicado a tentativas de login repetidas. | Não (padrão `2`) | Produção | `2` | Usa `2`. | Não |
| `MISTICA_DEFAULT_PANEL_PASSWORD` | Senha padrão usada ao sincronizar um novo usuário do painel sem senha definida. | Não | Produção | `senha-temporaria-fake` | Usuários sincronizados sem senha ficam sem senha padrão (login por senha fica indisponível até definição manual). | **Sim** |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON da conta de serviço do Google usada para upload no Google Drive (cursos/músicas). | Não | Produção | `{"type": "service_account", "...": "..."}` | Upload cai automaticamente para armazenamento local em disco (dentro do mesmo Persistent Disk). | **Sim** |
| `GOOGLE_DRIVE_FOLDER_CURSOS` | ID da pasta do Google Drive para materiais de curso, quando `GOOGLE_SERVICE_ACCOUNT_JSON` está configurada. | Não | Produção | `1AbCdEfGhIjKlMnOpQrSt-fake` | Upload vai para a raiz do Drive configurado, ou cai para disco local se `GOOGLE_SERVICE_ACCOUNT_JSON` também estiver ausente. | Não |
| `GOOGLE_DRIVE_FOLDER_MUSICAS` | ID da pasta do Google Drive para músicas de ambiente. | Não | Produção | `1XyZ9876543210AbCdEf-fake` | Mesmo comportamento de `GOOGLE_DRIVE_FOLDER_CURSOS`. | Não |
| `MISTICA_BUILD_ID` | Identificador curto de build exposto (sanitizado) em `GET /api/version` como `build`. | Não | Produção | `abc1234` | Cai para `RENDER_GIT_COMMIT` (truncado/sanitizado); se nenhuma das duas existir, `build` é `"unknown"`. | Não |
| `RENDER_GIT_COMMIT` | Preenchida automaticamente pelo Render com o commit do deploy atual; usada como fallback de `MISTICA_BUILD_ID` em `/api/version`, truncada a 12 caracteres e filtrada para conter só `[a-zA-Z0-9._-]`. | Não (automática no Render) | Produção | `a1b2c3d4e5f6` | Ver `MISTICA_BUILD_ID`. | Não |
| `MISTICA_BUILD_DATE` | Data do build, exposta em `/api/version` como `release_date`, se preenchida manualmente. | Não | Produção | `2026-07-13` | `release_date` retorna `null`. | Não |

## Apenas desenvolvimento/rede local (`api/main.py`, `MisticaLauncher.py`)

Estas variáveis controlam a API local usada na loja física (rede interna) e o app desktop — não são usadas pela API pública do site (`backend/main.py`, deployada no Render).

| Variável | Finalidade | Obrigatória? | Ambiente | Exemplo | Comportamento se ausente | Sensível? |
|---|---|---|---|---|---|---|
| `MISTICA_API_TOKEN` | Token da API local (rede da loja/painel mobile). | Sim, para usar a API local | Desenvolvimento/rede local | `token-rede-local-fake` | Rotas autenticadas da API local ficam inacessíveis. | **Sim** |
| `MISTICA_ALLOWED_ORIGINS` | Origens CORS permitidas para a API local, separadas por vírgula. | Não | Desenvolvimento/rede local | `http://localhost,http://127.0.0.1` | Em produção (`APP_ENV=production`) nenhuma origem é liberada por padrão; fora de produção, usa `http://localhost,http://127.0.0.1`. | Não |
| `MISTICA_SERVER_PORT` | Porta da API local quando executada fora do Render. | Não | Desenvolvimento/rede local | `8000` | Usa a porta padrão do framework/launcher. | Não |
| `MISTICA_PASSWORD_SALT` | Sal usado para hash de senha em ferramentas locais/desktop. | Não (tem padrão no código) | Desenvolvimento/desktop | `sal-fake` | Usa o sal padrão embutido no código — aceitável só fora de produção. | **Sim** |

## Como configurar no Render

Vá em **Environment** no serviço `misticapresentes-api` e cadastre cada chave marcada como obrigatória (e as opcionais desejadas) com o valor real — nunca no `.env.example` nem em commits. Veja `.env.example` neste repositório para o formato de referência (sem valores reais) e `render.yaml` para as variáveis já declaradas como parte do serviço versionado.

**Atenção especial:** `MISTICA_DB_PATH` (ou `DATABASE_PATH`) é a única variável cuja ausência, sozinha, causa perda de dados em produção — todas as outras têm um padrão seguro ou apenas desabilitam uma funcionalidade específica sem apagar pedidos existentes.
