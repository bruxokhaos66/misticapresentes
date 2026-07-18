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

em cada página HTML pública (23 páginas — ver lista em
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
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
img-src 'self' data: blob: https:;
font-src 'self' data: https://fonts.gstatic.com;
connect-src 'self' https://api.misticaesotericos.com.br https://api.mercadopago.com https://sdk.mercadopago.com
            https://www.google-analytics.com https://analytics.google.com https://www.googletagmanager.com
            https://www.facebook.com https://connect.facebook.net;
frame-src https://www.youtube.com https://www.mercadopago.com;
worker-src 'self' blob:;
manifest-src 'self';
media-src 'self' blob: https://api.misticaesotericos.com.br;
upgrade-insecure-requests
```

## Por que cada origem externa está autorizada

| Origem | Diretiva | Motivo |
|---|---|---|
| `sdk.mercadopago.com` | script-src, connect-src | Carrega o SDK oficial `MercadoPago.js v2`, usado para tokenizar o cartão (CardForm) sem que os dados passem pelo nosso servidor. |
| `api.mercadopago.com` | connect-src | O próprio SDK, rodando no navegador, chama esta API do Mercado Pago diretamente para tokenizar o cartão, consultar bandeira/emissor e calcular parcelas — nunca é o nosso backend fazendo isso pelo cliente. |
| `www.mercadopago.com` | frame-src | Hospeda os campos seguros (iframes) do CardForm (número do cartão, validade, CVV) quando o SDK monta o formulário. |
| `api.misticaesotericos.com.br` | connect-src, media-src | Nossa própria API (catálogo, carrinho, pedidos, pagamentos, vídeos de curso). |
| `www.googletagmanager.com` | script-src, connect-src | Google Analytics (`gtag.js`), carregado só depois de consentimento explícito (LGPD, ver `consent.js`) e só se `gaMeasurementId` estiver configurado em `site-config.js` (hoje vazio = inativo). |
| `www.google-analytics.com`, `analytics.google.com` | connect-src | Endpoints de coleta do Google Analytics, usados pelo `gtag.js` acima. |
| `connect.facebook.net` | script-src, connect-src | Meta/Facebook Pixel (`fbevents.js`), mesma regra de consentimento e mesma flag hoje vazia (`metaPixelId`) do Analytics. |
| `www.facebook.com` | connect-src | Endpoint de tracking do Facebook Pixel. |
| `www.youtube.com` | frame-src | Vídeos de aula incorporados via `<iframe>` na Escola Mística (`escola-curso.js`). |
| `fonts.googleapis.com`, `fonts.gstatic.com` | style-src, font-src | Fonte Google (`Cinzel`/`Inter`) usada em todo o site. |

**Nenhuma dessas origens tem acesso a criar/consultar pagamentos com o
Access Token** — o Access Token nunca sai do backend (ver
`backend/mercadopago_flags.py`), então mesmo com `api.mercadopago.com`
liberado no `connect-src`, o navegador só consegue fazer as chamadas
públicas de tokenização que o SDK do Mercado Pago expõe para uso no
cliente (não há endpoint de criação de cobrança acessível sem o Access
Token, e o frontend nunca o possui).

## `style-src 'unsafe-inline'` — exceção documentada

O site tem `style=""` inline em alguns pontos (ex.: fallback de imagem
mostrando/escondendo elementos, `404.html`) e depende de CSS-in-JS simples
em poucos lugares. Removê-los todos exigiria uma refatoração maior, fora do
escopo desta mudança. Optamos por manter `'unsafe-inline'` **somente em
`style-src`**, nunca em `script-src`: CSS inline não executa JavaScript —
o pior cenário de um CSS-injection é desfiguração visual, não execução de
código arbitrário. `script-src` permanece estrito (sem `unsafe-inline`,
sem `unsafe-eval`) em todas as páginas.

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
todas as 23 páginas). `X-Content-Type-Options`, `Permissions-Policy`,
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
   todas as 23 páginas (o mesmo texto de política é replicado em todas —
   não há um arquivo único incluído, pois GitHub Pages não suporta
   includes/templates no HTML estático).
5. Repetir até o checkout completar sem nenhuma violação.
6. Rodar `pytest tests/test_csp_meta.py` e `npx playwright test tests/e2e/csp.spec.js`
   antes de publicar a mudança.
