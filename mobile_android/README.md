# Mística Painel Android

Aplicativo Android da Mística. Esta PR (#411 — Fundação segura) cria a base
moderna, segura e testável sobre a qual a Central de Atendimento, o
dashboard nativo e as notificações (PRs seguintes) serão construídos, **sem**
remover o modo WebView legado que as lojas já usam hoje.

## Arquitetura

Migração híbrida e gradual: telas novas em **Kotlin + Jetpack Compose**
(Material 3), o WebView legado preservado como tela isolada de transição, e
nenhuma regra de negócio duplicada no app — o app só consome as APIs REST já
existentes no backend (`backend/user_sync_routes.py` na fundação; a Central
de Atendimento nativa, PR #412, consome `/api/admin/whatsapp/*`).

```text
br.com.misticapresentes.painel
├── app          # Application, container de DI manual, fábrica de ViewModel
├── navigation   # NavHost e rotas Compose
├── ui           # Telas Compose (splash, login, home, estados) e tema
├── auth         # AuthRepository, estado de autenticação
├── atendimento  # Central de Atendimento nativa (PR #412) -- network/dto,
│                # repository, model, ui/list, ui/detail
├── network      # Retrofit/OkHttp, interceptors, ApiResult, CookieJar
├── security     # Armazenamento criptografado (Keystore), FLAG_SECURE
├── legacy       # Activity do WebView legado, endurecida
└── common       # Ambiente, feature flags, DataStore, conectividade
```

`MainActivity` é o novo ponto de entrada Compose. `legacy/LegacyPanelActivity`
é uma Activity separada com o WebView, aberta a partir da Home (ou
diretamente, se `NEW_AUTH_ENABLED` estiver desligada — ver Feature flags).

## Ambientes (flavors)

Três flavors na dimensão `ambiente`, cada um com nome visual, URL base e
flags próprias — nunca é possível confundir dev/homolog com produção:

| Flavor | Nome visual | applicationId | URL base |
|---|---|---|---|
| `dev` | Mística Dev | `br.com.misticapresentes.painel.dev` | `https://dev.misticaesotericos.com.br/` (HTTP local liberado só para `10.0.2.2`/`localhost`) |
| `homolog` | Mística Homologação | `br.com.misticapresentes.painel.homolog` | `https://homolog.misticaesotericos.com.br/` |
| `prod` | Mística | `br.com.misticapresentes.painel` | `https://misticaesotericos.com.br/` |

Nenhuma URL de produção está hardcoded fora do `app/build.gradle` — tudo passa
por `BuildConfig` (`BASE_URL`, `LEGACY_PANEL_URL`, `ENVIRONMENT_NAME`,
`ENVIRONMENT_LABEL`). A Home e a tela de login sempre mostram um selo com o
ambiente atual.

## Como configurar e executar

1. Instale o Android Studio (Giraffe+) com JDK 17.
2. Abra a pasta `mobile_android`.
3. Selecione a variante `devDebug` no seletor de Build Variants.
4. Rode em um emulador ou dispositivo conectado.

Build via linha de comando (sempre pelo wrapper, nunca por uma instalação de
Gradle separada — build local e CI usam a mesma versão):

```bash
cd mobile_android
./gradlew assembleDevDebug
```

## Como testar

```bash
cd mobile_android
./gradlew lint
./gradlew testDebugUnitTest
./gradlew assembleDebug
```

Os testes de UI/Compose (`app/src/androidTest`) exigem um dispositivo ou
emulador e não rodam no CI desta PR (que cobre lint + testes unitários +
build debug, conforme §15 do plano). Rode-os manualmente com:

```bash
./gradlew connectedDevDebugAndroidTest
```

Nenhum teste depende de produção, credenciais reais, Meta, Render ou
WhatsApp real — todos usam fakes (`testutil/Fake*`) ou `MockWebServer`.

## Fluxo de login

Reaproveita a autenticação **já existente** no backend
(`POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, em
`backend/user_sync_routes.py`): sessão por cookie HttpOnly/Secure/SameSite=Lax
(`mistica_painel_sessao`, emitido por `backend/panel_sessions.py`). Não foi
inventado nenhum endpoint novo.

- O cookie de sessão é persistido de forma **criptografada** (Android
  Keystore, via `EncryptedSharedPreferences`) por um `CookieJar` do OkHttp
  (`PersistentCookieJar`) — a sessão sobrevive ao fechar o app, como em um
  navegador, mas nunca em texto puro em disco.
- Requisições que mudam estado (POST/PUT/PATCH/DELETE) recebem um header
  `Origin` apontando para a URL base do ambiente, porque o backend valida
  Origin/Referer como defesa de CSRF (`panel_sessions._validar_origem_csrf`)
  nas rotas autenticadas por sessão.
- `GET /api/auth/me` sempre revalida a sessão no servidor ao abrir o app —
  a sessão local nunca é confiada isoladamente.
- Qualquer `401` fora do próprio login dispara `SessionExpiredNotifier`, que
  leva a UI para a tela "Sua sessão expirou" e limpa a sessão local.
- A senha nunca é logada e é apagada do estado da tela assim que o envio
  termina (sucesso ou falha).

Não há `app_token` em query string, token fixo, chave administrativa dentro
do APK, credencial da Meta ou segredo do Render em nenhum lugar do app.

## Rede segura

- Cliente único (`network/ApiClient`): Retrofit + OkHttp, timeouts
  explícitos (connect 15s / read e write 20s), serialização com
  `kotlinx.serialization`.
- `ApiResult`/`ApiError` padronizam sucesso e erro (401/403/404/409/422/429/5xx
  + timeout + sem conexão), cada um com mensagem amigável pronta para a UI.
- Retry automático (`RetryInterceptor`) **somente** em GET/HEAD e apenas
  diante de falha de rede ou 5xx — nunca em POST/PUT/PATCH (envio de
  mensagem/mídia da futura Central de Atendimento não tem retry automático,
  por não haver garantia de idempotência).
- Log HTTP (`HttpLoggingInterceptor`) ligado só em dev/homolog
  (`BuildConfig.VERBOSE_NETWORK_LOGS`), nível `HEADERS` (nunca corpo), com
  `Cookie`, `Set-Cookie`, `Authorization` e `X-Mistica-Api-Key` redigidos.
  Em produção o log fica em `NONE`.

## Armazenamento

- **Sensível** (cookie de sessão, login/perfil do usuário autenticado):
  `security/SecureStorage`, `EncryptedSharedPreferences` com chave do
  Android Keystore (AES256-GCM). Nunca guarda senha, nunca guarda mensagem.
- **Não sensível** (ambiente, overrides locais de feature flag, última tela,
  flag de migração legada): `common/AppPreferences`, Jetpack DataStore.
- **Migração do app legado**: `common/LegacyPrefsMigration` lê as
  `SharedPreferences` antigas (`mistica_painel_prefs`: `server_url`,
  `api_token`), as apaga, e **descarta o token antigo** — ele nunca é
  reaproveitado como credencial real, pois não corresponde ao esquema de
  sessão por cookie do backend.

## Rede — Network Security Config

`android:usesCleartextTraffic="false"` no `AndroidManifest.xml` (não é mais
`true` global). Cada ambiente aponta para seu `networkSecurityConfig` via
`manifestPlaceholders`:

- `homolog`/`prod` → `res/xml/network_security_config.xml`: cleartext
  bloqueado globalmente, validação normal de certificado do sistema (sem
  trust-anchor extra, sem TrustManager permissivo).
- `dev` → `res/xml/network_security_config_dev.xml`: mesmo bloqueio global,
  com uma única exceção de cleartext para os hosts locais de
  desenvolvimento (`10.0.2.2`, `localhost`, `127.0.0.1`).

O WebView legado usa `MIXED_CONTENT_NEVER_ALLOW` (antes era
`MIXED_CONTENT_ALWAYS_ALLOW`).

## WebView legado endurecido

`legacy/LegacyPanelActivity` mantém o painel operacional acessível durante a
transição, mas:

- só navega, dentro do WebView, para o host configurado no `BuildConfig`
  daquele ambiente (`LegacyUrlPolicy`); qualquer outro `http(s)` abre no
  navegador do sistema; `file://` e `content://` são sempre bloqueados;
- `allowFileAccess`, `allowContentAccess`, `allowUniversalAccessFromFileURLs`
  e `allowFileAccessFromFileURLs` desligados;
- nenhum `addJavascriptInterface`;
- nenhum `onReceivedSslError` sobrescrito (certificado inválido nunca é
  aceito);
- cookies do WebView são apagados ao fechar a tela (`onDestroy`);
- a URL vem sempre do `BuildConfig` do flavor — em produção/homolog não há
  campo de URL customizada. A flag `ALLOW_CUSTOM_LEGACY_URL` já existe no
  `BuildConfig` do flavor dev para uma futura tela de configuração local;
  esta PR ainda não tem UI para isso.
- `FLAG_SECURE` habilitada (via `security/ScreenSecurity`, mecanismo
  reutilizável) — a tela mostra dados operacionais da loja, então
  screenshot/gravação de tela/preview em "recentes" ficam bloqueados.

## Segurança de tela (FLAG_SECURE)

`security/ScreenSecurity.enable(activity)` / `.disable(activity)` é o
mecanismo reutilizável para telas sensíveis. Nesta PR só é aplicado à tela
legada. A Central de Atendimento nativa (PR #412) deve chamá-lo nas suas
telas autenticadas com dados de cliente/mensagens. Splash, login e as
configurações do app **não** usam FLAG_SECURE (não há necessidade ali).

## Feature flags

Definidas em `common/FeatureFlags.kt`, com default vindo do `BuildConfig` de
cada flavor e podendo ser sobrescritas localmente via DataStore
(`common/AppPreferences`) — o override local nunca concede uma ação que o
backend negaria; ele só decide o que a UI deste build mostra:

| Flag | Default prod | Default dev/homolog |
|---|---|---|
| `NEW_AUTH_ENABLED` | `false` | `true` |
| `LEGACY_WEBVIEW_ENABLED` | `true` | `true` |
| `NATIVE_WHATSAPP_ENABLED` | `false` | `false` |
| `NATIVE_DASHBOARD_ENABLED` | `false` | `false` |
| `PUSH_NOTIFICATIONS_ENABLED` | `false` | `false` |
| `REALTIME_SYNC_ENABLED` | `false` | `false` |
| `BACKGROUND_SYNC_ENABLED` | `false` | `false` |
| `ATTENDANCE_NOTIFICATIONS_ENABLED` | `false` | `false` |

Com `NEW_AUTH_ENABLED` desligada (padrão de produção nesta PR), o app abre
direto no painel legado — exatamente o comportamento de hoje —, o que dá
**rollback trivial**: se algo no fluxo novo falhar em produção, desligar essa
flag (novo build ou, futuramente, flag remota) volta o app ao estado atual
sem precisar reverter código.

## Central de Atendimento nativa (PR #412)

Pacote `atendimento` (`network`, `network/dto`, `repository`, `model`,
`ui/list`, `ui/detail`), atrás da flag `NATIVE_WHATSAPP_ENABLED` (default
`false` em todos os flavors nesta PR — habilite localmente via override de
DataStore para testar em dev/homolog). Consome exclusivamente os endpoints já
existentes sob `/api/admin/whatsapp` (`backend/whatsapp_atendimento_routes.py`,
`backend/whatsapp_inbox_routes.py`, `backend/whatsapp_catalog_routes.py`) pela
mesma sessão por cookie/Retrofit/OkHttp desta fundação (ver
`network/ApiClient.createAtendimentoApi`). Escopo desta PR: fila, lista de
conversas (minhas/fila/todas), detalhe/histórico de mensagens paginado, envio
de texto e de produto (com Idempotency-Key por tentativa), assumir/liberar/
transferir/resolver, histórico de atribuição, atualização manual (sem
polling/WorkManager/tempo real). Nunca persiste mensagem, telefone completo ou
dado de cliente em disco — tudo em memória via StateFlow, perdido ao sair do
processo. Câmera, imagem, áudio, push e IA ficam para PRs futuras.

## Limitações desta PR (#412)

- Câmera, envio de imagem/áudio, notificações push, sincronização em tempo
  real, WorkManager, IA e Dashboard **não** são implementados na Central de
  Atendimento nativa — apenas o que está listado acima.
- Não há tela de configuração de URL customizada em dev ainda (só a flag no
  `BuildConfig`).
- DI é manual (`app/AppContainer`), sem Hilt/Koin.
- Testes de UI/Compose exigem dispositivo/emulador e não rodam no CI desta
  PR.
- Nenhuma build de release é assinada ou publicada por este módulo/workflow.

## Sincronização, WorkManager e notificações (PR #414)

**Auditoria feita ANTES de implementar** (backend `backend/whatsapp_*_routes.py`
e app existente da PR #412/#413): o backend não expõe WebSocket, SSE, long
polling, webhook interno para o app, nem endpoint incremental por cursor/
timestamp para eventos — só paginação por página (fila/`my-conversations`/
`conversations`) e por `before_id` (mensagens). Já existem, e esta PR
reaproveita: `unread_count` por conversa, `assignment_version` (controle
otimista já usado desde a PR #412), Retrofit/OkHttp/interceptors/cookie de
sessão, `ConnectivityObserver`, `FeatureFlagsRepository`/DataStore,
`SecureSessionStore`. Não havia FCM configurado (sem `google-services.json`,
sem plugin/dependência do Google Services, sem `firebase-messaging` em
nenhum `build.gradle`) — só a flag `PUSH_NOTIFICATIONS_ENABLED`, já existente
e não usada por nenhum código.

Com base nisso, a estratégia adotada é **polling HTTP eficiente** (não havia
WebSocket/SSE/endpoint incremental para reaproveitar, e não faria sentido
criar um do zero só para esta PR):

- Conversa aberta (`ConversationScreen` visível): a cada
  `SyncConfig.CONVERSATION_POLL_INTERVAL_MS` (8s).
- Lista/fila (`AtendimentoListScreen` visível): a cada
  `SyncConfig.LIST_POLL_INTERVAL_MS` (15s).
- Todos os intervalos vivem em `atendimento/sync/SyncConfig.kt` — nenhum
  outro arquivo tem um valor de intervalo "solto".
- `atendimento/sync/AttendanceSyncLoop` é o motor único (`start()`/`stop()`
  idempotentes) usado por ambas as telas via `viewModelScope` (nunca
  `GlobalScope`) — liga só quando a tela está em `ON_RESUME` E a flag
  `REALTIME_SYNC_ENABLED` está ligada; qualquer falha dispara backoff
  exponencial (dobra o intervalo até `FOREGROUND_MAX_BACKOFF_MS`), sucesso
  volta ao intervalo-base.
- O generation guard que já existia em `ConversationViewModel` (PR #412,
  para `load()`/`refreshMessagesQuietly()`) agora também guarda os ciclos de
  polling — uma resposta atrasada de um ciclo antigo nunca sobrescreve um
  estado mais novo.
- Background: `AttendanceBackgroundSyncWorker` (WorkManager,
  `PeriodicWorkRequest` a cada `SyncConfig.BACKGROUND_SYNC_INTERVAL_MINUTES`
  = 15min, o mínimo absoluto do Android), agendado/cancelado como trabalho
  ÚNICO (`enqueueUniquePeriodicWork` + `ExistingPeriodicWorkPolicy.UPDATE`)
  por `AttendanceBackgroundSyncScheduler`. Constraint de rede conectada,
  `BackoffPolicy.EXPONENTIAL`. Nunca substitui o polling em primeiro plano —
  só uma checagem leve de não lidas quando o app está em background. Checa
  `BACKGROUND_SYNC_ENABLED` e sessão local (`SecureSessionStore.hasSession()`)
  DENTRO do próprio `doWork()` (nunca só no agendamento), e é cancelado no
  logout/sessão expirada e quando a flag é desligada
  (`MisticaApplication.observeBackgroundSyncFlagAndSession`).
- Notificações: sem FCM configurado (ver auditoria acima), esta PR implementa
  só uma camada de abstração (`notifications/AttendanceNotifier`) + uma
  implementação local (`AndroidAttendanceNotifier`, `NotificationManagerCompat`),
  disparada pela própria sincronização (polling e Worker) — nunca por push de
  verdade. **Limitação conhecida**: sem servidor push real, uma mensagem só é
  percebida no próximo ciclo de sincronização, nunca instantaneamente com o
  app fechado fora da janela do WorkManager. Conteúdo sempre genérico
  ("Nova mensagem na Central de Atendimento" — nunca nome, telefone, texto da
  mensagem ou mídia), suprimida quando a própria conversa já está visível em
  primeiro plano (`atendimento/sync/AttendanceForegroundState`), id estável
  por conversa (dedupe), `PendingIntent` imutável, `FLAG_ACTIVITY_NEW_TASK` +
  extra de `conversationId` validado (`> 0`) para abrir a conversa certa, e
  limpa ao abrir a conversa (`onScreenResumed`) ou no logout (`clearAll`).
- Três novas flags, todas desligadas em todos os flavors (ver tabela acima):
  `REALTIME_SYNC_ENABLED`, `BACKGROUND_SYNC_ENABLED`,
  `ATTENDANCE_NOTIFICATIONS_ENABLED`. Cada uma é revalidada onde importa
  (ViewModel antes de iniciar o polling, dentro do `doWork()` do Worker,
  antes de notificar) — nunca só escondida na UI.
- UI: só um indicador textual discreto de sincronização ("Sincronizando...",
  "Atualizado agora", "Falha ao atualizar" — `atendimento/ui/common/syncStatusLabel`),
  o banner de offline já existente (agora também na tela de detalhe) e um
  badge simples de não lidas no topo da lista. Nenhum redesenho de tela, e o
  fluxo de câmera/galeria/áudio da PR #413 não foi alterado.

### Limitações conhecidas desta PR (#414)

- Sem FCM real: entrega depende do próximo ciclo de polling/WorkManager (ver
  acima) — não há push instantâneo com o app totalmente fechado.
- Ambiente de build usado para esta PR não teve acesso ao repositório Maven
  do Google (`dl.google.com` bloqueado pela política de saída da sessão) —
  não foi possível compilar/rodar `./gradlew test`/`assemble*` aqui; ver
  relatório da PR para o que foi verificado por revisão manual de código.
- Testes de notificação/WorkManager usam Robolectric (JVM, sem
  dispositivo/emulador real) — nenhum teste manual em aparelho físico foi
  executado nesta PR.

## Próximos passos

- Dashboard nativo e IA da Central de Atendimento continuam fora de escopo.
- FCM real (projeto Firebase de verdade, `google-services.json` real) para
  substituir a notificação local por push de verdade, quando/se decidido.
- `FLAG_SECURE` já cobre lista e detalhe da Central de Atendimento; estender
  a qualquer tela nova com dado de cliente/mensagem.
- Ícone de notificação dedicado (mono, para a barra de status) em vez de
  reaproveitar `ic_launcher`.
