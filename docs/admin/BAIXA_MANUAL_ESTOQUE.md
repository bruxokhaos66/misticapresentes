# Baixa manual de estoque

Esta fase adiciona um botão no Admin para baixar estoque manualmente quando o pedido ainda estiver pendente.

## Backend

Novo endpoint:

`POST /api/pedidos/{venda_id}/baixar-estoque`

Ele usa a mesma proteção da baixa automática:

- verifica se o pedido existe;
- verifica se o estoque já foi baixado;
- valida estoque disponível;
- baixa uma única vez;
- registra log no histórico do pedido.

## Frontend

No painel de pedidos, quando o estoque ainda está pendente, aparece o botão:

`Baixar estoque`

Depois da baixa, o painel recarrega e mostra `Estoque baixado`.
