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
img-src 'self' data: blob: https:;
font-src 'self' data: https://fonts.gstatic.com;
connect-src 'self' https://api.misticaesotericos.com.br https://*.mercadopago.com https://*.mercadopago.com.br
            https://www.google-analytics.com https://analytics.google.com https://www.googletagmanager.com
            https://www.facebook.com https://connect.facebook.net;
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
