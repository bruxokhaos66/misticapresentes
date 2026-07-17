# Isis 2.0 — Assistente Inteligente da Mística (Fase 1)

Consultora virtual do site, aditiva ao chat legado (`#isisChat`/`#isisForm`,
controlado por `isis-guided.js`, que **continua funcionando sem alterações**).
A Isis 2.0 é um widget flutuante independente, construído em módulos
reutilizáveis sob o namespace `window.Isis2`.

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
├── product-knowledge.js     Product Knowledge — única leitura do catálogo real
├── intent-engine.js         Intent Engine — regras + heurísticas em PT-BR
├── recommendation-engine.js Recommendation Engine — ranking + justificativa
├── context-memory.js        Context Memory — memória de sessão (sessionStorage)
├── cart-assistant.js        Cart Assistant — usa window.addToCart/removeFromCart
├── analytics.js             Analytics — contadores de uso, sem PII
├── ai-providers.js          AI Providers — abstração para IA futura (OpenAI/local)
├── conversation-manager.js  Conversation Manager — orquestra os módulos acima
├── widget.js                Widget (UI) — botão flutuante, painel, mensagens
├── widget.css                Estilo do widget (variáveis de marca de styles.css)
└── isis2-bootstrap.js       Bootstrap — monta o widget, feature flag
```

Cada módulo é um script clássico (mesmo padrão do restante do site — sem
bundler), que se registra em `window.Isis2.<Nome>` só se ainda não existir
(idempotente, como `isis-guided.js`). Nenhum módulo depende de outro por
`import`; a composição acontece via `window.Isis2` na ordem de carregamento
declarada no HTML.

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
| `ProductKnowledge` | única fonte de leitura do catálogo (`products`, `getStock`, `currency` globais) | não persiste nem modifica o catálogo |
| `IntentEngine` | interpreta texto livre em PT-BR | não decide o que recomendar |
| `RecommendationEngine` | ranqueia produtos do catálogo real e justifica | não inventa produtos fora do catálogo |
| `ContextMemory` | memória de sessão (sessionStorage) | nunca guarda nome, telefone, endereço, CPF |
| `CartAssistant` | fino wrapper sobre `window.addToCart`/`removeFromCart` | não reimplementa regras de carrinho/estoque |
| `Analytics` | contadores agregados de uso | não coleta dados pessoais; delega ao `misticaTrack` já existente (com gate de consentimento) |
| `AIProviders` | abstração para IA futura | não chama nenhuma API externa nesta fase |
| `ConversationManager` | orquestra os módulos acima | não manipula o DOM |
| `Widget` | única camada que toca o DOM | não contém regra de negócio |

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

## Métricas (Fase 1)

Eventos em `Analytics.track`: `conversation_started`, `message_sent`,
`product_recommended`, `recommendation_clicked`, `product_added_to_cart`,
`checkout_suggested`. Cada evento é um contador agregado por sessão
(sem PII) e é encaminhado para GA/Meta Pixel via `misticaTrack` somente
após consentimento — mesma política já usada pelo restante do site.
"Abandono" e "conversão pós-interação" ficam documentados como próximo
passo (roadmap), pois exigem correlação com o funil de checkout existente.

## Testes

- **Unitários** (`tests/isis2/*.test.js`, Node `node:test`): cobrem
  `ProductKnowledge`, `IntentEngine`, `RecommendationEngine`,
  `ContextMemory`, `CartAssistant` e o `ConversationManager` — incluindo os
  7 exemplos de conversa citados no briefing (`Quero um incenso para
  relaxar`, `Qual pedra ajuda na proteção?`, `Estou começando no
  xamanismo`, `Quero um presente até R$100`, `Tenho ansiedade`, `Quero
  montar um altar`, `Qual essência combina com lavanda?`). Rodar com
  `node --test tests/isis2/*.test.js`.
- **E2E** (`tests/e2e/isis2-widget.spec.js`, Playwright, já configurado
  para desktop e mobile — `playwright.config.js`): abrir o widget,
  recomendar um produto real, adicionar ao carrinho, filtrar por
  orçamento, checar que o chat legado continua no DOM, e uma checagem
  básica de acessibilidade (`role="dialog"`, `role="log"`,
  `aria-live="polite"`, fechar com Esc). Rodar com
  `npx playwright test tests/e2e/isis2-widget.spec.js`.
- Testes existentes do site (`localstorage-seguro`, `catalog-xss`,
  `catalogo`, etc.) foram reexecutados e continuam passando — ver relatório
  técnico do PR.

## Riscos conhecidos e mitigação

| Risco | Mitigação nesta fase |
|---|---|
| Catálogo genérico (8 categorias, não SKUs individuais) limita a precisão da recomendação | Ranking por categoria/termos já cobre os exemplos do briefing; RAG/embeddings ficam para quando houver catálogo mais granular |
| Widget aparecer sobre outros elementos fixos (banner de consentimento, WhatsApp flutuante) | z-index ajustado abaixo do banner de consentimento; validado por E2E |
| Peso extra no Lighthouse | ~11 arquivos pequenos, sem imagens externas, sem fontes novas, CSS reaproveitando variáveis existentes; script carregado com `defer` |
| Widget montado antes do catálogo estar pronto | `isis2-bootstrap.js` remonta (idempotente) em 250ms/900ms/1600ms, mesmo padrão de `isis-guided.js` |
| Provedor de IA externo mal configurado expor chave no cliente | Fase 1 não implementa nenhuma chamada de rede em `ai-providers.js`; qualquer ativação futura exige endpoint de backend |

## Roadmap (próximas fases, fora do escopo deste PR)

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
