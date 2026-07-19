# Content Security Policy (CSP) do site público

## Onde é enviada

O site público (`misticaesotericos.com.br`) é publicado via **GitHub Pages**
(`.github/workflows/deploy-pages.yml`, `actions/deploy-pages@v4`). GitHub
Pages **não permite configurar cabeçalhos HTTP customizados** — não há
mecanismo de `_headers`, proxy configurável ou qualquer camada de servidor
sob nosso controle nessa hospedagem. Por isso a CSP é entregue via

```html
<meta http-equiv="Content-Security-Policy" content="...">
```

em cada página HTML pública (24 páginas — ver lista em
`tests/test_csp_meta.py::PAGINAS_PUBLICAS`), inserida logo após
`<meta charset>`.

**Limitação importante do `<meta http-equiv>`** (spec CSP, não uma escolha
nossa): as diretivas `frame-ancestors`, `report-uri`/`report-to` e `sandbox`
são **ignoradas pelo navegador** quando entregues via meta tag — só têm
efeito via cabeçalho HTTP real. Como não há como enviar cabeçalho HTTP
nesta hospedagem, o site público **não tem proteção efetiva de
anti-clickjacking via CSP** (nem `X-Frame-Options`, que também exige
cabeçalho). Isso é uma limitação de infraestrutura, documentada aqui para
não passar a falsa impressão de que `frame-ancestors 'none'` protege o
site só por estar escrito na policy.

A **API** (`backend/main.py`, hospedada no Render/FastAPI, domínio
`api.misticaesotericos.com.br`) já envia CSP por cabeçalho HTTP de verdade
(`default-src 'none'; frame-ancestors 'none'`) — essa parte não mudou nesta
mudança, e `frame-ancestors` funciona ali normalmente porque é HTTP header,
não meta tag.

## Política aplicada (site público)

```
default-src 'self';
base-uri 'self';
object-src 'none';
form-action 'self';
script-src 'self' https://sdk.mercadopago.com https://www.googletagmanager.com https://connect.facebook.net;
style-src 'self' https://fonts.googleapis.com;
style-src-attr 'unsafe-inline';
img-src 'self' data: blob: https:;
font-src 'self' data: https://fonts.gstatic.com;
connect-src 'self' https://api.misticaesotericos.com.br https://*.mercadopago.com https://*.mercadopago.com.br
            https://www.google-analytics.com https://analytics.google.com https://www.googletagmanager.com
            https://www.facebook.com https://connect.facebook.net https://api.mercadolibre.com;
frame-src https://www.youtube.com https://*.mercadopago.com https://*.mercadopago.com.br;
worker-src 'self' blob:;
manifest-src 'self';
media-src 'self' blob: https://api.misticaesotericos.com.br;
upgrade-insecure-requests
```

## Por que cada origem externa está autorizada

| Origem | Diretiva | Motivo |
|---|---|---|
| `sdk.mercadopago.com` | script-src, connect-src | Carrega o SDK oficial `MercadoPago.js v2`, usado para tokenizar o cartão (CardForm) sem que os dados passem pelo nosso servidor. Único host do Mercado Pago mantido **exato** (sem curinga) em `script-src`, por ser a diretiva de maior risco. |
| `*.mercadopago.com`, `*.mercadopago.com.br` | connect-src, frame-src | O próprio SDK, rodando no navegador, monta os campos seguros do CardForm (número, validade, CVV) como iframes do Mercado Pago e chama a API dele diretamente para tokenizar o cartão, consultar bandeira/emissor e calcular parcelas — nunca é o nosso backend fazendo isso pelo cliente. Ver "Correção do CardForm sem foco/parcelas" abaixo sobre por que virou curinga de subdomínio em vez de hosts exatos. |
| `api.misticaesotericos.com.br` | connect-src, media-src | Nossa própria API (catálogo, carrinho, pedidos, pagamentos, vídeos de curso). |
| `www.googletagmanager.com` | script-src, connect-src | Google Analytics (`gtag.js`), carregado só depois de consentimento explícito (LGPD, ver `consent.js`) e só se `gaMeasurementId` estiver configurado em `site-config.js` (hoje vazio = inativo). |
| `www.google-analytics.com`, `analytics.google.com` | connect-src | Endpoints de coleta do Google Analytics, usados pelo `gtag.js` acima. |
| `connect.facebook.net` | script-src, connect-src | Meta/Facebook Pixel (`fbevents.js`), mesma regra de consentimento e mesma flag hoje vazia (`metaPixelId`) do Analytics. |
| `www.facebook.com` | connect-src | Endpoint de tracking do Facebook Pixel. |
| `www.youtube.com` | frame-src | Vídeos de aula incorporados via `<iframe>` na Escola Mística (`escola-curso.js`). |
| `fonts.googleapis.com`, `fonts.gstatic.com` | style-src, font-src | Fonte Google (`Cinzel`/`Inter`) usada em todo o site. |
| `api.mercadolibre.com` (host exato, sem curinga) | connect-src | Telemetria própria do SDK `MercadoPago.js v2` (`/tracks`) -- device fingerprint/analytics do CardForm, endpoint documentado do mesmo grupo Mercado Livre/Mercado Pago. Ver seção "Auditoria de runtime" abaixo. |

**Nenhuma dessas origens tem acesso a criar/consultar pagamentos com o
Access Token** — o Access Token nunca sai do backend (ver
`backend/mercadopago_flags.py`), então mesmo com `*.mercadopago.com`
liberado no `connect-src`, o navegador só consegue fazer as chamadas
públicas de tokenização que o SDK do Mercado Pago expõe para uso no
cliente (não há endpoint de criação de cobrança acessível sem o Access
Token, e o frontend nunca o possui).

### Correção: CardForm sem foco/parcelas (curinga de subdomínio do Mercado Pago)

**Sintoma reportado em sandbox**: o CardForm aparecia no checkout, mas os
campos de número/validade/CVV não aceitavam foco nem digitação, e o
seletor de parcelas ficava vazio.

**Causa raiz**: a CSP original autorizava só os hosts exatos
`sdk.mercadopago.com`, `api.mercadopago.com` e `www.mercadopago.com`. O
Secure Fields (iframes que o SDK `MercadoPago.js v2` injeta para número,
validade e CVV) e as chamadas de tokenização/parcelas do CardForm não têm
um único subdomínio documentado nem estável entre países/ambientes — para
um comerciante brasileiro (BRL), é esperado que parte do tráfego passe por
subdomínios sob `mercadopago.com.br`, não só `mercadopago.com`. Com
`frame-src`/`connect-src` restritos aos três hosts exatos, o navegador
bloqueia silenciosamente qualquer iframe/requisição para um subdomínio não
listado — o campo aparece (é só um `<div>` nosso) mas fica vazio por
dentro (o iframe nunca carrega), o que explica exatamente os dois sintomas
juntos (campo sem interação, parcelas nunca calculadas porque dependem do
BIN lido pelo campo de número).

**Correção**: `connect-src`/`frame-src` passaram de hosts exatos para
curinga de subdomínio do próprio Mercado Pago —
`https://*.mercadopago.com https://*.mercadopago.com.br`. Continua restrito
ao domínio do provedor de pagamento (não é um curinga global `*` nem
`https:`), só deixou de exigir um subdomínio específico que nem a
documentação oficial nem o repositório do SDK confirmam como fixo.
`script-src` continua com o host exato `sdk.mercadopago.com` (é a única
diretiva que executa JavaScript no nosso documento, então permanece a mais
restrita possível).

**Limitação de verificação**: este ambiente de desenvolvimento não tem
acesso de rede a `sdk.mercadopago.com` (política de rede do sandbox
bloqueia o host), então a correção não pôde ser confirmada com o SDK real
carregado num navegador aqui. A validação foi feita por: (1) revisão do
pacote npm oficial `@mercadopago/sdk-js` (confirma que o loader só injeta
`https://sdk.mercadopago.com/js/v2`, sem hosts adicionais visíveis nesse
pacote) e discussões públicas de outros integradores relatando o mesmo
tipo de bloqueio de CSP; (2) um teste Playwright dedicado
(`tests/e2e/csp-mercadopago-cardform.spec.js`) que simula, com um Chromium
real e a CSP de produção, o mesmo padrão de iframe/fetch que o CardForm
usa contra as origens agora autorizadas — confirmando que a política não
as bloqueia — e contra uma origem de terceiro não relacionada, confirmando
que o bloqueio de CSP continua funcionando para hosts fora do Mercado
Pago. **Recomendado**: validar visualmente em sandbox real (rede sem essa
restrição) antes de ativar `MERCADO_PAGO_ENABLED=true` em produção.

### Auditoria de runtime (violações reais pós-#365)

Depois do merge da PR #365 (que adicionou `iframe: true` à config do
`cardForm()`, corrigindo a montagem dos Secure Fields), o Console do
navegador passou a reportar 3 violações novas de CSP, todas originadas
dentro do bundle do SDK `MercadoPago.js v2` (`v2:1` -- código de terceiro,
fora do nosso controle) durante a montagem do CardForm real:

| # | Violação reportada | Diretiva responsável | Origem/ação bloqueada | Correção aplicada | Risco residual |
|---|---|---|---|---|---|
| 1 | `Applying inline style violates: style-src 'self' https://fonts.googleapis.com` | `style-src` (atributo `style=""`) | O SDK aplica `style=""` inline no `<div>` wrapper que envolve cada iframe de Secure Field (número/validade/CVV), para posicionar/dimensionar o campo dentro do nosso layout. | Adicionada a diretiva CSP3 `style-src-attr 'unsafe-inline'`, **separada** de `style-src`. Ela só cobre o atributo `style=""` -- não afeta `<style>`/`<link>` (que continuam em `style-src`/`style-src-elem`, sem `unsafe-inline`), nem `script-src`. | Um XSS que já tivesse conseguido injetar um atributo `style=""` arbitrário (ex.: via `innerHTML` não sanitizado) poderia usar CSS para acobertar/mascarar elementos (clickjacking visual) -- não pode executar JS. Mitigado porque o site não usa `innerHTML` com dado não confiável nas páginas públicas (ver seção "Handlers inline removidos" acima) e `style-src-elem`/`script-src` continuam tão restritos quanto antes. Navegadores sem suporte a CSP3 `style-src-attr` (raros hoje) ignoram a diretiva e caem de volta em `style-src` sem `unsafe-inline` -- o campo fica visualmente quebrado, não inseguro. |
| 2 | `Executing inline script violates: script-src 'self' https://sdk.mercadopago.com https://www.googletagmanager.com https://connect.facebook.net` | `script-src` | O SDK tenta executar um `<script>` inline (bootstrap do módulo de telemetria/device fingerprint do CardForm, correlacionado com a violação de `connect-src` abaixo e com o erro `Could not send event`). | **Nenhuma.** `script-src` foi mantido exatamente como estava, sem `'unsafe-inline'`, hash ou nonce. | **Deliberadamente não corrigido nesta mudança.** É a diretiva de maior risco (execução de código) e nenhuma das opções seguras é viável aqui: hash é inviável sem confirmar que o conteúdo do script é estável entre carregamentos/sessões (não há acesso de rede a `sdk.mercadopago.com` neste ambiente para capturar e validar isso -- ver limitação abaixo), e nonce por header dinâmico é inviável porque o site público é HTML estático via GitHub Pages sem servidor sob nosso controle (mesma limitação já documentada no topo deste arquivo). O SDK oficial não documenta esse script inline como requisito para tokenizar o cartão -- é telemetria própria do Mercado Pago, então o CardForm deve continuar funcional (Secure Fields, tokenização, parcelas) mesmo com esse script bloqueado; o efeito observável é só o console.error `Could not send event`, sem impacto no pagamento. **Ação pendente**: capturar em sandbox real (ver procedimento no fim deste arquivo) se o hash do script é estável; se for, trocar esta linha por `script-src-elem` com o(s) hash(es) exatos -- nunca por `'unsafe-inline'` global. |
| 3 | `Connecting to: https://api.mercadolibre.com/tracks violates connect-src` (+ console `/checkout/api_integration Could not send event`, `/checkout/api_integration/card_form Could not send event`) | `connect-src` | Mesmo módulo de telemetria do SDK, enviando eventos de uso do CardForm para o endpoint de tracking do grupo Mercado Livre/Mercado Pago. | Adicionado **só o host exato** `https://api.mercadolibre.com` a `connect-src` (sem curinga `*.mercadolibre.com`, sem `https:`). | Baixo: é um endpoint de coleta de eventos (POST de telemetria), não expõe nem recebe credenciais nossas -- o Access Token nunca sai do backend (ver acima) e esse host não tem relação com criação/consulta de pagamentos. Mesmo padrão de risco já aceito para `www.google-analytics.com`/`connect.facebook.net`. |

**Confirmação da política efetivamente aplicada**: como não há build/SSR (HTML
estático), a única fonte de verdade é a própria `<meta http-equiv=
"Content-Security-Policy">` de cada página -- não existe CSP duplicada por
header nesta hospedagem (GitHub Pages) nem em nenhum outro arquivo de
config do site público (`render.yaml`, `netlify.toml` e `_headers`
inexistem no repositório). Em produção, confirmar no DevTools com:

```js
document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content
```

e conferir a aba Network (Response Headers) que **nenhum** header HTTP
`Content-Security-Policy` é enviado para o site público (o GitHub Pages não
adiciona um por conta própria) -- só a `<meta>` está em vigor ali. A API
(`api.misticaesotericos.com.br`) é o único domínio deste projeto que entrega
CSP por header real, e não serve nenhuma página do checkout.

**Limitação de verificação (mesma já registrada na correção anterior)**:
este ambiente de desenvolvimento não tem acesso de rede a
`sdk.mercadopago.com` nem a `api.mercadolibre.com`, então as 3 violações
acima não puderam ser reproduzidas com o SDK real neste sandbox -- foram
registradas a partir do relato do Console (violações #1-#3 do ticket) e
validadas por: (1) um teste Playwright dedicado
(`tests/e2e/csp-mercadopago-runtime-violations.spec.js`) que simula, com um
Chromium real e a CSP de produção (`index.html`), o mesmo padrão de
atributo `style=""` inline + `fetch` para `api.mercadolibre.com/tracks` que
o módulo de telemetria do CardForm usa, confirmando que a policy corrigida
não os bloqueia mais, **e** que um `<style>` injetado, um `<script>` inline
e um host de terceiro não relacionado continuam bloqueados (prova de que a
correção não abriu a diretiva além do necessário); (2) `pytest
tests/test_csp_meta.py`, que confirma estaticamente, nas 23 páginas
públicas, que `'unsafe-inline'` existe só em `style-src-attr` e que
`connect-src` só ganhou o host exato `api.mercadolibre.com`, sem curinga.
**Recomendado antes de `MERCADO_PAGO_ENABLED=true`**: validar visualmente em
sandbox real (rede sem essa restrição) que as 3 violações originais
desapareceram do Console e que o CardForm aceita clique/digitação nos 3
campos, reconhece o BIN e carrega parcelas -- ver "Procedimento de
homologação real" no fim deste arquivo.

### Auditoria do script inline bloqueado (pós-#368)

Depois das PRs #364/#365/#367/#368, o campo continuou reportado como sem
clique/digitação em navegador real, com a mesma violação de `script-src`
documentada acima (inline script bloqueado, hash `sha256-
ED3LX2MEfaqqX5WV3GnfgYRAVm3XvX0aNWaf1la6psU=` reportado nesta execução --
diferente dos dois hashes já registrados em execuções anteriores). Esta
mudança tratou a hipótese anterior ("é só telemetria") como **não
confirmada** e investigou de novo, com os seguintes resultados:

**1. Este ambiente continua sem acesso de rede a `sdk.mercadopago.com`.**
Confirmado de novo, desta vez de forma explícita e reproduzível: o proxy
de saída deste sandbox responde `403` a toda tentativa de `CONNECT` para
`sdk.mercadopago.com:443` (`curl` direto e `WebFetch` — ambos falham com
403; `$HTTPS_PROXY/__agentproxy/status` lista os rejects em
`recentRelayFailures`). Isso significa que **nenhuma das validações que
exigem o SDK real** (capturar o `securitypolicyviolation` real do
navegador, confirmar estabilidade do hash em 5+ recarregamentos, testar
`trackingDisabled`/`advancedFraudPrevention` contra o comportamento real,
clicar/digitar nos Secure Fields reais, homologar em sandbox com cartão de
teste) pôde ser executada nesta mudança — mesma limitação já registrada em
todas as correções anteriores deste arquivo. Nada abaixo deve ser lido
como confirmação de que o cartão funciona.

**2. Nova evidência: migrar para o pacote npm `@mercadopago/sdk-js` não
evita o script inline.** O registro npm (`registry.npmjs.org`) é
acessível neste ambiente, então foi possível baixar e inspecionar o pacote
oficial (`npm pack @mercadopago/sdk-js`, versão 0.0.3, `dist/index.js`).
O `loadMercadoPago()` do pacote faz exatamente a mesma coisa que o
`<script src="https://sdk.mercadopago.com/js/v2">` da versão CDN: injeta
um `<script>` **externo** apontando para `https://sdk.mercadopago.com/js/v2`
e resolve uma Promise quando ele carrega -- não existe nenhum caminho
alternativo de carregamento nem bootstrap diferente no pacote npm. O
bundle servido por essa mesma URL (`js/v2`) é idêntico nos dois casos; é
de dentro desse bundle -- não do loader -- que vem o script inline
reportado. Portanto **migrar de CDN para npm não muda nada em relação a
este bloqueio de CSP**: não há necessidade de fazer essa migração (evitada
nesta mudança, como o item 6 do procedimento pedia para só migrar com
prova de que resolve o problema -- aqui está a prova do contrário).

**3. Opções oficiais do SDK confirmadas (README do pacote, seção API):**

| Opção | Default | Descrição oficial |
|---|---|---|
| `trackingDisabled` | `false` | "Enable/disable tracking of generic usage metrics" |
| `advancedFraudPrevention` | `true` | "Set the advanced fraud prevention status" |

Essas duas opções e seus defaults foram confirmados tanto no
`README.md` do pacote `@mercadopago/sdk-js` baixado do npm (fonte
primária, texto idêntico) quanto em buscas públicas sobre o SDK. Não há
documentação oficial associando explicitamente qualquer uma delas ao
script inline reportado neste ticket -- a suposição de que
`trackingDisabled` é a opção mais próxima do script de telemetria é uma
inferência (nome da opção + correlação já registrada com a violação de
`connect-src` para `api.mercadolibre.com/tracks` e o console.error
`Could not send event`), não uma confirmação do fabricante.

**4. Ação tomada nesta mudança:** `trackingDisabled: true` foi adicionado
à chamada `new MercadoPago(publicKey, options)` em
`v2-mercadopago-checkout.js`, por ser (a) uma opção oficial documentada
pelo próprio SDK, (b) a opção cujo nome/descrição melhor corresponde à
hipótese de telemetria já registrada, e (c) uma mudança que não relaxa a
CSP nem depende de hash instável. `advancedFraudPrevention` **não** foi
alterado -- continua no default (`true`, nunca passado como `false`): é
uma opção de prevenção de fraude, não de telemetria genérica, e desativá-
la tem impacto direto e não documentado nesta mudança sobre
aprovação/risco de fraude (o próprio ticket pede para não fazer isso sem
documentar esse impacto, e não há como medir esse impacto sem
processar pagamentos reais em produção).

**5. O hash não foi adicionado a `script-src`.** O próprio ticket já
lista 3 hashes diferentes observados em execuções anteriores para o que é
descrito como o mesmo script -- evidência direta de instabilidade (CSP
hash exige o conteúdo do script ser byte-a-byte idêntico para o hash
bater; um hash que muda entre execuções nunca autoriza consistentemente o
mesmo script, e cada mudança de hash reabre exatamente o mesmo sintoma
"campo sem interação" até alguém notar e atualizar a CSP de novo). Sem
acesso de rede ao SDK real neste ambiente, não há como este PR
independentemente confirmar ou refutar essa instabilidade -- então, por
segurança, o hash não foi adicionado. `tests/test_csp_meta.py::
test_csp_script_src_sem_hash_nao_validado` trava essa decisão (falha se
qualquer `sha256-` aparecer em `script-src`).

**6. Ferramenta criada para fechar o loop:** como este ambiente não pode
executar os passos 2-6 e 8 do procedimento pedido (capturar o evento real,
testar em 5+ recarregamentos/navegadores/dispositivos, validar
`trackingDisabled`/`advancedFraudPrevention` contra o SDK real, testar
clique/digitação/parcelas/`elementFromPoint`/foco), foi adicionada
`tests/manual/mp-csp-diagnostico.html` (+ `.css`/`.js` externos, sem
inline, para não violar a própria CSP da página) -- uma página para um
humano abrir num navegador com acesso de rede real, com:
- a mesma CSP de produção já aplicada;
- o listener de `securitypolicyviolation` pedido no ticket, mostrando
  `effectiveDirective`/`blockedURI`/`sourceFile`/`lineNumber`/
  `columnNumber`/`sample` numa tabela na tela (nunca lê nem loga
  cartão/CVV/token/CPF/e-mail -- o evento de violação de CSP não tem
  acesso a esses dados);
- um CardForm mínimo com Public Key de teste informada na hora (nunca
  persistida) para testar interatividade real;
- o checklist manual do procedimento de homologação abaixo.

`tests/e2e/csp-diagnostico-tool.spec.js` testa só o MECANISMO de captura
dessa ferramenta (uma violação sintética de `script-src`, não o SDK real)
-- confirma que a tabela recebe a linha e que nenhum termo sensível
aparece nela.

**Conclusão original desta mudança (revista abaixo):** não foi possível,
neste ambiente, provar nem refutar com evidência real se o script inline é
funcionalmente necessário para os Secure Fields ficarem interativos.
`trackingDisabled: true` foi adicionado como a mudança mais segura e
melhor fundamentada disponível sem acesso ao SDK real, mas seu efeito
sobre o script inline especificamente não pôde ser validado neste
ambiente.

### CORREÇÃO da conclusão acima -- evidência real obtida manualmente

Depois desta mudança, um humano com acesso de rede normal executou
`tests/manual/mp-csp-diagnostico.html` contra o SDK real do Mercado Pago
(fora deste ambiente de desenvolvimento). Resultado, registrado aqui
porque contradiz a suposição anterior deste arquivo:

- `typeof window.MercadoPago` retornou `"function"` (SDK carregou).
- Os 3 iframes reais de Secure Field foram criados, com origem
  `secure-fields.mercadopago.com`.
- `mpCardNumber`/`mpExpirationDate`/`mpSecurityCode` ficaram dentro do
  viewport, com geometria válida.
- `document.elementFromPoint` no centro de cada campo retornou o próprio
  iframe (nenhum overlay interceptando).
- Número, validade e CVV **aceitaram digitação**.
- O emissor foi reconhecido (Mastercard, no cartão de teste usado).
- As parcelas carregaram no seletor.
- **A violação de CSP do script inline (`script-src`) continuou aparecendo
  no Console durante todo o teste** -- ela não desapareceu, mas o CardForm
  funcionou de ponta a ponta mesmo assim.

**Isso invalida a hipótese "o script inline bloqueado é a causa do campo
não aceitar clique/digitação".** O script continuou bloqueado e o campo
funcionou. A hipótese registrada nas PRs #364/#365/#367/#368/#369 --
"talvez o script inline seja necessário para o Secure Field ficar
interativo" -- **não se sustenta** com esta evidência: ela mostra o
oposto, um caso onde ele ficou bloqueado o tempo todo e o CardForm
funcionou mesmo assim.

**Consequência para a CSP: não relaxar.** Como o script inline bloqueado
não está comprovado como causa de bloqueio nenhum, ele **não é
justificativa** para adicionar `'unsafe-inline'`, hash ou qualquer outra
exceção a `script-src`. A CSP desta mudança continua exatamente como
estava (sem hash, sem `unsafe-inline`, sem `unsafe-eval`) -- agora com um
motivo ainda mais forte para não mexer nela: não há mais nem a hipótese de
necessidade funcional sustentando um relaxamento futuro.

### Comparação DOM/CSS: diagnóstico x checkout real (produção)

Como o diagnóstico funcionou (evidência acima) mas havia relato de que o
**checkout publicado** da loja não aceita clique, foi feita uma comparação
controlada para isolar se a diferença está no DOM/CSS de produção. Com o
MESMO mock de SDK (iframe `about:blank` do tamanho calculado no instante de
`cardForm()`, idêntico ao já usado em
`tests/e2e/mercadopago-cardform-mount.spec.js`) montado dentro do
`index.html` REAL -- CSS de produção completo, header sticky,
`.form-panel::before`, todo o cascade do site --, em vez da página de
diagnóstico isolada:

| Verificação | `index.html` real (CSS de produção completo) |
|---|---|
| `cardForm()` monta exatamente 3 iframes | ✅ |
| cada iframe com largura/altura > 0 | ✅ |
| `elementFromPoint` no centro de cada iframe retorna o próprio iframe | ✅ |
| clique no iframe → `document.activeElement` é o iframe | ✅ |
| `.form-panel::before` intercepta o clique | ❌ Não -- já tem `pointer-events: none` explícito |
| alternar Pix→cartão→Pix→cartão duplica iframes/instâncias | ❌ Não -- 1 `cardForm()`, 1 iframe por campo |

**Conclusão: o DOM/CSS de produção não bloqueia o CardForm.** Quando o SDK
consegue montar um iframe de verdade (do tamanho/posição certos), o layout
completo de produção deixa esse iframe clicável e focável -- igual ao
comportamento da página de diagnóstico isolada. Essa prova foi fixada como
regressão automática em
`tests/e2e/mercadopago-cardform-production-dom.spec.js` (roda nos projetos
`desktop-chromium` e `mobile-chromium` do `playwright.config.js`): se uma
mudança futura de CSS introduzir um overlay/`pointer-events`/`z-index` que
cubra os campos, esses testes quebram.

**O que essa comparação NÃO prova:** o mock só reproduz a mecânica de um
iframe (tamanho, posição, DOM) -- não o conteúdo interno de um iframe do
SDK real. Continua sem responder por que o **checkout publicado**
especificamente não aceitou clique, já que (a) o teste manual com
`mp-csp-diagnostico.html` funcionou com o SDK real, e (b) esta comparação
mostra que o DOM/CSS de produção não é a causa. A lista abaixo enumera o
que seria necessário verificar para achar essa diferença -- itens que este
ambiente não consegue checar sozinho por não ter rede real para o site
publicado nem para `sdk.mercadopago.com` (confirmado de novo:
`curl https://www.misticaesotericos.com.br` e
`curl https://sdk.mercadopago.com/js/v2` retornam `CONNECT tunnel failed,
403` neste sandbox):

| O que comparar | Diagnóstico (`mp-csp-diagnostico.html`, funcionou) | Checkout publicado (não aceitou clique) | Como verificar |
|---|---|---|---|
| Public Key efetivamente usada | Digitada manualmente na página (sandbox) | Vem de `/api/payments/mercadopago/config` → `backend/mercadopago_flags.py::public_key_mercadopago()` (env `MERCADO_PAGO_PUBLIC_KEY` do servidor) | Comparar os dois valores; conferir se a key do publicado é sandbox ou produção |
| `trackingDisabled` | `true` (hardcoded no `mp-csp-diagnostico.js`) | `true` só se o checkout publicado estiver rodando o `v2-mercadopago-checkout.js` **desta mudança** (commit `3354122` em diante) | Ver items de versão/cache abaixo |
| Versão/conteúdo de `v2-mercadopago-checkout.js` carregado | Arquivo local, sempre o do commit atual | Depende do que o CDN/GitHub Pages está servindo | `curl` o arquivo publicado e comparar com `git show HEAD:v2-mercadopago-checkout.js`, ou ver o Console: a query string `?v=20260718-cartao-mercadopago` (cache-busting) precisa bater com a do HTML publicado |
| Cache/CDN/GitHub Pages | N/A (servido local) | GitHub Pages pode servir uma versão em cache até o CDN expirar | Recarregar com "disable cache" no DevTools e conferir o header `Age`/`Last-Modified` da resposta |
| Commit realmente publicado | N/A | Precisa bater com o HEAD desta análise | Conferir a Action `deploy-pages.yml` mais recente com sucesso e o SHA publicado |
| Instâncias de `MercadoPago`/`cardForm()` | 1 de cada (clique manual único no botão "Montar") | Deveria ser 1 de cada (guarda de remontagem em `v2-mercadopago-checkout.js`, coberta por `mercadopago-cardform-mount.spec.js` e pelo novo `mercadopago-cardform-production-dom.spec.js`) | `window.MercadoPago` sobrescrito mais de uma vez? Múltiplos listeners de clique no botão Pix/Cartão? |
| Chamadas de mount/unmount | 1 mount, sem unmount (nunca alternou) | Depende de quantas vezes o cliente alternou Pix↔Cartão antes de reportar o problema | Instrumentar temporariamente (`console.count`) ou usar o Network/Performance tab |
| Erros de `onError` | N/A -- `cardForm()` neste projeto não define callback `onError` (só `onFormMounted`, `onInstallmentsReceived`, `onSubmit`, `onFetching` -- ver `v2-mercadopago-checkout.js`) | Mesmo -- nenhum `onError` capturado hoje | Isso é um ponto cego real: se o SDK sinalizar erro por um canal que não escutamos, não aparece em lugar nenhum do nosso código |
| Resposta de `/api/payments/mercadopago/config` | Mockada/pública, `enabled:true` | Precisa ser lida diretamente (Network tab) no domínio publicado | Comparar `enabled`/`public_key` retornados |
| Estado de `MERCADO_PAGO_ENABLED` | N/A | Se o checkout publicado mostra o botão "Cartão de crédito", `MERCADO_PAGO_ENABLED` **já está `true` nesse ambiente** (senão `iniciar()` mantém o botão `hidden` -- ver `v2-mercadopago-checkout.js`) | Confirmar com quem administra o deploy qual env está configurado onde; **este repositório não muda isso** (`.env.example` continua `false`) |
| Seletores enviados ao `cardForm()` | `form-checkout__cardNumber` etc. (nomes do README oficial) | `mpCardNumber`/`mpExpirationDate`/`mpSecurityCode` (ver `v2-mercadopago-checkout.js`) -- nomes diferentes, mas isso é só rotulagem, não deveria mudar comportamento | Comparar a config capturada via `window.__mpConfigsCapturados` (mesmo padrão dos testes) no publicado |
| Os 3 iframes existem no publicado | Sim (evidência manual) | Não verificado nesta mudança -- precisa de alguém abrir o DevTools no site publicado | `document.querySelectorAll('#mpCardNumber iframe, #mpExpirationDate iframe, #mpSecurityCode iframe').length` deveria ser 3 |
| Geometria/`elementFromPoint` no publicado | ✅ (evidência manual) | Não verificado nesta mudança | Mesmo script do checklist de `mp-csp-diagnostico.js`, rodado no publicado |

**Nenhuma correção foi implementada a partir desta tabela.** Sem uma
diferença concreta identificada entre o diagnóstico (que funcionou) e o
checkout publicado (que não aceitou clique), qualquer mudança de código
seria um chute. O próximo passo é alguém com acesso ao site publicado
preencher a coluna "Checkout publicado" acima -- a origem mais provável,
dado que o diagnóstico já provou que o SDK real funciona e esta seção já
provou que o DOM/CSS de produção não bloqueia, é a linha **Public
Key**, **versão publicada de `v2-mercadopago-checkout.js`** ou **cache/CDN
servindo uma versão antiga** -- mas isso precisa ser confirmado, não
presumido.

**Card continua não homologado.** `MERCADO_PAGO_ENABLED` não foi alterado
por este repositório (continua `false` em `.env.example` e
`backend/mercadopago_flags.py`); se o ambiente publicado tem a flag ligada
para o teste manual acima, isso é uma decisão de infraestrutura fora deste
PR.

### Por que `img-src` inclui `https:` (qualquer origem HTTPS)

O cadastro de produto (`backend/product_routes.py::_validar_url_https`)
aceita **qualquer URL HTTPS** como imagem principal/galeria — não só do
nosso domínio ou de um CDN fixo. Isso é intencional (o operador da loja
pode apontar para a imagem de um fornecedor, uma CDN própria configurada
depois via `PRODUCT_IMAGES_PUBLIC_BASE_URL`, etc.), então não existe uma
lista fechada de domínios de imagem para enumerar em `img-src`. Como o
navegador só *carrega* a imagem (não executa nada a partir dela),
autorizar todo `https:` em `img-src` é o mesmo tipo de troca que outros
sites com conteúdo gerado por operador/usuário fazem — o risco real
(vazamento de referrer/cookie para um host de imagem) já é mitigado por
`Referrer-Policy: strict-origin-when-cross-origin` em toda página.

## Sem `unsafe-inline` em nenhuma diretiva

Nenhuma página pública tem `onclick=`/`onerror=`/`style=""` inline, nem
`<script>`/`<style>` sem `src`/`href` (auditoria completa desta mudança).
Onde existiam:

- **`style=""` fixo** (ex.: badge posicionado in-line em `produto-page.js`,
  fallback de imagem escondido por padrão em `achados-misticos.js`) →
  virou uma classe CSS dedicada.
- **`style=""` com valor dinâmico** (imagem de capa/barra de progresso em
  `escola-curso.js`/`escola.js`, calculadas a partir da API) → o valor
  passou a viajar num atributo `data-*` (URL/percentual) e é aplicado via
  `elemento.style.propriedade = valor` (CSSOM) logo depois do `innerHTML`.
  CSP restringe o atributo `style=""` vindo de HTML/`setAttribute`, **não**
  a manipulação de `element.style` via JavaScript — por isso essa técnica
  não precisa de `'unsafe-inline'`.
- **`<style>`/`<script>` inline** (`painel-operacional.html`, ~250 linhas
  de painel administrativo mobile; `painel/index.html`, redirecionamento)
  → viraram arquivos externos (`painel-operacional.css`/`.js`,
  `painel/redirect.css`).

Por isso `style-src`, assim como `script-src`, **não** precisa de
`'unsafe-inline'` nem de hash/nonce em massa.

## Handlers inline removidos (`onclick=`/`onerror=`)

Antes desta mudança, várias páginas geravam HTML com `onclick="addToCart(...)"`,
`onerror="this.src='...'"` etc. — inline event handlers, que exigiriam
`'unsafe-inline'` em `script-src` para continuar funcionando. Foram
substituídos por atributos `data-*` + delegação de eventos central:

- `app.js`: um único listener de `click` no `document` cobre
  `data-add-to-cart`, `data-buy-whatsapp`, `data-toggle-desc`,
  `data-remove-from-cart`, `data-inspect-product`, `data-close-inspector`
  (usado por `app.js` e `v2-product-inspector.js`, que compartilham as
  mesmas funções globais). Um listener de `error` (capture, já que `error`
  em `<img>` não borbulha) cobre `data-fallback-src` (troca o `src`) e
  `data-fallback-hide` (esconde a imagem e mostra o próximo irmão).
- `achados-misticos.js`, `escola.js` (cobre também
  `escola-incensos-catalog.js` e `escola-medicinas-floresta-catalog.js`,
  carregados na mesma página): listeners locais equivalentes, já que essas
  páginas não carregam `app.js`.
- `painel/index.html`: o redirecionamento de uma linha virou
  `painel/redirect.js` (script externo).

Nenhuma lógica de negócio mudou — só a forma como o clique/erro é
conectado à mesma função que já existia.

## Correção de contraste: Secure Fields e campo de Parcelas (visual, não CSP)

Depois de confirmado que os Secure Fields aceitam clique/foco/digitação no
checkout publicado (ver seção acima), foi reportado um problema visual
separado: o texto digitado em Número do cartão, Validade e CVV ficava
quase invisível sobre o fundo escuro, e o campo "Parcelas" aparecia como
uma faixa clara destoante do tema. **Isso não é CSP** -- CSP não controla
cor de texto/fundo de elemento nenhum; ficou registrado aqui só porque é o
mesmo componente (CardForm) já documentado neste arquivo.

**Causa confirmada** (duas, ambas em CSS/JS do frontend, nenhuma no
backend nem na CSP):

1. `.mp-secure-field` (o `<div>` que envolve cada iframe de Secure Field)
   dependia de `@media (prefers-color-scheme: dark)` -- o tema do
   sistema operacional do visitante, não o tema do site (que é sempre
   escuro, em todo o resto do site, sem nenhum outro uso de
   `prefers-color-scheme`). Com o SO em modo claro, caía no fundo branco
   fixo (`background: #fff`) e numa borda clara vinda de
   `var(--border, #d8d0ea)` -- `--border` não existe em `v2.css` (só em
   `styles.css`, que `index.html` nem carrega), então o fallback claro
   `#d8d0ea` sempre valia. Com o SO em modo escuro, o campo usava o fundo
   escuro certo, mas o texto DIGITADO dentro do iframe nunca teve cor
   definida (item 2) -- daí "texto escuro quase invisível sobre fundo
   escuro".
2. `cardForm()` nunca passava a opção `style` documentada pelo SDK (ver
   [`fields.md#style`](https://github.com/mercadopago/sdk-js/blob/main/docs/fields.md#style))
   para `cardNumber`/`expirationDate`/`securityCode` -- o Secure Field
   usava a cor de texto padrão do próprio Mercado Pago, nunca ajustada ao
   tema da Mística.
3. (Parcelas) `<select id="mpInstallments">` nunca teve CSS -- `v2.css`
   só estiliza `input, textarea` (não `select`), então o navegador usa o
   combo box nativo (claro na maioria dos navegadores/SOs).

Comprovado com screenshot antes/depois (`index.html` real, CardForm
mockado do mesmo jeito que
`tests/e2e/mercadopago-cardform-production-dom.spec.js`, sem tocar rede):
antes, os 3 campos e o seletor de parcelas aparecem como retângulos
brancos sólidos sobre o checkout escuro; depois, os mesmos elementos usam
o mesmo fundo escuro com borda dourada sutil dos demais campos do
formulário.

**Correção (mínima, só nestes dois arquivos):**

- `v2-mercadopago-checkout.js`: adiciona `MP_SECURE_FIELD_STYLE` (`color:
  "#F7E7BE"`, `placeholderColor: "rgba(247, 231, 190, 0.55)"`, `fontSize:
  "16px"`, `fontWeight: "500"`, `fontFamily: "Inter, system-ui,
  sans-serif"`) e passa `style: MP_SECURE_FIELD_STYLE` para os três
  campos (`cardNumber`, `expirationDate`, `securityCode`) dentro de
  `cardForm({ form: {...} })`. Só as propriedades documentadas em
  `fields.md#style` foram usadas -- **não existe `backgroundColor` nem
  estados `:focus`/`:valid`/`:invalid` nessa API** (o iframe é de outra
  origem; CSS do nosso documento não alcança o conteúdo dele). Pedidos do
  ticket que dependiam dessas propriedades (fundo interno "transparente"
  via API, caret e estados focus/valid/invalid controlados via `style`)
  não são possíveis pela API oficial -- o que dá para controlar do nosso
  lado é o fundo/borda do wrapper (`.mp-secure-field`, item abaixo), não o
  interior do iframe.
- `v2-mercadopago-checkout.css`: `.mp-secure-field` passa a usar sempre
  `background: rgba(0, 0, 0, .28)` e `border-color: var(--line, ...)` (o
  mesmo tratamento visual dos demais `<input>` do checkout, ver `v2.css`)
  -- removido o `@media (prefers-color-scheme: dark)`, já que o tema não
  depende do SO em nenhum outro lugar do site. Adicionada uma regra
  `.card-panel select` com o mesmo fundo/borda/cor de texto, cobrindo o
  `<select id="mpInstallments">` (parcelas) -- `#mpIssuer` e
  `#mpIdentificationType` também são `<select>` dentro de `.card-panel`,
  mas ambos ficam `hidden` no HTML, então a regra não muda nada visível
  neles.

**Nada mais mudou**: CSP (`<meta http-equiv="Content-Security-Policy">`),
backend, Pix, webhook, `MERCADO_PAGO_ENABLED`, seletores dos campos
(`id`s inalterados), fluxo de pagamento e lifecycle de mount/unmount
continuam exatamente como estavam.

**Testes**: `tests/mercadopago-cardform-config.test.js` ganhou dois testes
-- um confirma que os três campos recebem exatamente o `style` esperado
(e que `color`/`placeholderColor` são diferentes, e que `backgroundColor`
não é enviado -- não é suportado), outro confirma estaticamente que o CSS
não depende mais de `prefers-color-scheme` nem de `--border`, e que
`.mp-secure-field`/`.card-panel select` usam o fundo escuro esperado.
`tests/e2e/mercadopago-cardform-mount.spec.js` ganhou o mesmo teste de
`style` via Playwright (fixture com Chromium real). Os testes já
existentes de montagem/DOM/CSP (`mercadopago-cardform-mount.spec.js`,
`mercadopago-cardform-production-dom.spec.js`, `csp-mercadopago-
cardform.spec.js`, `csp.spec.js`) continuam passando sem alteração --
confirma que a correção visual não afetou clique/foco/digitação, contagem
de iframes, nem a CSP.

## Testes

- `tests/test_csp_meta.py` (Python, sem navegador): confirma que as 23
  páginas públicas têm a meta CSP, sem `unsafe-eval`, sem curinga global,
  com `object-src 'none'` e `base-uri 'self'`, sem `unsafe-inline` em
  `script-src`, sem handler inline residual, sem `<script>` inline
  executável (JSON-LD é exceção válida — não é sujeito a `script-src`).
- `tests/e2e/csp.spec.js` (Playwright): abre `index.html` e `produto.html`
  com um Chromium real, captura eventos `securitypolicyviolation` e erros
  de console, adiciona um produto ao carrinho (exercitando a nova
  delegação de cliques) e confirma viewport mobile.
- `tests/e2e/csp-mercadopago-cardform.spec.js` (Playwright): confirma que
  `frame-src`/`connect-src` autorizam subdomínios `.com`/`.com.br` do
  Mercado Pago sem violação, e que um host de terceiro não relacionado
  continua bloqueado.
- `tests/e2e/mercadopago-cardform-mount.spec.js` (Playwright, com fixture
  dedicada e SDK mockado): confirma a mecânica de montagem dos 3 iframes de
  Secure Fields sem violação de CSP.
- `tests/e2e/csp-mercadopago-runtime-violations.spec.js` (Playwright, novo
  nesta correção): reproduz as 3 violações reais reportadas após a PR #365
  (atributo `style=""` inline no wrapper do Secure Field, `fetch` para
  `api.mercadolibre.com/tracks`) contra a CSP real de `index.html`,
  confirmando que a policy corrigida não as bloqueia mais -- e, ao mesmo
  tempo, que `<style>` injetado, `<script>` inline e hosts de terceiros
  fora da lista continuam bloqueados (garante que a correção não abriu mais
  do que o necessário). Escuta `document.addEventListener(
  "securitypolicyviolation", ...)` e falha se sobrar qualquer violação
  relacionada ao Mercado Pago.
- `tests/e2e/mercadopago-cardform-production-dom.spec.js` (Playwright,
  novo nesta correção, roda em `desktop-chromium` e `mobile-chromium`):
  regressão permanente que prova que o DOM/CSS COMPLETOS de produção
  (`index.html`, cascade real do site) não bloqueiam o CardForm --
  monta exatamente 3 iframes com o mesmo mock de SDK das fixtures,
  confirma largura/altura > 0, `elementFromPoint` retornando o próprio
  iframe, foco após clique, `.form-panel::before` com `pointer-events:
  none`, e ausência de duplicação ao alternar Pix↔cartão repetidamente.
  Ver seção "Comparação DOM/CSS: diagnóstico x checkout real (produção)".
- `tests/e2e/csp-diagnostico-tool.spec.js` (Playwright, novo nesta
  correção): testa o mecanismo de captura de
  `tests/manual/mp-csp-diagnostico.html` (ferramenta de homologação
  manual, não é página pública) com uma violação de CSP sintética --
  confirma que a tabela na tela recebe `effectiveDirective`/`sourceFile`/
  etc. e que nenhum termo sensível (cartão/CVV/token/CPF) aparece nela.
- `tests/mercadopago-cardform-config.test.js` (Node): além da checagem já
  existente de `iframe: true`, confirma que `new MercadoPago(publicKey,
  options)` recebe `trackingDisabled: true` e nunca recebe
  `advancedFraudPrevention` (mantém o default do SDK).
- `tests/test_csp_meta.py::test_csp_script_src_sem_hash_nao_validado`
  (novo nesta correção): confirma que `script-src` não contém nenhum hash
  `sha256-` -- trava a decisão de não adicionar o hash reportado sem
  confirmação de estabilidade (ver "Auditoria do script inline bloqueado
  (pós-#368)").
- `tests/test_seguranca_reforcada.py`: atualizado para os novos valores de
  `Permissions-Policy` (`payment=(self)`) e `Cross-Origin-Opener-Policy`
  (`same-origin-allow-popups`) da API.

## Cabeçalhos que a API já enviava (sem alteração de comportamento)

`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Cross-Origin-Resource-Policy: cross-origin`, `Origin-Agent-Cluster: ?1` e
`Strict-Transport-Security` (só sob HTTPS) já existiam em
`backend/main.py::cabecalhos_seguranca` antes desta mudança. Ajustados
nesta mudança: `Permissions-Policy` ganhou `payment=(self)` (era
`payment=()`) e `Cross-Origin-Opener-Policy` passou de `same-origin` para
`same-origin-allow-popups` (permite popups legítimos, ex.: um futuro OAuth
de terceiros, sem abrir mão do isolamento COOP).

No site público (GitHub Pages), **nenhum destes cabeçalhos HTTP pode ser
configurado** — só `Content-Security-Policy` e `Referrer-Policy` têm
equivalente via `<meta>` (este último adicionado como
`<meta name="referrer" content="strict-origin-when-cross-origin">` em
todas as 24 páginas). `X-Content-Type-Options`, `Permissions-Policy`,
`Cross-Origin-Opener-Policy`/`Cross-Origin-Embedder-Policy` e
`Strict-Transport-Security` **não têm equivalente em meta tag** — não é
possível implementá-los no site público nesta hospedagem. HSTS, na
prática, já é aplicado automaticamente pela borda do GitHub Pages para
domínios customizados com HTTPS forçado (fora do nosso controle direto).

## Procedimento de manutenção (se o Mercado Pago mudar domínios)

1. Ativar `MERCADO_PAGO_ENABLED=true` num ambiente de teste/sandbox.
2. Abrir o checkout num navegador real com o DevTools aberto (aba Console
   + Network).
3. Qualquer chamada bloqueada pela CSP aparece no console como
   `Refused to ... because it violates the following Content Security
   Policy directive: ...`, com a origem exata bloqueada.
4. Adicionar **só o host exato** reportado à diretiva correspondente em
   todas as 24 páginas (o mesmo texto de política é replicado em todas —
   não há um arquivo único incluído, pois GitHub Pages não suporta
   includes/templates no HTML estático).
5. Repetir até o checkout completar sem nenhuma violação.
6. Rodar `pytest tests/test_csp_meta.py` e `npx playwright test tests/e2e/csp.spec.js`
   antes de publicar a mudança.

## Procedimento de homologação real do CardForm (obrigatório antes de `MERCADO_PAGO_ENABLED=true`)

Nenhum ambiente de desenvolvimento usado para preparar esta política tem
acesso de rede a `sdk.mercadopago.com` nem a `api.mercadolibre.com` — a
validação abaixo só pode ser feita num sandbox com acesso real à internet.
`tests/manual/mp-csp-diagnostico.html` automatiza a parte de captura do
passo 3 abaixo (sirva a pasta `tests/manual/` com um servidor HTTP local e
abra a página com a Public Key de teste) -- o restante (clique/digitação
reais, homologação com cartão de teste completo) continua manual.

1. Ativar `MERCADO_PAGO_ENABLED=true` e configurar a Public Key de
   **sandbox/teste** (nunca a de produção neste passo) no backend.
2. Abrir o checkout num navegador real (recarregar algumas vezes, em janela
   anônima e em pelo menos dois navegadores diferentes — hashes/scripts de
   terceiros podem variar por sessão/versão do SDK).
3. Console aberto: confirmar que as 3 violações originais deste ticket
   (`style-src` inline, `script-src` inline, `connect-src` para
   `api.mercadolibre.com/tracks`) não aparecem mais **exceto** a de
   `script-src` (deixada bloqueada de propósito — ver tabela acima). Se a
   violação de `script-src` persistir, confirmar no Console se ela vem
   rotulada como telemetria (`Could not send event`) — se sim, é esperada e
   não bloqueia o pagamento; qualquer outra violação de `script-src` deve
   ser investigada antes de prosseguir.
4. Rodar no Console:
   ```js
   document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content
   ```
   e conferir a aba Network (Response Headers) que nenhum header HTTP
   `Content-Security-Policy` divergente está sendo enviado — só a `<meta>`
   deve estar em vigor no site público.
5. Confirmar exatamente 1 iframe por campo seguro:
   ```js
   document.querySelectorAll("#mpCardNumber iframe").length     // 1
   document.querySelectorAll("#mpExpirationDate iframe").length // 1
   document.querySelectorAll("#mpSecurityCode iframe").length   // 1
   ```
6. Testar manualmente: clique e digitação em número/validade/CVV, BIN
   reconhecido (o SDK deve preencher a bandeira/emissor), parcelas
   carregando no seletor, e alternar Pix ↔ cartão várias vezes sem
   duplicar iframes.
7. Só depois de 3-6 passarem sem nenhuma violação inesperada e com um
   cartão de teste de verdade tokenizando com sucesso, considerar o
   CardForm homologado. `MERCADO_PAGO_ENABLED` permanece `false` em
   produção até essa homologação ser concluída.
8. Se `script-src` precisar ser relaxado (passo 3 acima falhar de forma
   não relacionada a telemetria), capturar o hash exato reportado pelo
   navegador (`sha256-...`) em pelo menos 3 recarregamentos/sessões
   diferentes; só adicionar o hash a `script-src-elem` se for **idêntico**
   em todas as tentativas. Nunca adicionar `'unsafe-inline'` a `script-src`
   como atalho.
