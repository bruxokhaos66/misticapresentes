# Issue #297 — Auditoria da Fase 1

Branch: `fix/checkout-producao-estavel`

Base validada: `7c10a311e8e2274081ca487fc737aaf387f305ed`

Escopo desta auditoria: checkout, Pix, catálogo, estoque e persistência no navegador. Nenhuma alteração foi feita na `main`.

## Resumo da causa raiz

O frontend público mantém duas arquiteturas concorrentes:

1. `app.js` implementa catálogo demonstrativo, estoque local, vendas locais e o fluxo `generatePix()`;
2. `site-production-guard.js` tenta corrigir o comportamento em produção por interceptação tardia, implementando um segundo fluxo completo em `guardedGeneratePix()` e sobrescrevendo `saveState()`.

Essa sobreposição cria comportamento dependente da ordem de carregamento dos scripts e dos listeners, em vez de uma única fonte de verdade.

## 1. Checkout e Pix duplicados

### `app.js`

- registra diretamente `generatePix` em `[data-generate-pix]`;
- valida carrinho e estoque local;
- chama `window.misticaCriarPedido(cart)`;
- renderiza o QR Code;
- chama `saveSale(pedido)`;
- limpa o carrinho e sincroniza novamente.

### `site-production-guard.js`

- registra listener global em fase de captura para o mesmo `[data-generate-pix]`;
- chama `event.stopImmediatePropagation()`;
- implementa novamente criação de pedido em `guardedGeneratePix()`;
- renderiza novamente o QR Code;
- registra venda local, limpa o carrinho e chama `saveState()`.

### Conflito

A proteção depende de o listener capturador estar instalado antes do clique. Se o guard atrasar, falhar ao carregar ou não instalar, o listener original de `app.js` continua funcional. Existem duas implementações de checkout e duas formas de montar o payload.

## 2. Duas implementações de criação do pedido

### `mobile-sync.js`

Expõe `window.misticaCriarPedido = criarPedidoNoServidor` e envia `/api/checkout/pedidos`.

### `site-production-guard.js`

Implementa separadamente `criarPedidoNaApi()` e envia para a mesma rota.

### Conflito

Os payloads não são iguais. O guard envia campos como `subtotal`, `desconto`, `taxa` e `total_final`; o fluxo de `mobile-sync.js` envia outra estrutura. Mesmo que o backend recalcule os valores, manter dois contratos no navegador aumenta o risco de regressão e divergência.

## 3. Baixa e reposição local de estoque

### `app.js`

- `reduceStockFromCart()` altera o objeto `stock` no navegador;
- `saveSale()` chama `reduceStockFromCart()` imediatamente após criar o Pix;
- a geração do Pix é tratada como registro de venda local e limpa o carrinho.

### `mobile-sync.js`

- `reporEstoqueDaVenda()` soma quantidades novamente no objeto local `stock`;
- cancelamentos e mudanças de status podem alterar estoque local;
- há ações locais de cancelamento e reposição.

### Conflito

O backend já reserva e controla o estoque do pedido. A baixa/reposição local cria uma segunda contabilidade, sujeita a divergência após recarga, sincronização, expiração ou cancelamento.

## 4. Persistência sensível no `localStorage`

### `app.js`

Na inicialização, lê:

- `misticaSales`;
- `misticaStock`;
- `misticaSuppliers`.

A implementação original de `saveState()` grava:

- `misticaSales`;
- `misticaStock`;
- `misticaSuppliers`;
- `misticaAutoBackup`;
- `misticaLastBackupAt`.

### `site-production-guard.js`

Somente depois tenta substituir `saveState()` por `safeProductionSaveState()` e remover as chaves.

### Conflito

A segurança depende de sobrescrita posterior. Antes do guard instalar, `app.js` já pode ler dados antigos e chamar o `saveState()` inseguro ao final da inicialização.

## 5. Catálogo demonstrativo e fallback comercial

### `app.js`

Inicializa `products` com oito produtos demonstrativos e cria estoque local a partir deles.

### `mobile-sync.js`

- só substitui o catálogo quando a API retorna uma lista não vazia;
- em falha, mostra `Catálogo local carregado • confirme disponibilidade pelo WhatsApp`;
- mantém os produtos demonstrativos disponíveis para carrinho e compra.

### Conflito

Uma falha da API não bloqueia a venda. Ela transforma o catálogo demonstrativo em fallback comercial de produção, contrariando a regra de backend como única fonte de verdade.

## 6. Estado de prontidão ausente

Não existe um estado central e explícito como:

- `loading`;
- `ready`;
- `error`.

O botão de Pix e os botões de adicionar produto não dependem de uma confirmação positiva de carregamento da API. O fluxo apenas tenta inferir se o produto possui `apiId`/`codigo` no momento do clique.

## 7. Ordem de carregamento frágil

Em `index.html`:

1. `site-config.js` é carregado;
2. `app.js` é carregado antes de `mobile-sync.js`;
3. `site-config.js` injeta `site-production-guard.js` dinamicamente;
4. o guard instala suas proteções apenas depois.

Isso permite que o estado demonstrativo e o `saveState()` original sejam inicializados antes da proteção de produção.

## Pontos que devem ser unificados na implementação

- um único listener para `[data-generate-pix]`;
- uma única função pública para criar pedido/Pix;
- catálogo vazio até resposta válida da API;
- estado explícito de catálogo (`loading`, `ready`, `error`);
- checkout e carrinho bloqueados quando o catálogo não estiver `ready`;
- nenhuma baixa ou reposição de estoque no navegador;
- persistência permitida somente para carrinho e ID de pedido pendente;
- remoção das chaves sensíveis antigas antes da leitura do estado;
- falha de API exibida como erro bloqueante, sem fallback demonstrativo.

## Arquivos diretamente envolvidos

- `index.html` — ordem dos scripts e elementos de checkout;
- `app.js` — catálogo demonstrativo, estado local, listener e fluxo de Pix;
- `mobile-sync.js` — carregamento da API, criação do pedido e ações locais de estoque/venda;
- `site-production-guard.js` — segundo checkout, listener capturador e sobrescrita tardia de persistência;
- `site-config.js` — modo de produção e carregamento dinâmico do guard;
- `v2-commerce.js` — renderizações derivadas do catálogo, sem controle próprio de prontidão.

## Testes mínimos exigidos para os primeiros commits funcionais

- um clique em “Gerar Pix” produz exatamente uma requisição de criação de pedido;
- API de catálogo indisponível mantém catálogo vazio e Pix bloqueado;
- nenhum produto demonstrativo aparece em produção;
- criar Pix não reduz `stock` no navegador;
- cancelar/expirar não repõe `stock` no navegador;
- apenas `misticaCart` e identificador de pedido pendente podem permanecer no `localStorage`;
- chaves sensíveis legadas são removidas na inicialização;
- falha de criação do pedido preserva o carrinho.
