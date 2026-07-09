# Fase 5 - Página individual de produto

Esta fase cria uma página real para cada produto, permitindo compartilhar links diretos no WhatsApp, Instagram e campanhas.

## Recursos adicionados

- Nova página `produto.html`.
- Novo script `produto-page.js`.
- Link direto por ID:

```text
produto.html?id=incenso-natural
produto.html?id=api-1
```

- Botão `Página do produto` nos cards da vitrine.
- Link `Abrir página do produto` no modal de detalhes.
- Página com:
  - nome do produto;
  - categoria;
  - descrição;
  - preço;
  - estoque;
  - foto/ícone;
  - botão Comprar pelo WhatsApp;
  - botão Copiar link;
  - produtos relacionados.

## Como testar

1. Abrir a vitrine do site.
2. Clicar em `Página do produto` em um item.
3. Confirmar se abre `produto.html?id=...`.
4. Conferir nome, preço, descrição e estoque.
5. Clicar em `Comprar pelo WhatsApp`.
6. Confirmar se a mensagem inclui o link do produto.
7. Clicar em `Copiar link`.
8. Abrir um produto relacionado.
9. Testar no celular.

## Observações

- A página usa os produtos carregados pelo site.
- Produtos vindos da API funcionam quando o ID for mantido no formato usado pelo catálogo.
- Esta fase melhora campanhas e compartilhamento, mas ainda não adiciona SEO dinâmico por produto no servidor.
