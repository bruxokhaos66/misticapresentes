# Mística Painel Android

Aplicativo Android da Mística. Esta PR (#411 — Fundação segura) cria a base
moderna, segura e testável sobre a qual a Central de Atendimento, o
dashboard nativo e as notificações (PRs seguintes) serão construídos, **sem**
remover o modo WebView legado que as lojas já usam hoje.

## Arquitetura

Migração híbrida e gradual: telas novas em **Kotlin + Jetpack Compose**
(Material 3), o WebView legado preservado como tela isolada de transição, e
nenhuma regra de negócio duplicada no app — o app só consome as APIs REST já
existentes no backend (`backend/user_sync_routes.py` nesta PR; a Central de
Atendimento vem na PR #412).

```text
br.com.misticapresentes.painel
├── app          # Application, container de DI manual, fábrica de ViewModel
├── navigation   # NavHost e rotas Compose
├── ui           # Telas Compose (splash, login, home, estados) e tema
├── auth         # AuthRepository, estado de autenticação
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

Com `NEW_AUTH_ENABLED` desligada (padrão de produção nesta PR), o app abre
direto no painel legado — exatamente o comportamento de hoje —, o que dá
**rollback trivial**: se algo no fluxo novo falhar em produção, desligar essa
flag (novo build ou, futuramente, flag remota) volta o app ao estado atual
sem precisar reverter código.

## Limitações desta PR

- A Central de Atendimento, dashboard nativo e push (FCM) **não** são
  implementados aqui — só a fundação para recebê-los.
- Não há tela de configuração de URL customizada em dev ainda (só a flag no
  `BuildConfig`).
- DI é manual (`app/AppContainer`), sem Hilt/Koin — reavaliar se a
  complexidade justificar na PR #412.
- Testes de UI/Compose exigem dispositivo/emulador e não rodam no CI desta
  PR.
- Nenhuma build de release é assinada ou publicada por este módulo/workflow.

## Próximos passos (PR #412)

- Central de Atendimento nativa consumindo `backend/whatsapp_inbox_routes.py`
  e `backend/whatsapp_atendimento_routes.py` (fila, conversas, mensagens,
  produtos, mídia, assumir/transferir/resolver) sobre esta mesma fundação de
  rede/auth/segurança.
- `FLAG_SECURE` nas novas telas com dado de cliente/mensagem.
- Permissões de câmera/áudio com fluxo de runtime permission.
