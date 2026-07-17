# Isis 2.0 — Assistente Inteligente da Mística (Fase 1)

Consultora virtual do site, aditiva ao chat legado (`#isisChat`/`#isisForm`,
controlado por `isis-guided.js`, que **continua funcionando sem alterações**).
A Isis 2.0 é um widget flutuante independente, construído em módulos
reutilizáveis sob o namespace `window.Isis2`, **desligada por padrão** atrás
de uma feature flag pública (veja "Feature flag" abaixo).

## Feature flag — MISTICA_ISIS2_ENABLED

`window.misticaSiteConfig.isis2.enabled` em `site-config.js` (arquivo
estático público, carregado antes de qualquer outro script). Default
**`false`**. Propriedades:

- não é segredo — é só um booleano de apresentação, sem token nem chave;
- nunca é lida de query string nem de `localStorage`/`sessionStorage`
  (testado em `tests/e2e/isis2-widget.spec.js`);
- determinística: mesmo valor em todo carregamento da página, não muda em
  runtime por ação do usuário;
- com a flag desligada, `isis2/isis2-homolog-gate.js` (o único script
  sempre baixado) sai sem carregar nenhum outro arquivo da Isis 2.0 — a
  menos que o backend autorize a homologação para a sessão atual (ver
  seção abaixo) — e a Isis 1 (`isis-guided.js`) segue como está.

**Produção**: a flag em `site-config.js` fica **sempre `false`**. Não é
editada manualmente por ambiente — o site publicado (GitHub Pages,
domínio único `www.misticaesotericos.com.br`) é o mesmo para todo mundo.

## Homologação controlada (mesmo domínio de produção)

Como o projeto não tem hoje um segundo domínio/serviço Render dedicado a
staging (GitHub Pages publica só a branch `main`; o Render roda um único
serviço web), a homologação real da Isis 2.0 completa acontece no MESMO
domínio de produção, para uma allowlist fechada de contas autorizadas —
nunca para o público geral. Mecanismo (Opção B do plano de homologação):

1. `index.html`/`kit.html`/`produto.html`/`escola.html`/`escola-curso.html`
   carregam `isis2/isis2-homolog-gate.js` no lugar do antigo
   `isis2-loader.js` estático.
2. Com a flag estática desligada (sempre, em produção), o portão faz
   `GET /api/isis2/homolog-config` com `credentials: "include"` — ou seja,
   usa o cookie de sessão HttpOnly **já existente** (painel admin ou aluno
   logado), nunca lê query string, hash, header customizado, localStorage
   ou sessionStorage.
3. `backend/isis2_homolog.py` decide no servidor: só responde
   `{enabled:true, escola:true, refinamento:true, homologacao:true}` se
   (a) o interruptor global estiver ligado (tabela
   `isis2_homolog_config`, por padrão desligado) **e** (b) a sessão for de
   um admin **ou** de um aluno presente na allowlist fechada (tabela
   `isis2_homolog_testers`). Qualquer outro caso — visitante anônimo,
   sessão expirada, aluno fora da allowlist, erro de banco, exceção —
   responde a configuração desativada com HTTP 200 (fail-safe: nunca
   ativa por omissão).
4. Só quando a resposta confirma `enabled` e `homologacao` como `true`, o
   portão sobrescreve `window.misticaSiteConfig.isis2` em runtime, injeta
   `isis2-loader.js` (o restante da Isis 2.0 carrega normalmente a partir
   daí) e mostra o indicador "Isis em homologação" no canto inferior
   esquerdo da tela.

Administração da allowlist (todas as rotas exigem sessão de admin):

| Ação | Rota |
| --- | --- |
| Ligar o interruptor global | `POST /api/isis2/homolog/ativar` |
| **Desligar imediatamente (sem deploy)** | `POST /api/isis2/homolog/desativar` |
| Consultar estado | `GET /api/isis2/homolog/estado` |
| Listar testadores autorizados | `GET /api/isis2/homolog-testers` |
| Autorizar um aluno (por ID interno) | `POST /api/isis2/homolog-testers/{aluno_id}` |
| Revogar um aluno | `DELETE /api/isis2/homolog-testers/{aluno_id}` |
| Revogar todos de uma vez | `POST /api/isis2/homolog-testers/revogar-todos` |

Ver `docs/isis2-homologacao-checklist.md` para o roteiro manual completo de
testes e `tests/test_isis2_homolog.py` / `tests/isis2/homolog-gate.test.js`
/ `tests/e2e/isis2-homolog.spec.js` para a cobertura automatizada.

## Convivência com a Isis 1 (chat legado)

Com a flag desligada (default), nada muda: só a Isis 1 aparece, exatamente
como hoje. Com a flag ligada, para evitar dois assistentes competindo pela
atenção do cliente (dois botões, dois históricos, dois pontos manipulando o
carrinho), `isis2-bootstrap.js` **esconde em runtime** o chat embutido da
Isis 1 (`#isisChat`, `#isisForm`, `.quick-actions` dentro de `#isis`) assim
que confirma que o widget novo montou com sucesso (catálogo disponível), e
mostra uma nota (`.isis2-legacy-notice`) apontando para o botão flutuante.

Importante: isso é feito com JavaScript, não removendo elementos do DOM nem
com CSS estático — se a Isis 2.0 falhar ao montar por qualquer motivo
(catálogo não carregou, erro de script), a Isis 1 **permanece visível e
funcional**, porque nunca é desativada antes da confirmação de sucesso.
Esse comportamento é coberto por `tests/e2e/isis2-widget.spec.js`
("convivência com a Isis 1").

## Por que aditivo, e não uma reescrita do chat existente

- Reduz o risco de regressão: nenhuma função existente foi removida ou
  alterada (`app.js`, `isis-guided.js`, carrinho, checkout, etc.).
- Permite comparar/depreciar o chat legado depois, com dados reais, em vez
  de decidir isso na Fase 1.
- Mantém o PR revisável: o diff é só adição de arquivos novos + algumas
  linhas de `<script>`/`<link>` nas páginas públicas.

## Arquitetura

```
isis2/
├── isis2-loader.js          Loader — único script sempre baixado; só injeta o resto se a flag estiver ligada
├── product-knowledge.js     Product Knowledge — única leitura do catálogo real
├── intent-engine.js         Intent Engine — regras + heurísticas em PT-BR
├── safety-guardrails.js     Safety Guardrails — saúde/crise/substâncias
├── recommendation-engine.js Recommendation Engine — ranking + justificativa
├── context-memory.js        Context Memory — memória de sessão (sessionStorage)
├── cart-assistant.js        Cart Assistant — usa window.addToCart/removeFromCart
├── analytics.js             Analytics — contadores de uso, sem PII
├── ai-providers.js          AI Providers — abstração para IA futura (OpenAI/local)
├── conversation-manager.js  Conversation Manager — orquestra os módulos acima
├── widget.js                Widget (UI) — botão flutuante, painel, mensagens
├── widget.css                Estilo do widget (variáveis de marca de styles.css)
└── isis2-bootstrap.js       Bootstrap — monta o widget, convivência com a Isis 1
```

Cada módulo é um script clássico (mesmo padrão do restante do site — sem
bundler), que se registra em `window.Isis2.<Nome>` só se ainda não existir
(idempotente, como `isis-guided.js`). Nenhum módulo depende de outro por
`import`; a composição acontece via `window.Isis2`. Só `isis2-loader.js` é
declarado nas páginas HTML (`<script defer>`); ele injeta os demais
dinamicamente, na ordem correta (`script.async = false`), e só quando a
feature flag está ligada — ver "Feature flag" acima e "Performance" abaixo.

### Fluxo de uma mensagem

```
usuário digita/clica          Widget (UI)
        │                          │
        ▼                          ▼
 handleUserMessage(text) ──▶ Conversation Manager
        │
        ├─▶ Intent Engine.detect(text)          → intenção, orçamento, saudação...
        ├─▶ Context Memory.registerMessage(...)  → memória da sessão
        ├─▶ Recommendation Engine.recommend(...)
        │        └─▶ Product Knowledge (catálogo real: products/getStock)
        ├─▶ Analytics.track(...)                 → métricas agregadas
        └─▶ devolve {text, products, reasons, complements, quickReplies}
                                   │
                                   ▼
                         Widget renderiza a resposta
```

### Camada híbrida de inteligência (Fase 1)

1. **Regras** (`intent-engine.js`): dicionário de sinônimos/PT-BR informal,
   extração de orçamento ("até R$100"), detecção de saudação/agradecimento.
2. **Busca semântica leve** (`product-knowledge.js#searchByTerms`):
   pontuação por frequência de termos no nome/descrição/categoria do
   produto — não é um motor de embeddings, mas resolve bem o catálogo atual
   (poucas dezenas de categorias) e tem contrato estável para evoluir.
3. **Ranking** (`recommendation-engine.js#rankProducts`): combina o score
   textual com bônus por categoria prioritária da intenção e por
   aderência ao orçamento informado.

`ai-providers.js` já prepara o encaixe de um provedor externo (OpenAI,
modelo local, RAG): a interface `generate(prompt, context)` está definida e
registrada, mas **nenhuma chamada de rede é feita nesta fase** — o provedor
ativo por padrão é sempre `"rules"`. Ativar outro provedor no futuro deve
passar por um endpoint de backend próprio (a chave de API nunca pode viver
no navegador).

## Componentes e contratos

| Módulo | Responsabilidade | Não faz |
|---|---|---|
| `ProductKnowledge` | única fonte de leitura do catálogo (`products`, `getStock`, `currency` globais); deduplica por ID e tolera ID string/número | não persiste nem modifica o catálogo |
| `IntentEngine` | interpreta texto livre em PT-BR: intenção, orçamento (fixo/faixa), ordenação por preço, exclusões/negação, combo com orçamento total | não decide o que recomendar |
| `SafetyGuardrails` | classifica mensagens sensíveis (saúde mental, alegação médica, risco imediato, substâncias) | não decide o texto final da resposta — só classifica |
| `RecommendationEngine` | ranqueia produtos do catálogo real e justifica; respeita exclusões e nunca extrapola orçamento | não inventa produtos fora do catálogo |
| `ContextMemory` | memória de sessão (sessionStorage) | nunca guarda nome, telefone, endereço, CPF |
| `CartAssistant` | fino wrapper sobre `window.addToCart`/`removeFromCart`; valida quantidade e confirma sucesso comparando o carrinho antes/depois | não reimplementa regras de carrinho/estoque, não assume sucesso sem checar |
| `Analytics` | contadores agregados de uso | não coleta dados pessoais; delega ao `misticaTrack` já existente (com gate de consentimento) |
| `AIProviders` | abstração para IA futura | não chama nenhuma API externa nesta fase |
| `ConversationManager` | orquestra os módulos acima, incluindo guardrails de segurança | não manipula o DOM |
| `Widget` | única camada que toca o DOM | não contém regra de negócio |

### Intenção de compra: negação e exclusão

"não quero X" / "sem X" / "já tenho X" removem X da recomendação e dos
complementos sugeridos. Detalhe importante e testado: **"não tenho X" é
tratado como sinal positivo, não como exclusão** — "quero um incenso, mas
não tenho incensário" deve *sugerir* o incensário como complemento, não
escondê-lo. Ver comentário em `intent-engine.js#detectExclusions`.

## APIs e dados utilizados

- **Catálogo**: variável global `products` (populada por `mobile-sync.js` a
  partir da API oficial `/api/produtos`, com fallback estático em `app.js`).
  Nenhuma chamada de rede nova foi criada.
- **Estoque/preço**: `getStock(id)` e `currency` (globais de `app.js`).
- **Carrinho**: `window.addToCart`, `window.removeFromCart`, `cart`
  (globais de `app.js`) — a Isis 2.0 nunca grava direto em
  `localStorage`/`sessionStorage` o carrinho; quem faz isso continua sendo
  `app.js`.
- **Telemetria**: `window.misticaTrack` (`analytics.js`), já com gate de
  consentimento (LGPD) — a Isis 2.0 só adiciona eventos prefixados
  `isis2_*`.
- **Avaliações**: `product.avaliacoesTotal`/`avaliacoesMedia`, já
  sincronizados pelo `mobile-sync.js`.

Nenhuma rota de backend nova foi criada nesta fase.

## Segurança

- Todo conteúdo dinâmico renderizado pelo widget passa por `escapeHtml()`
  antes de entrar em `innerHTML` (nomes de produto, textos gerados,
  respostas do usuário ecoadas na conversa).
- Sem `eval`, sem `new Function`, sem `document.write`.
- Sem acesso a rotas administrativas, sem tokens no cliente, sem acesso
  direto a banco de dados — a Isis 2.0 só lê os mesmos globais já expostos
  publicamente pelo site (`products`, `cart`, etc.).
- `ContextMemory`/`Analytics` usam **sessionStorage** (não `localStorage`),
  reforçando que é memória de sessão, e a lista de campos salvos é
  fechada (ver testes) — nunca dado pessoal.
- O widget fica com z-index abaixo do banner de consentimento
  (`consent-banner.css`), para nunca cobrir a decisão de cookies do
  cliente.

## Saúde e espiritualidade (Safety Guardrails)

`safety-guardrails.js` classifica a mensagem antes de qualquer
recomendação de produto:

- **Risco imediato** (ex.: "quero morrer") → não tenta vender nada,
  orienta CVV 188 (24h) e SAMU 192 em emergência.
- **Alegação médica** (ex.: "qual pedra cura câncer", "posso parar meu
  remédio") → nunca confirma cura/tratamento/substituição de terapia,
  nunca recomenda interromper tratamento, e explica que os produtos são
  para experiência aromática/decorativa/cultural/bem-estar não médico.
- **Saúde mental comum** (ansiedade, depressão, insônia, pânico) → segue
  para a recomendação normal (ex.: banho de ervas, aromatizador), mas
  sempre com aviso de que a Isis não é profissional de saúde e não
  diagnostica.
- **Rapé/ayahuasca/medicinas da floresta**: por padrão, resposta educativa
  (sem dose/preparo, direciona à Escola Mística); se a mensagem pedir
  dose/preparo/combinação ou envolver menor de idade, a resposta é ainda
  mais restrita e recusa dar qualquer instrução de uso.

Testes: `tests/isis2/safety-guardrails.test.js`.

## Métricas (Fase 1)

Eventos em `Analytics.track`: `conversation_started`, `message_sent`
(só a categoria de intenção, ex. `"calma"` — nunca o texto da mensagem),
`product_recommended` (contagem + intenção), `recommendation_clicked`
(item + ação), `product_added_to_cart` (item + quantidade real),
`checkout_suggested`, e os eventos de guardrail
(`safety_crisis_detected`, `safety_medical_claim_detected`,
`safety_substance_risk_detected`, `safety_substance_education_shown` —
só a categoria, nunca o texto da mensagem que disparou). Cada evento é um
contador agregado por sessão (sem PII) e é encaminhado para GA/Meta Pixel
via `misticaTrack` somente após consentimento — mesma política já usada
pelo restante do site. Nenhum evento carrega texto de conversa, dado
pessoal, termo médico literal ou conteúdo de checkout.
"Abandono" e "conversão pós-interação" ficam documentados como próximo
passo (roadmap), pois exigem correlação com o funil de checkout existente.

## Performance

`isis2-loader.js` é o único arquivo sempre baixado pelas páginas públicas
(link/scripts estáticos). Com a flag desligada (default), ele sai sem
fazer nada — nenhum outro arquivo da Isis 2.0 é requisitado. Com a flag
ligada: ~60KB de JS (~18KB gzip) + ~7KB de CSS (~2KB gzip) em 12
requisições adicionais, todas com `defer`/injeção assíncrona, sem bloquear
o parse do HTML nem o LCP da página (nenhum desses arquivos afeta conteúdo
acima da dobra). Ver medições no relatório do PR.

## Testes

- **Unitários** (`tests/isis2/*.test.js`, Node `node:test`, 62 testes):
  `ProductKnowledge` (catálogo real, duplicatas, ID string/número, preço
  ausente), `IntentEngine` (intenção, orçamento fixo/faixa, ordenação,
  exclusão/negação, combo), `SafetyGuardrails` (saúde/crise/substâncias),
  `RecommendationEngine` (ranking, orçamento, exclusões, combo),
  `CartAssistant` (quantidade inválida, estoque insuficiente, produto
  inexistente, input de quantidade ausente na página), `ConversationManager`
  — incluindo os 7 exemplos de conversa do briefing original e os 14 da
  matriz de recomendação pedida na auditoria. Rodar com `npm run
  test:isis2` (ou `node --test tests/isis2/*.test.js`). Script auxiliar
  `tests/isis2/helpers/dump-matrix.js` imprime a saída real de cada
  mensagem da matriz (não é teste automatizado, é ferramenta de inspeção
  usada para escrever o relatório sem inventar comportamento).
- **E2E** (`tests/e2e/isis2-widget.spec.js`, Playwright, desktop e mobile
  — `playwright.config.js`, 16 testes): feature flag (desligada por
  padrão, impossível ligar por query string/localStorage, zero requisições
  extras quando desligada), convivência com a Isis 1, recomendação real +
  adicionar ao carrinho, filtro por orçamento, recusa de estoque
  insuficiente sem fingir sucesso, XSS (nome/descrição maliciosos do
  catálogo e mensagem do próprio usuário), acessibilidade (`role="dialog"`,
  `role="log"`, `aria-live="polite"`, Tab+Enter, fechar com Esc), mobile
  (layout e não sobreposição com WhatsApp/cookies). Rodar com
  `npx playwright test tests/e2e/isis2-widget.spec.js`.
- Testes existentes do site (`localstorage-seguro` — 20 testes,
  `catalog-xss`, `catalogo` — 6 testes) foram reexecutados após todas as
  mudanças desta auditoria e continuam passando — ver relatório técnico do
  PR.

## Riscos conhecidos e mitigação

| Risco | Mitigação nesta fase |
|---|---|
| Catálogo genérico (8 categorias, não SKUs individuais) limita a precisão da recomendação | Ranking por categoria/termos já cobre os exemplos do briefing; RAG/embeddings ficam para quando houver catálogo mais granular |
| Widget aparecer sobre outros elementos fixos (banner de consentimento, WhatsApp flutuante) | z-index ajustado abaixo do banner de consentimento; validado por E2E |
| Peso extra no Lighthouse | Loader único (~700 bytes) sempre baixado; resto (~60KB JS/7KB CSS) só com a flag ligada, via injeção assíncrona sem bloquear render |
| Widget montado antes do catálogo estar pronto | `isis2-bootstrap.js` remonta (idempotente) em 250ms/900ms/1600ms, mesmo padrão de `isis-guided.js` |
| Provedor de IA externo mal configurado expor chave no cliente | Fase 1 não implementa nenhuma chamada de rede em `ai-providers.js`; qualquer ativação futura exige endpoint de backend |
| Cliente digita comandos de carrinho em texto livre ("remova tudo", "troque 2 por 5") | **Não suportado nesta fase** — o carrinho só é alterado pelos botões dos cards recomendados. Mensagens desse tipo caem no fluxo normal de recomendação (sem quebrar, mas sem executar a ação). Documentado como gap conhecido, não fingido como resolvido. |
| Resposta fraca para pedidos muito genéricos ("quero algo") após uma exclusão total (ex.: "não quero lavanda" sozinho) | A Isis admite que não entendeu em vez de adivinhar (kind `no_match`) — comportamento intencional (nunca inventar), mas a UX podia perguntar de volta de forma mais ativa; fica como melhoria de Fase 2 |

## Honestidade (sem falsa inteligência)

A mensagem de boas-vindas deixa explícito, na primeira interação: "uma
assistente virtual baseada no catálogo e em regras da Mística Presentes
(ainda não sou uma pessoa nem uma IA generativa nesta fase)". A Isis 2.0
não afirma ter memória permanente, não trata a conversa como confidencial
(é uma vitrine de loja, não atendimento médico), e só afirma fatos que vêm
do `ProductKnowledge` — nunca inventa preço, estoque, avaliação ou
característica de produto.

## Roadmap (próximas fases, fora do escopo deste PR)

- **Fase 1.1 (gap conhecido)**: comandos de carrinho em texto livre
  ("remova tudo", "troque 2 por 5") — hoje o carrinho só muda pelos
  botões dos cards recomendados.
- **Fase 3**: motor de afinidade de complementos aprendido a partir de
  vendas reais (hoje é uma tabela de regras em `product-knowledge.js`);
  Escola: motor de recomendação aprendido a partir de conclusões reais.
- **Fase 4**: RAG sobre a base de conhecimento (descrições, dúvidas
  frequentes, avaliações), com backend próprio para custodiar a chave do
  provedor de IA — nunca no navegador.
- **Fora de escopo permanente nesta iniciativa**: qualquer recurso
  administrativo, acesso a dados de clientes/vendas/fornecedores, ou
  execução de comandos — a Isis 2.0 é só uma consultora de vitrine/tutora
  de conteúdo, nunca um painel de gestão.

---

# Fase 2 — Especialista da Mística Escola

Expande a Isis 2.0 para as páginas da Escola Mística (`escola.html`,
`escola-curso.html`): apresenta cursos, explica módulos/aulas, recomenda
uma trilha, ajuda o aluno a achar seus cursos e — só quando autenticado —
consulta progresso, próxima aula e motivo de bloqueio de módulo. Aditiva
à Fase 1: mesmo widget, mesmo `ConversationManager` como ponto de
entrada, nenhum arquivo da Fase 1 foi reescrito — só uma delegação
condicional (ver "Arquitetura" abaixo) e extensões pontuais em
`context-memory.js`, `analytics.js` e `widget.js`.

## Feature flag — MISTICA_ISIS2_ESCOLA_ENABLED

`window.misticaSiteConfig.isis2.escola.enabled` em `site-config.js`.
Default **`false`**. Regras (testadas em
`tests/e2e/isis2-escola.spec.js` e `tests/isis2/school-conversation-manager.test.js`):

- depende também de `isis2.enabled === true` — com a flag geral
  desligada, a flag da Escola nunca é avaliada (`school-mode.js#isActive`
  faz `flagsEnabled() && isSchoolPage()`, nessa ordem);
- só ativa nas páginas autorizadas: `escola.html` e `escola-curso.html`
  (`window.location.pathname`, nunca query string);
- nunca lida de query string nem de `localStorage`/`sessionStorage`;
- não contém segredo — é só um booleano de apresentação, igual à flag
  geral;
- configurável estaticamente no `site-config.js` publicado por ambiente,
  mesmo processo já documentado para `MISTICA_ISIS2_ENABLED` acima.

Comportamento (ver `isis2-loader.js#schoolPageActive`):

```
MISTICA_ISIS2_ENABLED=false
→ Isis 2.0 não carrega (nem a comercial, nem a Escola).

MISTICA_ISIS2_ENABLED=true, MISTICA_ISIS2_ESCOLA_ENABLED=false
→ Isis 2.0 comercial funciona normalmente onde já funcionava
  (index/kit/produto); nas páginas da Escola, o widget só monta se
  houver catálogo comercial disponível ali (hoje não há), então na
  prática a Escola não ganha assistente nenhum — fallback seguro: a
  experiência atual da Escola (sem Isis) continua exatamente igual.

Ambas true
→ nas páginas da Escola, os módulos da Fase 2 são baixados e o widget
  passa a responder no domínio de cursos; fora dessas páginas, nada muda.
```

## Escopo permitido

Só `escola.html` e `escola-curso.html` (`isis2-loader.js#SCHOOL_PAGES`).
Não foi adicionado a checkout, admin (`admin.html`, `escola-admin.html`)
nem a nenhuma outra página. Páginas públicas de curso específicas por
módulo (`escola-incensos.html`, `escola-medicinas-floresta.html`) **não**
foram incluídas nesta fase — não usam a plataforma de estudo (LMS) real
(`escola-curso.js`), então ficam fora do escopo "fonte oficial de dados"
até que migrem para lá; documentado como gap conhecido, não fingido como
resolvido.

## Arquitetura

Módulos novos (mesmo padrão: script clássico, registra em
`window.Isis2.<Nome>`, sem `import`):

```
isis2/
├── school-mode.js                 School Mode — decide se a Escola está ativa (flags + página)
├── school-knowledge.js            School Knowledge — catálogo real de cursos + APIs de curso
├── student-context.js             Student Context — sessão do aluno, "meus cursos", curso com progresso
├── course-recommendation-engine.js Course Recommendation Engine — ranking + justificativa
├── progress-assistant.js          Progress Assistant — traduz o payload do backend em explicação simples
├── lesson-navigation.js           Lesson Navigation — URLs seguras (rota fixa + slug validado)
├── assessment-safety.js           Assessment Safety — guardrail de proteção acadêmica
├── school-intent-engine.js        School Intent Engine — intenções do domínio de cursos, PT-BR informal
└── school-conversation-manager.js School Conversation Manager — orquestra os módulos acima
```

Reaproveitados sem duplicar (nenhum arquivo novo reimplementa o que já
existe):

- **Conversation Manager** (`conversation-manager.js`): ganhou só 3
  branches de delegação (`schoolActive()` no topo de
  `handleUserMessage`/`handleIntentShortcut`/`startConversation`) — se
  `SchoolMode.isActive()`, delega 100% ao `SchoolConversationManager` e
  retorna; senão, comportamento da Fase 1 é idêntico, sem nenhuma outra
  mudança de lógica;
- **Safety Guardrails** (`safety-guardrails.js`): reaproveitado
  verbatim — `SchoolConversationManager` chama o mesmo `classify(text)`
  antes de qualquer recomendação de curso, com textos de resposta
  adaptados ao contexto educacional (nunca duplicando a classificação);
- **Context Memory** (`context-memory.js`): estendido com um sub-objeto
  fechado `school` (ver "Memória de sessão" abaixo) — a memória
  comercial da Fase 1 não mudou de formato (só ganhou um campo a mais no
  objeto raiz, testado no allowlist de campos permitidos);
- **Analytics** (`analytics.js`): ganhou `trackSchoolEvent(name, payload,
  {dedupeKey})`, que envia o nome exato pedido pelo briefing da Escola
  (sem o prefixo automático `isis2_`), reaproveitando a mesma
  infraestrutura (contador local + `misticaTrack` + gate de
  consentimento). Guardrails de segurança do domínio da Escola
  (crise/saúde) continuam usando o `track()` comercial existente, para
  reaproveitar a mesma taxonomia de eventos da Fase 1 em vez de inventar
  nomes novos fora da lista pedida;
- **Widget (UI)** (`widget.js`): sem novo componente visual — só passou
  a suportar dois campos extras na resposta (`reply.courses`,
  `reply.actions`), renderizados com as mesmas classes CSS dos cards de
  produto (`isis2-card`, `isis2-btn`); `mount()` passou a aceitar
  catálogo comercial OU catálogo da Escola como fonte válida
  (`hasUsableCatalog()`); `respondTo()` passou a aceitar tanto uma
  resposta síncrona (Fase 1) quanto uma Promise (Fase 2, que consulta
  APIs reais) via `Promise.resolve(...)`;
- **Feature flags** (`isis2-loader.js`, `site-config.js`): a Escola é
  uma segunda camada de módulos injetada pelo mesmo loader único, nunca
  um segundo `<script>` estático nas páginas — ver "Feature flag" acima.

### Por que o Intent Engine da Escola é um módulo irmão, não uma extensão do comercial

`intent-engine.js` (Fase 1) já tem um contrato estável e testado para o
domínio comercial (orçamento, exclusão de produto, combo). O vocabulário
da Escola (módulo, aula, avaliação, matrícula, bloqueio) não tem
equivalente ali, e misturar os dois domínios no mesmo arquivo aumentaria
o risco de regressão na Isis comercial só para adicionar cursos. Por
isso `school-intent-engine.js` é um módulo irmão, com a mesma técnica
(regras + normalização PT-BR), registrado à parte
(`window.Isis2.SchoolIntentEngine`). Essa é uma decisão de design
explícita, não um esquecimento — sinalizada aqui para a auditoria.

### Fluxo de uma mensagem na Escola

```
usuário digita           Widget (UI)
     │                        │
     ▼                        ▼
handleUserMessage(text) → Conversation Manager
     │
     └─ schoolActive()? → School Conversation Manager
              ├─ Assessment Safety.classify(text)   → bloqueia resposta de avaliação
              ├─ Safety Guardrails.classify(text)   → reaproveitado da Fase 1
              ├─ School Intent Engine.detect(text)  → intenção do domínio de cursos
              ├─ School Knowledge / Course Recommendation Engine  → catálogo real
              ├─ Student Context (só quando autenticado)          → APIs reais
              ├─ Progress Assistant                                → traduz o payload
              ├─ Context Memory.updateSchool(...)                  → memória mínima
              └─ Analytics.trackSchoolEvent(...)                   → eventos sem PII
                                   │
                                   ▼
                    {text, courses, actions, quickReplies}
                                   │
                                   ▼
                         Widget renderiza a resposta
```

## Fonte oficial de dados

Nenhum dado é inventado. Mapeamento real observado em
`escola.js`/`escola-curso.js` (comentado em cada módulo consumidor):

| Dado | Fonte real |
|---|---|
| Catálogo público de cursos (slug, título, tipo, preço, tags, resumo) | `window.MISTICA_ESCOLA_CURSOS`, exposto por `escola.js` (a mesma lista renderizada em `escola.html`; congelada, somente leitura) |
| Detalhe público de um curso (visitante) | `GET /api/escola/publico/cursos/:slug` |
| Detalhe de um curso com progresso real (aluno autenticado) | `GET /api/escola/cursos/:slug` — 401 sem sessão, 403 sem acesso liberado |
| "Meus cursos" (matrículas, percentual, aulas concluídas) | `GET /api/escola/meus-cursos` — 401 sem sessão |
| Quem está logado | `GET /api/alunos/me` |
| Módulos, aulas, status (concluída/em andamento), bloqueio (`liberado`) | dentro do payload de `GET /api/escola/cursos/:slug` |
| Avaliação (quiz): nota mínima, perguntas | `GET /api/escola/quizzes/:id/iniciar` — **não é chamado pela Isis** (ver nota abaixo) |
| Certificado | `GET /api/cursos/:slug/certificado` (link direto, não uma pergunta da Isis) |

**Por que a Isis nunca chama `/api/escola/quizzes/:id/iniciar`**: essa
rota inicia uma sessão de avaliação no backend (`sessao_id`), e não há
garantia documentada de que isso seja livre de efeito colateral (pode
contar como o início de uma tentativa). Chamar essa rota "só para saber
a nota mínima" arriscaria consumir uma tentativa do aluno sem ele ter
pedido — por isso `gradeReply()`/`attemptsReply()` admitem que não têm
esse número na conversa e direcionam o aluno a abrir a avaliação de
verdade, em vez de arriscar. Documentado em `progress-assistant.js`.

A Isis nunca lê texto renderizado da página como fonte de verdade — só
`window.MISTICA_ESCOLA_CURSOS` (dado estruturado, mesma fonte do HTML) e
as APIs acima.

## Comportamento — visitante não autenticado

Pode: ver catálogo, comparar cursos, pedir recomendação por tema/nível,
saber quantidade de módulos/aulas de um curso público
(`fetchPublicDetail`), ser direcionado à matrícula. Não pode: consultar
progresso (a Isis nunca chama `courseDetail`/`myCourses` fingindo
sessão — o próprio `fetch` com `credentials:"include"` simplesmente volta
401 sem cookie de sessão, e a resposta explica que é preciso entrar),
nem ver dado de outro aluno (não existe nenhum caminho de código que
aceite um identificador de aluno vindo do usuário — a única "identidade"
é o cookie de sessão do próprio navegador, decidido pelo backend).

## Comportamento — aluno autenticado

`StudentContext` consulta sempre com `credentials: "include"` (cookie de
sessão real, não token no cliente) e nunca decide autorização sozinho:
todo 401/403 é repassado como veio do backend. Respostas de progresso
citam explicitamente que o dado "é da sua conta, consultado agora" —
nunca fingem saber algo sem ter chamado a API na hora.

## Intenções implementadas

`school-intent-engine.js#detect` reconhece (com tolerância a erro de
digitação simples via variações de grafia e raízes de palavra — ex.:
"xamanicmo" ainda casa com o tema xamanismo): catálogo de cursos, melhor
curso para começar (+ nível iniciante), tema de interesse (xamanismo,
cristais, aromaterapia, rapé, ayahuasca, cosmologia), "meus cursos",
próximo módulo/próxima aula ("terminei a aula, o que faço agora?"),
quanto já concluí, módulo bloqueado (motivo), nota mínima, tentativas
restantes, matrícula suspensa — ver testes em
`tests/isis2/school-conversation-manager.test.js`.

## Recomendação de cursos

`course-recommendation-engine.js#recommend` pontua por tema
(`SchoolKnowledge#searchByTerms`), filtra por nível iniciante quando
pedido (tag `"Iniciante"` do catálogo real, nunca suposição), e — quando
o aluno está autenticado — nunca sugere de novo um curso já
adquirido/concluído (`StudentContext.myCourses()`). Sempre explica o
motivo (`"Recomendo começar por X porque..."`, texto construído a partir
de sinais reais: tema batido, tag de iniciante, primeira posição no
ranking) e nunca inventa duração, certificado, preço ou pré-requisito
fora do catálogo/API.

## Navegação assistida

`lesson-navigation.js` é o único módulo que constrói URL. Contrato:

- só aceita um `slug` que exista de fato em `SchoolKnowledge.bySlug()`
  (`isKnownCourse`) — qualquer slug desconhecido, path traversal ou URL
  absoluta retorna `null`, nunca uma URL montada;
- toda URL gerada é relativa às duas páginas autorizadas
  (`escola.html`, `escola-curso.html?curso=<slug>`);
- o widget (`widget.js#isSafeSchoolUrl`) valida de novo, em defesa
  profunda, com uma regex fechada antes de renderizar qualquer `href` —
  mesmo que um módulo upstream tivesse um bug, a UI não renderizaria uma
  URL fora do padrão;
- nunca `javascript:`, nunca HTML não escapado (`escapeHtml` em todo
  texto vindo de API antes de entrar no DOM, igual à Fase 1).

**Limitação documentada**: a rota real de player (`escola-curso.js`)
sempre abre a primeira aula pendente automaticamente — não existe hoje
parâmetro de URL para "aula X" ou "módulo Y" específico. Por isso
"continuar", "próxima aula" e "abrir módulo" apontam todos para a mesma
URL do curso; é o player (com o progresso real do backend) quem decide a
aula exata. Não fingimos ter granularidade que a rota atual não tem.

## Progresso e desbloqueio

`progress-assistant.js` é só leitura: nunca marca aula concluída, libera
módulo, altera nota, reseta tentativa ou contorna suspensão — cada
consulta reflete exatamente o que `GET /api/escola/cursos/:slug` devolve
naquele momento. Motivo de bloqueio é descrito de forma genérica e
verdadeira ("o módulo anterior ainda não foi concluído"), sem inventar
nota mínima/tentativas quando o payload não traz esses campos.

## Avaliações — proteção acadêmica

`assessment-safety.js#classify` bloqueia dois padrões, testados em
`tests/isis2/assessment-safety.test.js` e no E2E:

1. pedido explícito de gabarito/resposta certa (regex de frases como
   "qual a alternativa correta", "me dá a resposta", "gabarito");
2. pergunta de múltipla escolha colada (2+ linhas no formato `a)`/`b)`/`c)`
   junto de contexto de avaliação ou `?`).

Quando classificado, a Isis nunca resolve a questão, nunca indica a
alternativa correta — oferece revisar o conteúdo ou propor perguntas de
estudo (não idênticas à avaliação). O evento `isis_assessment_help_blocked`
é disparado sem nenhum trecho da pergunta.

Dúvidas comuns de conteúdo ("pode explicar de novo o que é rapé?") não
são bloqueadas — só o pedido de resposta direta de avaliação.

## Conteúdo sensível

Reaproveita 100% o `safety-guardrails.js` da Fase 1 (crise, alegação
médica, saúde mental, substâncias/rapé/ayahuasca/medicinas da floresta)
com textos de resposta adaptados ao tom educacional da Escola. Nenhuma
regra nova foi criada — as mesmas garantias testadas na Fase 1 (nunca
promete cura, nunca recomenda parar tratamento, nunca dá dose/preparo)
valem aqui.

## Memória de sessão

`context-memory.js` ganhou um sub-objeto fechado `school` dentro do
mesmo `sessionStorage` (`isis2_session`), com expiração própria de
**45 minutos** (`SCHOOL_TTL_MS`), mais estrita que a memória comercial
(que só "expira" ao fechar a aba):

```
courseOfInterest, studentLevel, viewedCourseSlug, currentModuleId,
currentLessonId, educationalIntent, presentedCourseIds (máx. 10)
```

Nunca guarda: resposta de avaliação, nota, texto integral de conversa,
dado pessoal, token, cookie ou conteúdo médico — testado no allowlist de
campos em `tests/isis2/context-memory-and-cart.test.js` (agora cobre os
dois sub-objetos, comercial e escola).

## Estados de erro

Tratados explicitamente em `school-conversation-manager.js` (nunca
inventa resposta quando a API falha):

| Estado | Resposta |
|---|---|
| API indisponível (erro de rede) | `"Não consegui consultar seu progresso agora. Tente novamente em alguns instantes ou abra "Meus cursos"."` |
| Não autenticado / sessão expirada (401) | explica que precisa entrar, nunca mostra número de progresso |
| Matrícula suspensa/sem acesso (403) | repassa a mensagem real do backend (`body.detail`) |
| Curso fora de foco (pergunta de progresso sem contexto) | pergunta de qual curso o aluno está falando, nunca adivinha |
| Progresso ausente/incompleto no payload | mensagem de erro genérica, nunca `NaN%`/`undefined` |
| Nota mínima / tentativas restantes indisponíveis nesta camada | admite a lacuna (ver nota sobre `/quizzes/:id/iniciar` acima) |

## Analytics

`Analytics.trackSchoolEvent` (nomes exatos, sem prefixo automático):
`isis_school_opened` (de-dupe por sessão), `isis_school_intent`
(categoria da intenção, nunca o texto), `isis_course_recommended`
(contagem), `isis_course_opened` (clique em "Ver curso", de-dupe por
slug), `isis_resume_course_clicked`, `isis_progress_consulted`,
`isis_assessment_help_blocked` (payload vazio, nunca a pergunta). Os
guardrails de segurança (crise/saúde/substância) continuam usando o
`track()` comercial existente da Fase 1 (`isis2_safety_*`), para não
duplicar taxonomia. Nenhum evento carrega e-mail, nome, nota detalhada,
conteúdo de avaliação ou identificador persistente.

## Interface

Reaproveita o widget da Fase 1 (`widget.css`, `widget.js`) sem nenhum
componente novo — cards e botões de curso usam as mesmas classes CSS dos
cards de produto. Chips rápidos da Escola
(`school-conversation-manager.js#QUICK_REPLIES`): "Ver meus cursos",
"Continuar estudando", "Qual curso começar?", "Como funcionam os
módulos?", "Por que minha aula está bloqueada?". Teclado, foco,
`prefers-reduced-motion`, zoom 200% e não sobreposição de player/mobile
já eram garantidos pela Fase 1 e não foram alterados — cobertos de novo
em `tests/e2e/isis2-escola.spec.js` para confirmar que continuam válidos
nas páginas da Escola especificamente.

## Segurança

- **IDOR/dado de outro aluno**: impossível por construção — nenhuma
  função de `StudentContext`/`SchoolKnowledge` aceita um identificador de
  aluno vindo do cliente; toda consulta autenticada usa só o cookie de
  sessão (`credentials:"include"`) e a autorização é 100% decidida pelo
  backend (401/403 repassados como vieram);
- **Alteração de `aluno_id`**: não existe no cliente — não há campo de
  ID de aluno em nenhum payload enviado pela Isis (a Isis nunca envia
  `POST`/`PUT`/`DELETE`, só `GET`);
- **Endpoints administrativos/professor**: nenhum módulo da Fase 2 chama
  `/api/escola/quizzes/*/enviar`, rotas de admin ou de correção — só
  leitura de rotas de aluno;
- **XSS**: todo texto de curso/módulo/aula vindo de API passa por
  `escapeHtml()` no `widget.js` antes de `innerHTML` (mesma função da
  Fase 1), testado em `tests/e2e/isis2-escola.spec.js`;
- **URL arbitrária/`javascript:`**: ver "Navegação assistida" acima —
  validação em duas camadas (`lesson-navigation.js` + `widget.js`);
- **Progresso manipulado pelo navegador**: impossível — a Isis nunca
  escreve progresso, nunca lê `localStorage`/`sessionStorage` como fonte
  de autorização (só como memória de conversa, nunca decide acesso a
  conteúdo a partir dela).

## Testes

- **Unitários** (`tests/isis2/*.test.js`, Node `node:test`, 114 testes
  no total, +37 novos desta fase): `school-conversation-manager.test.js`
  (catálogo, recomendação por tema/iniciante, curso já
  concluído/adquirido, catálogo indisponível, não autenticado, sessão
  expirada, progresso, próxima aula, módulo bloqueado, nota
  mínima/tentativas admitidamente desconhecidas, matrícula suspensa, API
  indisponível, dados incompletos, pedido de resposta de avaliação,
  conteúdo sensível, URL maliciosa, analytics sem PII, de-dupe de
  evento), `assessment-safety.test.js` (guardrail acadêmico, navegação
  segura, catálogo real vs. inexistente, expiração/limite da memória da
  Escola). Rodar com `npm run test:isis2`.
- **E2E** (`tests/e2e/isis2-escola.spec.js`, Playwright): feature flags
  (as duas independentes, impossível ligar por query
  string/localStorage), visitante não autenticado (saudação, recomendação
  real, tentativa de consultar progresso sem login), aluno autenticado
  (meus cursos reais, abrir próxima aula por link seguro, módulo
  bloqueado), avaliação ativa sem resposta direta, XSS (título malicioso
  vindo da API), ausência de `javascript:` em qualquer link sugerido,
  teclado/Escape, restauração de foco, mobile 390×844 sem rolagem
  horizontal, zoom 200%. Rodar com `npx playwright test
  tests/e2e/isis2-escola.spec.js`.
- Suítes existentes da Fase 1 (62 testes unitários + 16 E2E) foram
  reexecutadas após todas as mudanças desta fase e continuam passando —
  ver relatório técnico do PR para o resultado completo.

## Riscos conhecidos e mitigação (Fase 2)

| Risco | Mitigação nesta fase |
|---|---|
| Nota mínima e tentativas restantes não aparecem no payload de listagem do curso (só ao abrir a avaliação de fato) | A Isis admite a lacuna em vez de arriscar chamar `/quizzes/:id/iniciar` "só para checar", o que poderia consumir uma tentativa sem o aluno pedir |
| Rota de player não tem parâmetro de aula/módulo específico na URL | "Continuar"/"próxima aula" apontam para a URL do curso; documentado como limitação da rota atual, não da Isis |
| Páginas de curso fora do LMS real (`escola-incensos.html`, `escola-medicinas-floresta.html`) não têm assistente | Fora de escopo desta fase — não usam `escola-curso.js`/APIs reais de progresso; entrariam numa fase futura só depois de migrarem para o LMS |
| `AssessmentSafety` é heurística (regex), pode deixar passar uma pergunta de avaliação reformulada de forma muito diferente do padrão observado, ou bloquear uma dúvida legítima de conteúdo em formato de múltipla escolha | Documentado como heurística, não um classificador perfeito; erra para o lado de proteger (mais falso-positivo bloqueando dúvida legítima do que falso-negativo entregando resposta) — revisão de padrões reais fica como acompanhamento pós-deploy |
| Cobertura de teste da Fase 2 é representativa, não exaustiva dos ~40 cenários enumerados no briefing (ex.: tablet, todas as 22 combinações de E2E) | Priorizados os cenários de maior risco (segurança, autorização, dado de outro aluno, XSS, flags); ver checklist completo no relatório do PR para o que ficou fora desta rodada |

# Fase 2.1 — Refinamento da Especialista da Mística Escola

## Objetivo

Aprimorar a qualidade, precisão e naturalidade da Isis nas páginas da
Mística Escola **sem alterar a arquitetura principal** da Fase 2: mesmos
módulos, mesmo Conversation Manager comercial delegando para o da Escola,
mesma Widget, mesmas feature flags de base. A Fase 2.1 adiciona módulos
"irmãos" novos e amplia módulos existentes de forma aditiva — nada foi
reescrito do zero, nenhum contrato de entrada/saída dos módulos da Fase 2
mudou. Com a flag de refinamento desligada (default), o comportamento é
byte-a-byte o mesmo da Fase 2.

## Feature flag — MISTICA_ISIS2_ESCOLA_REFINAMENTO_ENABLED

`site-config.js`, `window.misticaSiteConfig.isis2.escola.refinamento.enabled`
(booleano, default `false`). Lida uma única vez, de forma síncrona, deste
arquivo estático — nunca por query string, hash, atributo HTML,
`localStorage`, `sessionStorage` ou cookie, e nunca tratada como segredo
(é o mesmo padrão das duas flags anteriores). Não é ativada
automaticamente em produção; só passa a `true` depois de um deploy manual
e deliberado do arquivo, tipicamente primeiro em homologação.

Depende, nessa ordem, de:

1. `isis2.enabled === true` (Fase 1);
2. `isis2.escola.enabled === true` (Fase 2);
3. `isis2.escola.refinamento.enabled === true` (Fase 2.1).

`window.Isis2.SchoolMode.isRefinementActive()` encapsula essa checagem
(`isis2-loader.js` usa a mesma lógica para decidir se baixa os 4 módulos
novos — ver "Arquitetura" abaixo). Com qualquer uma das três desligada,
`isRefinementActive()` é sempre `false`.

### Matriz de ativação

| `isis2` | `escola` | `refinamento` | Resultado |
|---|---|---|---|
| false | false | false | Isis 2.0 não carrega |
| true | false | true | Refinamento não carrega (Escola desligada) |
| true | true | false | Comportamento da Fase 2, inalterado |
| true | true | true | Comportamento refinado da Fase 2.1 |

Com a flag de refinamento desligada, nenhum dos 4 módulos novos é sequer
baixado (`isis2-loader.js`), e nenhuma requisição adicional acontece —
confirmado pelo teste E2E "zero requisição extra ao endpoint público sem
pedido explícito" e pelo teste unitário de regressão byte-a-byte (mesma
resposta da Fase 2 para o mesmo pedido).

## Arquitetura

Módulos novos (aditivos, carregados só com a flag ligada):

- `negation-parser.js` — interpreta negações/exclusões/preferências da
  mensagem, devolve uma estrutura fechada e limitada.
- `course-payload-normalizer.js` — valida e normaliza com rigor o payload
  do endpoint público de detalhe de curso.
- `school-public-detail.js` — consulta esse endpoint sob demanda, com
  cache curto, timeout, `AbortController` e tratamento explícito de cada
  falha.
- `course-comparison-engine.js` — compara até 3 cursos usando só
  atributos disponíveis, sem eleger vencedor absoluto.

Módulos existentes da Fase 2 ampliados de forma aditiva (mesma função
exportada, parâmetros novos sempre opcionais):

- `school-intent-engine.js` — vocabulário novo (comparação, detalhe/
  estrutura de curso, aulas, acesso, dificuldade/nível, revisão de
  conteúdo, retomada dos estudos), resolução de intenção primária por
  ordem de prioridade explícita (`PRIORITY_ORDER`) para evitar colisão
  entre intenções concorrentes na mesma frase, e uma lista completa de
  intenções combinadas (`matchedIntents`) para não perder contexto em
  pedidos compostos.
- `course-recommendation-engine.js` — aceita um parâmetro `preferences`
  opcional (estrutura do `negation-parser.js`) para excluir/priorizar
  tema e nível sem nunca cair de volta para "qualquer curso" quando a
  exclusão elimina todas as opções.
- `assessment-safety.js` — muitos padrões novos de contorno indireto
  (ver "Proteção acadêmica" abaixo) e uma segunda função,
  `isLegitimateStudyRequest()`, que nunca afrouxa `classify()` — só
  reconhece pedidos explícitos de conteúdo inédito de estudo.
- `progress-assistant.js` — `explainBlockedModule()` agora repassa o
  motivo exato quando a API o informa (`motivo`/`motivo_bloqueio`), e só
  cai no texto genérico do briefing quando a API não informa nada.
- `context-memory.js` — sub-objeto `school` ganhou 7 campos novos, todos
  numa allowlist fechada que descarta silenciosamente qualquer chave fora
  dela (`sanitizeSchoolPartial`).
- `analytics.js` — allowlist de campos por evento novo
  (`SCHOOL_EVENT_FIELD_ALLOWLIST`) e lista fechada de categorias de erro
  (`ERROR_REASON_ALLOWLIST`).
- `school-conversation-manager.js` — todo o roteamento novo (negações,
  comparação, detalhe público, acesso, nível, revisão, retomada,
  indisponibilidade, curso concluído) fica atrás de
  `refinementActive()`; com a flag desligada, o dispatch é idêntico ao
  da Fase 2 (mesmas funções, mesma ordem, preservadas sem alteração de
  comportamento).

`isis2-loader.js` só injeta os 4 módulos novos quando
`isRefinementActive()`-equivalente é verdadeiro na página atual (mesma
checagem replicada ali, sem depender de rede — ver comentário no
próprio arquivo).

## Ordem de prioridade (guardrails antes de tudo)

`school-conversation-manager.js#handleUserMessage` roda, nessa ordem fixa,
independente da flag de refinamento: **crise → segurança/saúde → proteção
acadêmica → intenção educacional (School Intent Engine, incluindo as
intenções novas) → recomendação → comercial**. O School Intent Engine
nunca executa antes dos guardrails críticos — mesmo uma frase como
"quero morrer, qual é a próxima aula?" é interceptada pelo guardrail de
crise antes de qualquer roteamento de intenção (testado em
`school-refinamento.test.js`).

## Negações e exclusões

`negation-parser.js#parse(texto)` devolve sempre a mesma estrutura
fechada e limitada (nunca o texto integral da conversa):

```javascript
{
  includeTopics: [],
  excludeTopics: [],
  includeLevels: [],
  excludeLevels: [],
  excludeCourseIds: [],
  completedCourseIds: [],
  wantsRestart: false,
  wantsResume: false,
}
```

Reconhece, além da palavra "não": `sem`, `evite`/`evita`, `menos`,
`exceto`/`tirando`/`fora` (inclusive no padrão "qualquer um, exceto X"),
`não gosto`, `não tenho interesse`, `não preciso`, e marcadores de curso
já cursado (`já fiz`, `já concluí`, `já tenho`, `não preciso repetir`).
Também distingue "continuar de onde parei" (`wantsResume`) de "começar do
zero" (`wantsRestart`). Exclusão sempre vence conflito com inclusão do
mesmo termo. `resolveCompletedCourseIds()` resolve tema/nível "já
cursado" contra o catálogo real — nunca inventa um ID de curso.

`school-conversation-manager.js#buildPreferences()` acumula a exclusão da
mensagem atual com o que já estava salvo na sessão (`ContextMemory`,
TTL de 45min), então "não quero cristais" dito uma vez continua valendo
nas próximas recomendações da mesma sessão, sem precisar repetir.

## Recomendação e comparação

`course-recommendation-engine.js#recommend(detection, { preferences })`
nunca ignora uma exclusão "para sempre apresentar alguma recomendação":
se toda opção do tema pedido também bate com uma exclusão, o resultado é
`note: "no_match"` e a Isis diz claramente "Não encontrei no catálogo
atual um curso que combine com todas essas preferências." — nunca sugere
de volta o que foi excluído.

`course-comparison-engine.js#compare()` compara até 3 cursos usando só
tema/nível/resumo do catálogo (mais módulos/aulas quando o detalhe
público foi consultado). Campo ausente vira exatamente "Essa informação
não está disponível no catálogo atual." — nunca inventado. Nunca elege um
vencedor absoluto; a conclusão é sempre contextual ("Para quem está
começando... Para quem já possui base...").

## Endpoint público de detalhe

`GET /api/escola/publico/cursos/:slug`, só chamado quando o cliente pede
detalhes/módulos/aulas/estrutura/descrição/comparação — nunca ao abrir o
widget, nunca para todos os cursos de uma vez (`school-public-detail.js`).
Cache curto (3 minutos) por slug, timeout de 6 segundos via
`AbortController`, e cada falha tratada explicitamente com uma categoria
fechada (`timeout | offline | invalid_payload | not_found | rate_limited
| server_error | unauthorized | forbidden`). Em qualquer falha, a Isis diz
exatamente: "Não consegui consultar os detalhes completos desse curso
agora. Posso mostrar as informações básicas disponíveis ou você pode
tentar novamente mais tarde." — nunca inventa um detalhe que a API não
confirmou.

`course-payload-normalizer.js` valida tipo, tamanho, formato de cada
campo antes de qualquer renderização, ignora campos desconhecidos, e
nunca deixa passar um valor tratado como HTML confiável — a Widget usa
`textContent`/atributos escapados para todo texto vindo da API (nunca
`innerHTML`), igual à Fase 2.

## Proteção acadêmica reforçada

`assessment-safety.js` ganhou detecção para: confirmação de alternativa,
eliminação de opções, "segunda melhor resposta", tradução/codificação da
resposta (inclusive código Morse), pedido de responder só com a letra,
tentativa de fingir que não é avaliação, pedido de ordenar alternativas,
pedido de porcentagem/probabilidade de acerto, e pedido de confirmar uma
resposta já escolhida — nenhum padrão da Fase 2 foi removido ou
afrouxado, só adicionado (`classify()` continua um superconjunto estrito
do que já bloqueava). `isLegitimateStudyRequest()` é uma função separada,
nova, que só reconhece pedidos explícitos de conteúdo inédito ("crie uma
pergunta de múltipla escolha para eu treinar", "explique a diferença
entre X e Y", "quero revisar o conceito de Z") — nunca é usada para
liberar algo que `classify()` bloqueou; existe só para a Isis reconhecer
e responder melhor a estudo genuinamente legítimo. Em caso de ambiguidade
real, o bloqueio prevalece (erra para o lado seguro).

## Memória refinada

`context-memory.js`, sub-objeto `school`, 7 campos novos, todos numa
allowlist fechada (`SCHOOL_FIELD_ALLOWLIST`) que descarta silenciosamente
qualquer chave fora dela: `includeTopics`, `excludeTopics`,
`includeLevels`, `excludeLevels`, `lastRecommendedCourseIds`,
`lastComparedCourseIds`, `lastPublicCourseSlug`. Listas limitadas a 10
itens (`SCHOOL_LIST_MAX`), strings normalizadas, mesmo TTL de 45 minutos
da Fase 2, mesma limpeza em logout/troca de conta/sessão expirada
(`resetSchool()`, já disparado por `escola.js#resetIsis2SchoolIdentity`).
Nunca guarda resposta de avaliação, nota, texto integral da conversa,
e-mail, nome, ID de aluno, token ou cookie — `excludeCourseIds` e
`completedCourseIds` do `negation-parser.js` são deliberadamente
transitórios (só duram o turno atual), não entram na allowlist de
persistência.

## Analytics

Eventos novos, cada um com allowlist de campos fechada
(`SCHOOL_EVENT_FIELD_ALLOWLIST` em `analytics.js`):
`isis_school_refinement_intent` (`intent`), `isis_course_comparison`
(`count`), `isis_course_detail_consulted` (`cached`),
`isis_course_exclusion_applied` (`excludedCount`),
`isis_study_path_suggested` (`kind`), `isis_assessment_bypass_blocked`
(sem payload), `isis_school_api_unavailable` (`reason`, restrito à lista
fechada de categorias de erro). Nenhum evento carrega texto digitado,
questão, resposta, alternativa, descrição completa, nome, e-mail, ID de
aluno, nota, progresso detalhado, token, cookie ou condição médica —
qualquer campo fora da allowlist do evento é descartado antes de chegar
em `misticaTrack`/`sessionStorage`.

## Segurança e privacidade

Reaproveita integralmente as garantias da Fase 2 (IDOR impossível por
construção, XSS coberto por `textContent`/normalização, nenhuma escrita,
URL sempre validada contra o catálogo real) e adiciona: validação
rigorosa do payload público (nunca confia em status 200 sozinho),
`AbortController`/timeout no novo endpoint, e allowlists fechadas tanto
na memória quanto no analytics dos campos novos. Nenhuma chave, segredo,
ou credencial nova foi introduzida — a flag de refinamento não é tratada
como segredo, igual às duas anteriores.

## Performance

O endpoint de detalhe é lazy — só consultado quando o cliente pede
detalhe/estrutura/comparação de um curso específico, nunca para todo o
catálogo. Com a flag de refinamento desligada, o comportamento (bundle,
requisições, LCP/CLS) é idêntico à Fase 2: os 4 módulos novos não são
sequer baixados. Medição completa de Lighthouse/bundle para o estado
"refinamento ligado" não foi executada nesta sessão (ver limitações
abaixo e o relatório do PR) — recomenda-se rodar `npm run
test:lighthouse` em CI/homologação antes de qualquer promoção de
ambiente.

## Testes (Fase 2.1)

- **Unitários** (`tests/isis2/school-refinamento.test.js`, +49 testes
  novos, node:test): matriz de flags, negação/exclusão (todos os
  exemplos do briefing), recomendação com exclusão (incluindo o caso
  "nenhuma opção sobra"), comparação (dois cursos, campo ausente, sem
  contexto suficiente), detalhe público (sucesso, 401/403/404/429/500,
  JSON inválido, HTML inesperado, corpo vazio, payload incompleto, curso
  removido, slug inválido, offline, timeout via `AbortController`, cache
  e `fresh:true`, GET-only), normalizer (campos desconhecidos, tipos
  errados, slug/título inválidos), proteção acadêmica reforçada (todas
  as frases do briefing, mais confirmação de que o guardrail antigo não
  foi afrouxado), ordem de prioridade (crise e proteção acadêmica antes
  do refinamento), memória (allowlist, limite de 10, limpeza),
  analytics (payload mínimo, categorias de erro controladas), retomada
  dos estudos (autenticado/não autenticado), módulo bloqueado (motivo
  real da API vs. texto genérico), navegação segura, GET-only.
- **E2E** (`tests/e2e/isis2-escola.spec.js`, describe "Refinamento (Fase
  2.1)"): flag desligada sem requisição extra, dependência das três
  flags, negação respeitada, comparação sem vencedor absoluto, detalhe
  indisponível com a mensagem padrão, GET-only com as intenções novas.
- Toda a suíte da Fase 1 e da Fase 2 (166 testes unitários no total, 117
  pré-existentes + 49 novos) foi reexecutada após as mudanças desta fase
  e continua passando — ver relatório técnico do PR para o resultado
  completo, incluindo E2E.

## Limitações conhecidas (Fase 2.1)

| Limitação | Detalhe |
|---|---|
| `NegationParser` é heurístico (regex sobre um vocabulário fechado de temas/níveis), não um parser sintático completo | Cobre os exemplos do briefing e variações comuns, mas uma negação com estrutura muito incomum pode não ser reconhecida — nesse caso a Isis simplesmente não aplica a exclusão (não é o mesmo risco que inventar dado; na pior hipótese, recomenda algo que o aluno não queria, corrigível pedindo de novo) |
| `CourseComparisonEngine` resolve os cursos a comparar por correspondência de título/tema no texto, não por um seletor explícito de UI | Em frases muito ambíguas ("compare os dois"), pode não identificar 2-3 cursos e pedir contexto em vez de adivinhar — comportamento deliberado (nunca compara ao acaso) |
| Medição de performance (Lighthouse, bundle, requisições) do estado "refinamento ligado" não foi executada nesta sessão | Ambiente desta sessão não tinha `npm install` nem o servidor Lighthouse configurados de forma estável a tempo; recomenda-se medir em CI/homologação antes de qualquer promoção de ambiente |
| Cobertura de teste E2E da Fase 2.1 é representativa, não exaustiva das ~30 combinações listadas no briefing (viewports completos, tablet dedicado, todas as combinações de auth × intent) | Priorizados os cenários de maior risco (flags, negação, comparação, detalhe indisponível, GET-only); ver checklist completo no relatório do PR para o que ficou fora desta rodada |
| `explainBlockedModule()` só repassa `motivo`/`motivo_bloqueio` se a API real do backend passar a expor esses campos — hoje (mesmo payload observado na Fase 2) o backend normalmente não envia nenhum dos dois | Documentado como "pronto para quando a API expuser o motivo", não uma funcionalidade nova de verdade sem uma mudança correspondente no backend — comportamento atual seguro (nunca deduz) preservado |
