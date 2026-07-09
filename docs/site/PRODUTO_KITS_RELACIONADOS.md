# Produto, kits e relacionados

Esta etapa adiciona recursos comerciais ao catálogo sem trocar toda a estrutura do site.

## Recursos adicionados

- Botão `Ver detalhes` nos cards de produto.
- Modal com informações principais do produto.
- Produtos relacionados por categoria.
- Seção de kits prontos:
  - Kit Proteção
  - Kit Limpeza Energética
  - Kit Presente Místico
- Botão para adicionar uma sugestão de kit ao carrinho.

## Como testar

1. Abrir a vitrine.
2. Verificar se aparece a seção `Kits prontos` antes da grade de produtos.
3. Clicar em `Adicionar sugestão` em um kit.
4. Confirmar se os itens sugeridos entram no carrinho.
5. Clicar em `Ver detalhes` em um produto.
6. Confirmar se abre o modal do produto.
7. Conferir se aparecem produtos relacionados.
8. Testar fechamento do modal clicando no `X` ou fora da janela.

## Observações

- Os kits são sugestões automáticas baseadas em termos dos produtos cadastrados.
- Produtos relacionados usam a categoria atual.
- Esta fase ainda não cria uma URL dedicada real por produto; por enquanto usa modal de detalhes.
