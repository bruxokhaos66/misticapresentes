# Auditoria Profunda — Site Mística Esotéricos / Mística Presentes

> Data: 12/07/2026 · Branch: `claude/mistica-web-audit-nsijj4`
> Escopo: repositório `bruxokhaos66/misticapresentes` (site estático + API FastAPI + app desktop).
> Natureza: **diagnóstico baseado em evidências**. Nenhuma alteração de código foi feita. Onde algo não pôde ser verificado, está dito explicitamente.

---

## 1. Resumo executivo

O projeto é um **site estático** (HTML/CSS/JS puro, publicado no GitHub Pages sob domínio próprio) acoplado a uma **API FastAPI** (Render) que cuida de catálogo, pedidos, Pix, painel administrativo, avaliações, campanhas e da **Escola Mística** (cursos pagos com área do aluno). Há também um app desktop em Python (`mistica_presentes.py`, ~175 KB) e apps móveis, que compartilham o mesmo repositório.

A **qualidade da engenharia de segurança da API é acima da média** para um projeto deste porte: preços e estoque são recalculados no servidor (o navegador não define valor), baixa de estoque é atômica, há idempotência no checkout, sessões em cookie `HttpOnly`, verificação de origem contra CSRF, rate limiting com bloqueio progressivo no login, segredos nunca vão ao navegador, e o painel administrativo é separado do bundle público (há teste E2E que prova isso). A suíte de testes existe e **passa**: 111 testes Python e 24/24 testes Playwright (após uma correção de flakiness de ambiente, ver Fase 8).

O risco dominante **não é de código, é de infraestrutura**: a API roda no **Render plano Free, sem Persistent Disk**, com o banco em **SQLite gravado em filesystem efêmero**. O próprio `docs/RENDER_FREE_API_PAINEL_MOBILE.md` admite que "qualquer SQLite gravado no filesystem da API pode voltar vazio" após reinício/redeploy/sleep. Isso significa **perda potencial de pedidos, cadastros de alunos, liberação de cursos pagos, avaliações e campanhas** — os dados comerciais mais importantes do negócio. É o item que mais ameaça a confiança e a operação.

No front, o site está bem estruturado e com boa base de SEO/acessibilidade (Lighthouse: SEO 100, Acessibilidade 96–100), mas **performance é o gargalo comercial**: LCP de 4,8 s na home e um **CLS de 0,399 na página de produto** (acima de 5× o limite bom de 0,1), além de ~7 MB de imagens PNG pesadas que são publicadas no artefato mas nunca referenciadas. Há também uma **inconsistência de URL de API** (parte dos scripts aponta para `misticapresentes-api.onrender.com`, o resto para `api.misticaesotericos.com.br`), que é uma bomba-relógio de manutenção.

---

## 2. Mapa da arquitetura

```
                    ┌──────────────────────────────────────────────┐
   Visitante  ───▶  │  GitHub Pages (domínio próprio, CNAME)        │
   (desktop/        │  Site estático: index.html, produto.html,    │
    mobile)         │  kit.html, escola.html, /incensos, /cristais…│
                    │  JS público: app.js, mobile-sync.js,         │
                    │  v2-commerce.js, site-production-guard.js,   │
                    │  seo-site.js, consent/analytics, escola.js   │
                    └───────────────┬──────────────────────────────┘
                                    │ fetch() cross-site (CORS + cookies)
                                    ▼
                    ┌──────────────────────────────────────────────┐
   Admin/Aluno ───▶ │  FastAPI (Render Free)  backend/main.py      │
                    │  Routers: product, order_status, payment,    │
                    │  site_stock, upload, course, aluno_auth,     │
                    │  review, campaign, user_sync, backup, system │
                    │  Auth: cookie HttpOnly (painel + aluno)      │
                    │  + chave estática servidor-a-servidor        │
                    └───────────────┬──────────────────────────────┘
                                    ▼
                    ┌──────────────────────────────────────────────┐
                    │  SQLite (⚠ filesystem EFÊMERO no Free)       │
                    │  produtos, pedidos, pedidos_itens,           │
                    │  pagamentos, alunos, alunos_cursos,          │
                    │  avaliacoes_produtos, campanhas, painel_*    │
                    └──────────────────────────────────────────────┘

   Fora do site público (mesmo repo): app desktop Python
   (mistica_presentes.py, services/), api/ (2ª app FastAPI legada),
   mobile_android/, installer/, scripts de build Windows.
```

### Frameworks e bibliotecas
- **Frontend:** HTML/CSS/JS "vanilla", sem framework nem bundler no runtime. Build com **esbuild** só para minificar (`scripts/minify-assets.mjs` → `dist-site/`).
- **Backend:** **FastAPI + Uvicorn**, **SQLite** (`sqlite3` puro, sem ORM), **Pillow** (validação de imagem), PBKDF2-HMAC-SHA256 (senhas). `render.yaml`: `uvicorn backend.main:app`.
- **Testes:** `pytest` (111 testes), **Playwright** (E2E, `tests/e2e/`), **Lighthouse CI** (`.lighthouserc.json`).
- **CI/CD:** 17 workflows em `.github/workflows/` (deploy Pages, auditoria semanal, backup diário, healthcheck, testes API/Playwright, builds Windows/Android).

### Autenticação
Dois domínios de sessão independentes, ambos por cookie `HttpOnly`:
- **Painel/admin** (`mistica_painel_sessao`): `backend/panel_sessions.py`. Expiração absoluta 12 h + inatividade 30 min (sliding). `SameSite=Lax`, `Secure` em HTTPS. Login em `POST /api/auth/login` (`backend/user_sync_routes.py:240`), com rate limit + bloqueio progressivo.
- **Aluno da Escola** (`mistica_aluno_sessao`): `backend/aluno_auth.py`. `SameSite=None`+`Secure` (cross-site real, site ≠ API). Senha criada via link de convite de uso único após confirmação do pagamento.
- **Integração servidor-a-servidor:** header `X-Mistica-Api-Key`/`X-Mistica-Sync-Key`, segredo só no servidor.

### Principais fluxos do usuário
1. **Compra de produto:** catálogo (`/api/produtos`, público) → carrinho (localStorage) → "Gerar Pix" → `POST /api/checkout/pedidos` (público, sem segredo) → backend recalcula preço, **reserva estoque**, gera Pix → cliente paga → admin confirma no painel (ou webhook Pix) → baixa de estoque definitiva.
2. **Curso pago:** `escola.html` → "Comprar" → `POST /api/checkout/cursos` (preço vem do catálogo do servidor) → Pix → admin confirma → gera link de convite → aluno cria senha (`/api/alunos/definir-senha`) → acesso liberado (`alunos_cursos`) → conteúdo protegido por sessão de aluno.

---

## 3. Estado atual do projeto

| Área | Estado | Observação |
|---|---|---|
| Testes Python (`pytest`) | ✅ 111 passam | Precisou atualizar `cryptography` no ambiente (ver Fase 8) |
| Testes E2E (Playwright) | ✅ 24/24 passam | 1 falha inicial foi timeout de ambiente, não do código |
| Build do site (`minify-assets.mjs`) | ✅ gera `dist-site/` (29 MB) | Inclui ~7 MB de PNG não referenciados |
| `npm audit --omit=dev` | ✅ 0 vulnerabilidades | |
| Lighthouse home | Perf **63**, A11y 96, BP 96, SEO 100 | LCP 4,8 s |
| Lighthouse produto | Perf **65**, A11y 100, BP 96, SEO 100 | **CLS 0,399** |
| Separação admin/público | ✅ garantida por teste | `tests/e2e/admin-separation.spec.js` |
| Persistência de dados (produção) | ⚠️ **frágil** | SQLite em disco efêmero no Render Free |

---

## 4. Problemas críticos (P0)

### P0-1 — Banco SQLite em disco efêmero: perda de dados em produção
- **Severidade:** P0 · **Categoria:** estabilidade / perda de dados / infraestrutura
- **Evidência:** `render.yaml:5` → `plan: free` e **nenhum `disk:` (Persistent Disk) declarado**. `config.py:82-108` (`carregar_db_path`) usa por padrão `~/Documents/mistica_gestao_v20.db` quando `MISTICA_DB_PATH` não está setada. `docs/RENDER_FREE_API_PAINEL_MOBILE.md:5`: *"o plano Free nao oferece Persistent Disk, qualquer SQLite gravado no filesystem da API pode voltar vazio depois desses eventos"*.
- **Impacto:** todo redeploy, sleep (o Free hiberna após inatividade) ou reinício pode **zerar** `pedidos`, `alunos`, `alunos_cursos`, `avaliacoes_produtos`, `campanhas`, `pagamentos`. Um aluno que pagou um curso **perde o acesso**; pedidos somem; avaliações e histórico se perdem. É o maior risco de confiança do negócio.
- **Reprodução:** fazer um pedido/cadastro → forçar redeploy da API no Render → consultar `/api/pedidos` (com sessão): registros anteriores ao redeploy desaparecem.
- **Recomendação:** migrar para **Render pago com Persistent Disk** e `MISTICA_DB_PATH=/data/mistica_gestao_v20.db`, **ou** migrar para Postgres gerenciado (o `DATABASE_URL` já está previsto em `config.py:17` mas não implementado). Até lá, garantir que o **backup diário** (`.github/workflows/backup-diario.yml`) esteja de fato configurado com `MISTICA_SITE_API_KEY` nos secrets — hoje ele falha silenciosamente se o segredo faltar.
- **Esforço:** médio (config + validação) · **Risco da alteração:** baixo · **Teste de validação:** após configurar disco, fazer pedido → redeploy → confirmar que o pedido persiste via `GET /api/pedidos`.

> Observação: **não há evidência de que `MISTICA_DB_PATH` esteja ou não configurado no painel do Render** (variáveis de ambiente de produção não estão no repositório). Se já estiver apontando para um disco persistente, o P0 cai para "verificar". Isso **não pôde ser confirmado localmente** — precisa ser checado no dashboard do Render.

---

## 5. Problemas altos (P1)

### P1-1 — CLS de 0,399 na página de produto
- **Severidade:** P1 · **Categoria:** performance / UX / conversão
- **Evidência:** Lighthouse local em `produto.html?id=pedra-energetica` → `cumulative-layout-shift: 0.399` (bom ≤ 0,1). Causa: `produto-page.js:211` só renderiza o conteúdo em `window.load` + `setTimeout(init, 400)`, e a imagem principal (`produto-page.js:129`) não tem `width`/`height` reservados. O layout "pula" ~0,4 s depois do carregamento.
- **Impacto:** experiência ruim (o usuário clica onde o conteúdo estava e ele já se moveu), penalização de ranking (Core Web Vitals) e queda de conversão na página que mais deveria vender.
- **Reprodução:** abrir `produto.html?id=<id>` e observar o salto de layout ao renderizar.
- **Recomendação:** reservar altura mínima no `#produtoPageRoot`, definir `width`/`height` (ou `aspect-ratio`) na `.product-page-photo`, e remover o atraso artificial de 400 ms (renderizar assim que `products` estiver disponível). Idem para os cards da home.
- **Esforço:** pequeno · **Risco:** baixo · **Teste:** rodar `lhci autorun` e confirmar CLS < 0,1.

### P1-2 — Inconsistência de URL da API entre scripts
- **Severidade:** P1 · **Categoria:** bug de configuração / risco de ambiente
- **Evidência:** `escola.js:2`, `v2-courses.js:14` e `v2-admin-products.js:2` fixam `https://misticapresentes-api.onrender.com`, enquanto `site-config.js:4` e todos os demais scripts usam `https://api.misticaesotericos.com.br`. Grep confirma os dois grupos.
- **Impacto:** (a) a Escola e o admin de cursos falam com um host diferente do resto; **cookies de sessão do aluno** são gravados no domínio `onrender.com` e não no `api.` — se um dia o domínio `api.` deixar de apontar para o mesmo backend, ou o CORS mudar, a área do aluno quebra de forma difícil de diagnosticar; (b) qualquer troca de provedor exige mexer em N arquivos; (c) o `onrender.com` expõe o provedor de hospedagem.
- **Reprodução:** inspecionar as requisições de rede em `escola.html` vs `index.html`.
- **Recomendação:** centralizar **um único** `apiBaseUrl` em `site-config.js` e fazer `escola.js`/`v2-courses.js`/`v2-admin-products.js` lerem dele, como os outros já fazem.
- **Esforço:** pequeno · **Risco:** baixo (precisa confirmar que `api.misticaesotericos.com.br` responde igual ao `onrender.com`) · **Teste:** E2E de compra de curso + login de aluno após a troca.

### P1-3 — Rate limiting apenas em memória (não vale entre workers/instâncias)
- **Severidade:** P1 · **Categoria:** segurança / abuso
- **Evidência:** `backend/rate_limit.py:8-9` usa dicionário em memória de processo; o próprio docstring avisa que "se o serviço passar a rodar com múltiplos workers/instâncias, trocar por Redis". O checkout público (`/api/checkout/pedidos`), avaliações e login dependem dele.
- **Impacto:** com mais de um worker Uvicorn (comum em produção), o limite real fica multiplicado pelo nº de workers; um atacante pode gerar muitos pedidos/avaliações/tentativas. O **bloqueio de login** em si é persistido no banco (`painel_login_tentativas`), então esse está protegido; o risco maior é o abuso de endpoints públicos de escrita.
- **Recomendação:** confirmar que hoje roda com **1 worker** (mitigação atual). Ao escalar, mover o rate limit para armazenamento compartilhado (Redis) ou persistir contadores no SQLite como já é feito no login.
- **Esforço:** médio · **Risco:** baixo · **Teste:** `tests/fase1_security_test.py` já cobre o caso de 1 processo.

---

## 6. Problemas médios (P2)

### P2-1 — Ausência de cabeçalhos de segurança HTTP
- **Evidência:** `backend/main.py` só adiciona `CORSMiddleware` (`:86`); não há `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`. O site estático (GitHub Pages) também não define CSP.
- **Impacto:** menos defesa em profundidade contra XSS, clickjacking e sniffing. Não é uma falha explorável direta (as respostas da API são JSON), mas é higiene esperada e alguns scanners de confiança/PCI apontam.
- **Recomendação:** middleware simples adicionando os headers na API; para o site estático, avaliar `<meta http-equiv>` de CSP ou mover para um proxy que injete headers. Começar com `X-Content-Type-Options: nosniff` e `Referrer-Policy: strict-origin-when-cross-origin` (baixo risco).
- **Esforço:** pequeno · **Risco:** baixo (CSP restritiva pode quebrar Google Fonts/analytics — testar).

### P2-2 — LCP de 4,8 s na home
- **Evidência:** Lighthouse home → LCP 4,8 s / FCP 3,0 s / TTI 4,9 s. Fatores: fontes Google bloqueando render (`index.html:23-25`), hero `isis-hero.webp` (452 KB) e **~13 scripts `defer`** carregados no `<head>` (`index.html:37-49`).
- **Impacto:** parte dos visitantes de anúncio/Instagram (móvel, 3G/4G) abandona antes de ver a primeira dobra.
- **Recomendação:** `preload` da imagem LCP, `font-display: swap` já vem no link do Google mas considerar auto-hospedar as fontes; adiar scripts não críticos (analytics, player, inspector) para depois do `load`; comprimir a hero. **Nota:** parte do "render-blocking" e "text-compression" do relatório é artefato do `python -m http.server` local (sem gzip); o GitHub Pages serve com compressão, então o número real em produção é melhor. Ainda assim LCP alto é real.
- **Esforço:** médio · **Risco:** baixo.

### P2-3 — ~7 MB de imagens não referenciadas publicadas no artefato
- **Evidência:** `dist-site/` tem `assets/ChatGPT Image 11 de jul… .png` (2,8 MB), `assets/isis-humana-xamanica-03-produtos.png` (2,3 MB) e `assets/xamanicaintencao.png` (2,0 MB). O grep mostra que só a variante **`.webp`** de `xamanicaintencao` é referenciada (`v2-kits-banner.css:26`); os `.png` e o nome "ChatGPT Image…" não são usados por nenhum HTML/CSS/JS.
- **Impacto:** artefato de deploy inflado, custo de banda, e o arquivo com nome "ChatGPT Image…" passa impressão amadora se alguém acessar a URL direto.
- **Recomendação:** excluir os PNGs órfãos do repositório (ou ao menos do build via `minify-assets.mjs`). Confirmar antes que nenhuma página externa/rede social use as URLs.
- **Esforço:** pequeno · **Risco:** baixo.

### P2-4 — MP3 de ambiente de 9,2 MB carregado sem streaming otimizado
- **Evidência:** `assets/audio/xamanico-ambiente.mp3` = 9,2 MB, servido como arquivo estático e referenciado por `v2-shamanic-player.js:26`.
- **Impacto:** quem der play baixa 9 MB; em celular no plano de dados, é pesado. Não bloqueia o carregamento inicial (só toca sob clique), por isso é P2 e não P1.
- **Recomendação:** reduzir bitrate (o commit `20260710-audio-128kbps` sugere que já houve tentativa), servir por faixa menor, ou hospedar em CDN/Drive (o backend já suporta links de áudio).
- **Esforço:** pequeno · **Risco:** baixo.

### P2-5 — `/api/site/acessos` exige chave de API mas nenhum script do site a chama
- **Evidência:** `backend/site_stock_routes.py:511` (`registrar_acesso_site`) exige `validar_site_api_key`; grep não encontra nenhum `fetch` para `site/acessos` no JS público. Ou seja, a métrica de acessos do site **nunca é populada pelo navegador** (o navegador não tem a chave, corretamente).
- **Impacto:** o "resumo de acessos" do painel (`/api/site/acessos/resumo`) mostra números vazios/irreais; código morto ou expectativa não cumprida.
- **Recomendação:** decidir o modelo — ou registrar acesso por um endpoint público sem segredo (com rate limit), ou remover a feature e confiar no Google Analytics (que já existe via `analytics.js`).
- **Esforço:** pequeno · **Risco:** baixo.

### P2-6 — Duas aplicações FastAPI coexistindo (`api/` legada vs `backend/`)
- **Evidência:** `api/main.py` é uma segunda app FastAPI (com `@app.on_event` deprecado, WebSocket, painel próprio) além de `backend/main.py` (a que o `render.yaml` publica). Só `tests/api_smoke_test.py` e `scripts/auditoria_operacional.py` referenciam `api/`.
- **Impacto:** confusão de manutenção, superfície dupla, risco de alguém corrigir no lugar errado. Não afeta produção (só `backend/` é servido).
- **Recomendação:** confirmar que `api/` é do app desktop/rede local; se sim, documentar claramente ou isolar em subpasta separada do site.
- **Esforço:** médio · **Risco:** médio (precisa confirmar que nada em produção usa).

### P2-7 — Avaliações publicadas sem moderação
- **Evidência:** `backend/review_routes.py:70` insere com `aprovado=1` direto. Há honeypot no front (`product-reviews.js`) e rate limit (5/5 min), mas o texto vai ao ar imediatamente.
- **Impacto:** spam/ofensa aparece publicamente até alguém remover. XSS está mitigado (o front escapa via `escapeHtml`), então é risco de conteúdo, não de segurança.
- **Recomendação:** inserir com `aprovado=0` e ter uma fila de aprovação no painel, ou pelo menos filtro de palavrões.
- **Esforço:** médio · **Risco:** baixo.

### P2-8 — Descontos de campanha não são aplicados no preço do pedido
- **Evidência:** `campaigns-banner.js` só exibe o cupom; o checkout (`site_stock_routes.py::recalcular_venda_site`) recalcula **sempre** pelo preço cheio do produto, sem considerar cupom/campanha. `campaign_routes.py` gerencia campanhas mas não há aplicação de desconto no total.
- **Impacto:** cliente vê "use o cupom X" mas o Pix vem com valor cheio → frustração e perda de confiança. (É seguro do ponto de vista de fraude — ninguém consegue baixar preço pelo front — mas quebra a promessa comercial.)
- **Recomendação:** decidir se cupom é só divulgação (então tirar a menção a "desconto" do banner) ou implementar a aplicação real no backend.
- **Esforço:** médio/grande · **Risco:** médio.

---

## 7. Problemas baixos (P3)

- **P3-1 — Arquivos de patch legados na raiz:** `app_backup_*.py`, `app_frajola_patch.py`, `app_runtime_patch.py`, `app_pagamento_misto_patch.py`, etc. (10+ arquivos `app_*_patch.py`) são do app desktop e poluem a raiz. Não vão ao site (o build os exclui), mas dificultam navegação. *Recomendação:* mover para `desktop/` ou `patches/`.
- **P3-2 — `teste-commerce.html` em produção:** página de teste com `noindex` mas acessível publicamente e listada no `robots.txt` como Disallow. *Recomendação:* remover do deploy.
- **P3-3 — `mistica-v2/index.html`:** redirect de compatibilidade que o workflow de deploy valida obrigatoriamente. Mantido de propósito; documentar por quê.
- **P3-4 — Senha admin padrão compartilhada com salt estático:** `backend/user_sync_routes.py:135` cria `bruxo`/`bruxa` com `MISTICA_DEFAULT_PANEL_PASSWORD` e salt fixo `"mistica_presentes"`. Funcional, mas dois admins com a mesma senha e salt não-aleatório é fraqueza menor. PBKDF2 com 120k iterações (`config.py:178`) é adequado. *Recomendação:* senhas individuais e salt aleatório por usuário.
- **P3-5 — Nome do sitemap desatualizado:** `sitemap.xml` não inclui `/politica-*` com `lastmod` recente nem as páginas de categoria com prioridade coerente; datas fixas em 2026-07-10/11. *Recomendação:* gerar sitemap no build.
- **P3-6 — `console.warn` em produção:** `mobile-sync.js:163` loga produto sem código; ruído menor no console do cliente.
- **P3-7 — Divergência de CSS entre páginas:** home/escola/kit usam `v2.css`; produto/políticas/404 usam `styles.css` + `commercial.css`. Dois sistemas de design conviventes; risco de inconsistência visual futura.

---

## 8. Bugs confirmados

| # | Bug | Evidência | Severidade |
|---|---|---|---|
| B1 | CLS 0,399 na página de produto (salto de layout) | Lighthouse + `produto-page.js:211` | P1 |
| B2 | Scripts apontando para host de API diferente do resto | `escola.js:2`, `v2-courses.js:14`, `v2-admin-products.js:2` | P1 |
| B3 | Métrica de acessos do site nunca é populada (endpoint exige chave que o browser não tem) | `site_stock_routes.py:511` + ausência de caller JS | P2 |
| B4 | Cupom de campanha exibido mas não aplicado ao total | `campaigns-banner.js` vs `recalcular_venda_site` | P2 |
| B5 | ~7 MB de PNGs órfãos publicados no `dist-site` | `du -h dist-site/assets` + grep de referências | P2 |

> **Não classifiquei como bug** (funciona conforme o design, verificado no código): recálculo de preço no servidor, baixa de estoque atômica, reserva/expiração de pedido, idempotência, proteção de material de curso pago, separação admin/público. Todos têm testes que passam.

---

## 9. Riscos prováveis

- **R1 (alto):** perda de dados no Render Free (ver P0-1). Provável a cada deploy se não houver disco persistente.
- **R2 (médio):** cold start do Render Free — a API "dorme" e a primeira compra/consulta do dia demora vários segundos, podendo parecer "site travado". O `healthcheck.yml` ajuda a manter acordado, mas depende de agenda.
- **R3 (médio):** se algum dia a API subir com múltiplos workers, o rate limit em memória enfraquece (P1-3).
- **R4 (médio):** dependência de um único host `onrender.com` fixado em 3 arquivos (P1-2) — mudança de infra quebra Escola/admin silenciosamente.
- **R5 (baixo):** avaliações sem moderação podem receber spam (P2-7).

---

## 10. Segurança

**Pontos fortes confirmados (com evidência):**
- Preço/estoque **sempre** recalculados no servidor; o cliente não define valor (`site_stock_routes.py:152-173`, comentários e código). Impede fraude de preço pelo front.
- Baixa de estoque **atômica** (`UPDATE … WHERE quantidade >= ?`), previne venda do mesmo último item a dois clientes (`site_stock_routes.py:176`, `order_status_routes.py:195`).
- **Idempotência** no registro de pagamento/checkout (`backend/idempotency.py`).
- Sessões em **cookie `HttpOnly`**; token nunca no corpo da resposta (`panel_sessions.py:266`, `user_sync_routes.py:275`).
- **CSRF:** verificação de `Origin`/`Referer` em métodos mutáveis (`panel_sessions.py:324`).
- **Login:** rate limit + bloqueio progressivo (5→5min, 10→30min, 15→24h) persistido no banco, com atraso exponencial e alerta de segurança (`panel_sessions.py:138-224`).
- **Segredos nunca no navegador** — checkout público usa chave interna só no servidor (`product_routes.py:44`); há teste dedicado `tests/test_no_browser_api_secret.py`.
- **Docs/OpenAPI protegidos:** `/docs`, `/redoc`, `/openapi.json` exigem sessão admin (`backend/main.py:72-84`).
- **Upload validado por conteúdo real** (magic bytes / Pillow), não só content-type (`upload_routes.py:127-159`).
- **Material de curso pago protegido:** `/uploads/cursos/{arquivo}` confere sessão de aluno com acesso liberado (`backend/main.py:110`).
- **Recibo de pedido** exige `pix_txid` ou chave admin — impede varredura de IDs sequenciais para colher dados de clientes (`order_status_routes.py:350`).
- **CORS** restrito a domínios próprios (`api_security.py:11`); teste garante que não é wildcard.
- **Webhook Pix** com segredo próprio, separado da chave geral (`payment_routes.py:116`).
- **LGPD:** consentimento antes de analytics (`consent.js`/`analytics.js`); dados de cliente não persistem no navegador em produção (`site-production-guard.js`).

**Fraquezas (já detalhadas):** sem headers de segurança (P2-1); rate limit em memória (P1-3); avaliações sem moderação (P2-7); senha admin padrão compartilhada (P3-4).

*Não realizei testes ativos/exploração contra o ambiente de produção — apenas análise estática e um `GET /api/health` que retornou 403 pelo proxy (esperado neste ambiente de auditoria).*

---

## 11. Performance

| Métrica | Home | Produto | Alvo bom |
|---|---|---|---|
| Performance (LH) | 63 | 65 | ≥ 90 |
| FCP | 3,0 s | 1,4 s | ≤ 1,8 s |
| **LCP** | **4,8 s** | 3,1 s | ≤ 2,5 s |
| **CLS** | 0 | **0,399** | ≤ 0,1 |
| TBT | 230 ms | 20 ms | ≤ 200 ms |

*Medido localmente com Lighthouse (`lhci autorun`, 1 run, Chromium headless). Parte do "render-blocking" e "text-compression" é artefato do servidor local sem gzip; em produção (GitHub Pages) o número real de rede é melhor, mas LCP e CLS são reais.*

Principais alavancas: reservar dimensões de imagem (CLS), preload da hero + adiar scripts não críticos (LCP/TTI), remover PNGs órfãos e reduzir o MP3.

---

## 12. Responsividade

- **Viewport** correto em todas as páginas (`width=device-width, initial-scale=1.0`).
- Menu mobile com `data-menu-toggle` funcional (`app.js:230`); testes Playwright rodam em **Pixel 7** e passam (catálogo, kits).
- `mobile-sync.js` cuida de sincronização em telas pequenas; há status flutuante.
- **Não verificado manualmente em tablet real** (só emulação Chromium Desktop + Pixel 7 via Playwright). Recomenda-se um passe visual em ~768px de largura.
- Áreas clicáveis dos chips/botões parecem adequadas; sem medição formal de touch target por página.

---

## 13. UX e UI

**Fortes:** identidade xamânica coerente (paleta escura + dourado, tipografia Cinzel/Inter), primeira dobra clara com CTA duplo (Ver produtos / WhatsApp), categorias por intenção, "kits por intenção", player ambiente, seção Isis, prova social (estrelas) no card. Navegação por WhatsApp é o CTA comercial central e está presente em todo lugar (bom para o público-alvo).

**A melhorar:**
- CLS na página de produto quebra a sensação de solidez (P1-1).
- Dois sistemas de CSS (`v2.css` vs `styles.css`) → risco de o produto/políticas parecerem de "outra loja".
- Carrinho e Pix ficam na mesma seção longa da home (`#checkout`) — em celular exige muito scroll; considerar um mini-carrinho fixo.
- Player e várias seções competem por atenção na home; para quem chega de anúncio, a hierarquia "produto → carrinho" pode ficar diluída.
- A Isis da home é hoje um placeholder ("A Isis comercial está carregando…", `app.js:212`) — promete inteligência que não entrega na home; ajustar a expectativa ou conectar de fato.

---

## 14. Conversão

Alavancas comerciais identificadas (todas éticas, sem padrões obscuros):
1. Corrigir CLS/LCP (páginas mais estáveis e rápidas convertem mais).
2. Aplicar de fato os cupons (P2-8) ou parar de prometê-los.
3. Mini-carrinho fixo/contador de itens no header.
4. Página de produto com foto real (hoje muitos produtos usam só ícone emoji).
5. Prova social real (avaliações moderadas) em vez de campo vazio.
6. Frete/prazo mais explícito antes do WhatsApp.
7. Botão de compra sempre visível (sticky) no mobile na página de produto.
8. Reduzir o nº de scripts no head para acelerar a primeira interação.

---

## 15. Retenção nos estudos (Escola Mística)

Estado atual: catálogo de 4 cursos (1 grátis, 3 pagos), compra por Pix, área do aluno com login e liberação após confirmação manual do admin. Conteúdo servido protegido por sessão.

Oportunidades (éticas):
- **Barreira de cadastro:** hoje a senha só nasce após confirmação **manual** do admin via WhatsApp — fricção alta e dependente de humano. Automatizar confirmação (webhook Pix já existe para produtos; estender para cursos).
- **Progresso do aluno:** não há marcação de aula concluída, "continuar estudando", histórico ou trilha. Adicionar `alunos_progresso` e um botão "retomar".
- **Prévia/aula demonstrativa** dos cursos pagos para reduzir barreira de compra.
- **Onboarding** do aluno após criar senha (hoje cai direto no catálogo).
- **Materiais complementares, resumos, certificado** ao concluir — nada disso existe ainda.
- **Filtros por tema/nível/duração** no catálogo (hoje é lista fixa de 4).

---

## 16. SEO

**Muito bom (Lighthouse SEO 100).** Evidências: `<title>`/meta description por página, canonical, Open Graph + Twitter Card completos, `robots.txt` com Disallow de admin/teste + Sitemap, `sitemap.xml` com 12 URLs, JSON-LD rico (`seo-site.js`: LocalBusiness/Store, WebSite, BreadcrumbList, Product com AggregateRating), páginas de categoria com FAQPage e CollectionPage, `lang="pt-BR"`, geo tags.

**Ajustes:** sitemap com datas estáticas (P3-5); a home injeta muito SEO via JS (`seo-site.js` roda em `load`+700ms) — se o Googlebot não executar bem o JS, parte do structured data pode não ser lida; considerar renderizar o essencial no HTML. `teste-commerce.html`/`mistica-v2` com `noindex` (correto).

---

## 17. Acessibilidade

**Bom (Lighthouse A11y 96 home / 100 produto).** `aria-label` em navegação, botões e player; `alt` nas imagens principais; `lang` correto; foco e HTML semântico (`header`/`main`/`section`/`article`/`footer`). Formulários com `<label>`/`aria-label`.

**Ajustes:** confirmar contraste do dourado sobre fundos claros em alguns cards; garantir foco visível em todos os chips/botões custom; a home perdeu 4 pontos — o relatório aponta itens menores de contraste/nome acessível (rodar `lighthouse` com detalhe para listar). Áreas clicáveis dos emojis de categoria devem ter texto associado (já têm `<strong>`).

---

## 18. Qualidade do código

**Positivo:** backend modular por router, funções pequenas, comentários explicando decisões de segurança (raro e valioso), testes cobrindo os caminhos críticos, uso de `Decimal` para dinheiro (`site_stock_routes.py:146`), tratamento de concorrência pensado.

**A melhorar:** raiz do repositório poluída (site + app desktop + patches + 2 apps FastAPI no mesmo lugar); `app.js` com muitas funções em uma linha (densidade dificulta leitura); duplicação de `validar_site_api_key` reexportada em vários módulos (já foi parcialmente unificada em `api_security.py`); dois sistemas de CSS; `console.warn` em produção; `on_event` deprecado em `api/main.py`.

---

## 19. Testes executados e resultados

| Verificação | Comando | Resultado |
|---|---|---|
| Deps Python | `pip install -r requirements.txt` | OK (precisou `-U cryptography`: o `cryptography 41` do sistema causava `PanicException` no PyO3; após upgrade, resolveu) |
| Testes unit/integração | `python -m pytest -q` | ✅ **111 passed** |
| E2E | `npx playwright test` (Chromium `/opt/pw-browsers`) | ✅ **24 passed** após rerun (1 falha inicial de timeout de ambiente, não do código — passou isolada) |
| Build do site | `node scripts/minify-assets.mjs` | ✅ gera `dist-site/` (minifica CSS/JS) |
| Auditoria de deps Node | `npm audit --omit=dev` | ✅ **0 vulnerabilidades** |
| Lighthouse | `npx lhci autorun` | ✅ rodou; scores na Fase 11 |
| Health API produção | `curl api.misticaesotericos.com.br/api/health` | ⚠️ 403 (bloqueado pelo proxy do ambiente de auditoria — não é falha do site) |

**O que NÃO pôde ser verificado:**
- Configuração real de variáveis de ambiente do Render (inclusive se `MISTICA_DB_PATH` aponta para disco persistente) — **não está no repositório**.
- Comportamento real de produção (cold start, CORS ao vivo, cookies cross-site) — o proxy bloqueou o acesso à API.
- `pip-audit` (não instalado no ambiente; o workflow `auditoria-periodica.yml` roda no CI).
- Fluxo de pagamento Pix real (depende de banco/PSP configurado).
- Teste manual em tablet/dispositivo físico e leitor de tela real.

---

## 20. Melhorias rápidas (baixo risco)

1. Definir `width`/`height`/`aspect-ratio` nas imagens de produto e reservar altura do `#produtoPageRoot` → mata o CLS (P1-1).
2. Unificar `apiBaseUrl` em `site-config.js` e remover os 3 hosts `onrender.com` fixos (P1-2).
3. Excluir os PNGs órfãos de ~7 MB (P2-3).
4. Adicionar `X-Content-Type-Options: nosniff` e `Referrer-Policy` na API (P2-1, parte fácil).
5. `preload` da imagem hero da home (P2-2).
6. Remover `teste-commerce.html` do deploy (P3-2).
7. Tirar o `console.warn` de `mobile-sync.js` (P3-6).
8. Alinhar o texto do banner de cupom com o que o checkout realmente faz (P2-8, versão "só divulgação").

---

## 21. Melhorias estruturais

1. **Persistência de produção** (P0-1): Persistent Disk ou Postgres + validar backup diário.
2. **Progresso/retenção da Escola**: tabela de progresso, "continuar estudando", automação da liberação pós-pagamento.
3. **Rate limit compartilhado** ao escalar (P1-3).
4. **Unificar sistema de CSS** (`v2.css` como fonte única).
5. **Separar o repositório**: site público vs app desktop vs API, ou ao menos pastas claras.
6. **Cabeçalhos de segurança + CSP** testados.
7. **Moderação de avaliações**.

---

## 22. Roadmap recomendado

- **Sprint 0 (urgente):** garantir persistência do banco em produção (P0-1) + confirmar backup diário funcionando.
- **Sprint 1 (rápidas de conversão):** CLS produto, unificar API base, remover assets órfãos, preload hero, alinhar cupom.
- **Sprint 2 (segurança/estabilidade):** headers de segurança, moderação de avaliações, plano de rate limit ao escalar.
- **Sprint 3 (performance/responsivo):** LCP home, MP3, revisão tablet.
- **Sprint 4 (Escola/retenção):** automação de liberação, progresso do aluno, prévias.
- **Sprint 5 (SEO/A11y/limpeza):** sitemap dinâmico, contraste, organização do repositório.

---

## 23. Arquivos que precisam ser modificados (por melhoria)

| Melhoria | Arquivos |
|---|---|
| CLS produto | `produto-page.js`, `produto-page.css` |
| API base única | `escola.js`, `v2-courses.js`, `v2-admin-products.js`, `site-config.js` |
| Assets órfãos | `assets/*.png` (remover), `scripts/minify-assets.mjs` |
| Headers de segurança | `backend/main.py` |
| LCP home | `index.html` (preload, ordem de scripts) |
| Cupom | `campaigns-banner.js` e/ou `backend/campaign_routes.py` + `site_stock_routes.py` |
| Persistência | `render.yaml`, `config.py`, secrets do Render (fora do repo) |
| Rate limit | `backend/rate_limit.py` |
| Moderação avaliações | `backend/review_routes.py`, `admin.html`/`campaign-admin.js` |

---

## 24. Critérios de conclusão (aceite) por melhoria

- **P0-1 resolvido:** pedido criado → redeploy da API → pedido ainda existe em `GET /api/pedidos`. Backup diário gera artifact com sucesso.
- **CLS:** `lhci autorun` reporta CLS < 0,1 em `produto.html`.
- **API base:** grep não encontra mais `onrender.com` fixo; E2E de compra de curso + login de aluno passam.
- **Assets órfãos:** `dist-site` sem os PNGs; nenhuma página quebra visualmente (Playwright verde).
- **Headers:** resposta da API traz os headers; suíte `pytest` e E2E continuam verdes.
- **LCP:** Lighthouse home LCP < 2,5 s (ou melhora mensurável documentada).
- **Cupom:** ou o banner não promete desconto, ou o total do Pix reflete o desconto (novo teste de backend).
- **Rate limit:** teste que simula N workers, ou documentação de que roda com 1 worker.
- **Avaliações:** novas avaliações entram como `aprovado=0` e só aparecem após aprovação.

---

## Saída final obrigatória

### 1) Os 10 problemas mais importantes
1. **P0-1** — SQLite em disco efêmero no Render Free → perda de pedidos/alunos/cursos.
2. **P1-1** — CLS 0,399 na página de produto.
3. **P1-2** — 3 scripts apontando para host de API diferente do resto.
4. **P1-3** — Rate limit só em memória (frágil ao escalar).
5. **P2-1** — Sem cabeçalhos de segurança HTTP.
6. **P2-2** — LCP 4,8 s na home.
7. **P2-8** — Cupom de campanha exibido mas não aplicado no total.
8. **P2-3** — ~7 MB de PNGs órfãos no artefato de deploy.
9. **P2-7** — Avaliações publicadas sem moderação.
10. **P2-5** — Métrica de acessos do site nunca populada (código morto).

### 2) As 10 melhorias de maior impacto comercial
1. Garantir persistência do banco (confiança/operação).
2. Corrigir CLS/LCP das páginas de venda.
3. Aplicar cupons de verdade (ou parar de prometê-los).
4. Fotos reais de produto no lugar de emojis.
5. Mini-carrinho fixo no mobile.
6. Botão de compra sticky na página de produto.
7. Prova social real (avaliações moderadas).
8. Frete/prazo mais explícito antes do WhatsApp.
9. Reduzir scripts no head (primeira interação mais rápida).
10. Automatizar liberação de curso pós-pagamento (menos fricção).

### 3) As 10 melhorias para retenção nos estudos
1. Indicador de progresso por curso.
2. Botão "continuar estudando" / retomar última aula.
3. Automação da liberação de acesso após pagamento.
4. Onboarding do aluno após criar senha.
5. Aula demonstrativa/prévia dos cursos pagos.
6. Trilhas recomendadas e conteúdos relacionados.
7. Materiais complementares e resumos.
8. Certificado ao concluir.
9. Filtros por tema/nível/duração.
10. Histórico e favoritos do aluno.

### 4) Correções rápidas de baixo risco
Ver Fase 20 — CLS, unificar API base, remover PNGs órfãos, headers básicos, preload hero, remover `teste-commerce.html`, tirar `console.warn`, alinhar texto do cupom.

### 5) Plano de execução por prioridade
Ver Fase 22 (Sprints 0–5). Etapa 1 = P0 + P1; depois estabilidade/segurança; depois performance/responsivo; depois Escola; por fim SEO/A11y/limpeza.

### 6) Verificações realmente executadas
`pytest` (111 ✅), Playwright E2E (24 ✅), build do site (✅), `npm audit --omit=dev` (0 vuln ✅), Lighthouse (home/produto ✅), leitura completa de rotas, componentes, config, workflows e schema.

### 7) O que NÃO pôde ser verificado
Variáveis de ambiente reais do Render (incl. `MISTICA_DB_PATH`/disco persistente), comportamento de produção ao vivo (cold start, CORS, cookies cross-site — API retornou 403 pelo proxy do ambiente), `pip-audit`, fluxo Pix real com banco/PSP, e teste manual em tablet físico e leitor de tela.

### 8) Aprovação
**Nenhuma alteração foi feita.** Este relatório é o diagnóstico inicial. Aguardo sua aprovação para implementar — sugiro começar pelas correções rápidas de baixo risco (Fase 20) e pela verificação/correção do P0-1 (persistência), que é o item mais crítico.
