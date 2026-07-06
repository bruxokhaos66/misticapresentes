# Auditoria visual do site — etapas e limpeza técnica

Este documento registra o estado atual dos ajustes visuais do site da Mística Presentes e serve como guia para manutenção futura.

## Etapas já realizadas

### Etapa 1 — Hero e Isis

Objetivo: corrigir a primeira dobra do site e estabilizar a posição da Isis.

Arquivos envolvidos:

- `hero-isis-position-fix.js`
- `commercial-layer.js`

Resultado:

- Isis deixou de ficar baixa demais.
- Depois foi corrigido o problema de “pulo” visual após o carregamento.
- A posição ficou estável sem `setTimeout` agressivo.

### Etapa 2 — Sistema visual dos cards

Objetivo: padronizar proporção, bordas, sombras, padding e altura dos cards.

Arquivos envolvidos:

- `card-system-fix.js`
- `commercial-layer.js`

Resultado:

- Cards do hero ficaram mais leves.
- Categorias, produtos, formulários, carrinho, estoque e histórico ganharam padrão visual.
- O site ficou menos “montado” e mais comercial.

### Etapa 3 — Espaçamento entre seções

Objetivo: melhorar o respiro vertical entre hero, experiência sonora, categorias, produtos, checkout, Isis e contato.

Arquivos envolvidos:

- `section-spacing-fix.js`
- `commercial-layer.js`

Resultado:

- Rolagem entre seções ficou mais natural.
- O bloco “Experiência sonora xamânica” ficou mais bem encaixado.
- Âncoras do menu foram ajustadas com `scroll-margin-top`.

## Camadas visuais carregadas atualmente

O site ainda carrega várias camadas visuais via `commercial-layer.js`:

1. `modern-icon-fix.js`
2. `seo-site.js`
3. `admin-access.js`
4. `product-extras.js`
5. `pedido-status.js`
6. `admin-alerts.js`
7. `admin-activity.js`
8. `painel-auth.js`
9. `site-readiness.js`
10. `isis-commerce.js`
11. `isis-commands.js`
12. `isis-section-products-fix.js`
13. `commercial-premium.js`
14. `ambient-experience.js`
15. `layout-wide-fix.js`
16. `hero-isis-position-fix.js`
17. `card-system-fix.js`
18. `section-spacing-fix.js`

## Ponto de atenção técnico

As camadas visuais funcionam, mas várias delas injetam CSS ou alteram o DOM depois do carregamento. Isso pode causar:

- conflitos de prioridade CSS;
- cache segurando visual antigo;
- comportamento diferente entre primeiro carregamento e recarregamento;
- dificuldade para manutenção futura.

## Regra de manutenção recomendada

A partir deste ponto:

1. Evitar criar novos arquivos de correção visual sem necessidade.
2. Manter a ordem final das camadas visuais:
   - `layout-wide-fix.js`
   - `hero-isis-position-fix.js`
   - `card-system-fix.js`
   - `section-spacing-fix.js`
3. Não reintroduzir `setTimeout` para mexer no hero/Isis, a menos que seja realmente necessário.
4. Evitar margens negativas agressivas no hero.
5. Alterar primeiro em branch separada e validar com print/vídeo.

## Necessidades salvas para depois

### Produtos e catálogo

- Deixar a seção de produtos mais leve.
- Avaliar filtros por intenção/categoria.
- Reduzir sensação de muitos botões próximos.

### Rodapé

- Refinar para visual mais premium.
- Melhorar alinhamento e hierarquia.
- Integrar melhor com a identidade xamânica do topo.

### Contador de acessos ADM

- Criar endpoints reais no backend/API:
  - `POST /api/site/acessos`
  - `GET /api/site/acessos/resumo`
- O objetivo é mostrar acessos reais de todos os clientes, não apenas fallback local.

### Música ambiente

- Manter ativação por clique.
- Avaliar trilha própria leve/premium futuramente.

### Testes finais

- Desktop largo.
- Notebook.
- Android.
- Links de menu e âncoras.
- Carrinho.
- Pix.
- WhatsApp.

## Próxima limpeza futura sugerida

Depois que o visual estiver aprovado por completo, consolidar os ajustes visuais em uma estrutura mais definitiva, possivelmente movendo regras estáveis para CSS fixo e reduzindo scripts que apenas injetam CSS.
