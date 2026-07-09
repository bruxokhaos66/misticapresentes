# Baixa controlada de estoque em pedidos

Esta fase protege o estoque dos pedidos criados pela Isis e pelo site.

## Regra

O estoque não é descontado quando a Isis cria o pedido.

A baixa acontece somente quando o pedido muda para um destes status:

- Pagamento confirmado
- Separando pedido

## Proteção contra baixa duplicada

A tabela `vendas` passa a usar:

- `estoque_baixado`
- `estoque_baixado_em`

Depois da primeira baixa, novas mudanças de status não descontam novamente.

## O que acontece se faltar estoque

A API retorna erro de estoque insuficiente e o status não deve ser confirmado até resolver o produto.

## Arquivo alterado

- `backend/order_status_routes.py`
