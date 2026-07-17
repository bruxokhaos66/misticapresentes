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
- com a flag desligada, `isis2/isis2-loader.js` (o único script sempre
  baixado) sai sem fazer nada — nenhum outro arquivo da Isis 2.0 é
  requisitado, e a Isis 1 (`isis-guided.js`) segue como está.

**Como habilitar em homologação/produção**: como o site é estático (sem
build por ambiente), a flag é ligada editando o valor no `site-config.js`
publicado naquele ambiente (`enabled: true`) antes do deploy — o mesmo
arquivo, sem lógica condicional de servidor. Recomendação: ligar primeiro
num deploy de homologação, validar, e só then promover para produção.
Nunca ligar via parâmetro de URL nem hack de navegador — isso é
intencionalmente impossível por design.

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
- **Fase 2**: expandir o widget para as páginas de categoria/Escola
  Mística; correlacionar `Analytics` com o funil de checkout para medir
  conversão real e abandono.
- **Fase 3**: motor de afinidade de complementos aprendido a partir de
  vendas reais (hoje é uma tabela de regras em `product-knowledge.js`).
- **Fase 4**: RAG sobre a base de conhecimento (descrições, dúvidas
  frequentes, avaliações), com backend próprio para custodiar a chave do
  provedor de IA — nunca no navegador.
- **Fora de escopo permanente nesta iniciativa**: qualquer recurso
  administrativo, acesso a dados de clientes/vendas/fornecedores, ou
  execução de comandos — a Isis 2.0 é só uma consultora de vitrine.
