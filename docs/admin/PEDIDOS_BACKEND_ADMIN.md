# Pedidos conectados ao backend

Esta fase transforma o painel de pedidos em um painel conectado à API/backend.

## Recursos adicionados

### Backend

Rotas ampliadas em `backend/order_status_routes.py`:

```http
GET /api/pedidos
GET /api/pedidos/{venda_id}
POST /api/pedidos/{venda_id}/status
POST /api/pedidos/{venda_id}/observacao
DELETE /api/pedidos/{venda_id}
GET /api/pedidos/status-log
```

### Admin

O arquivo `pedido-status.js` agora:

- carrega pedidos da API;
- mostra itens da venda;
- atualiza status no backend;
- salva observação interna no backend;
- cancela pedido no backend;
- mantém fallback local se a API estiver offline;
- recarrega pedidos automaticamente.

## Status aceitos

- Aguardando pagamento
- Pagamento confirmado
- Separando pedido
- Pronto para retirada
- Entregue
- Cancelado
- Concluído

## Como testar

1. Subir a API.
2. Criar uma venda pelo site.
3. Abrir `?admin=mistica`.
4. Entrar no Admin.
5. Conferir se o painel mostra `Pedidos carregados da API`.
6. Alterar status do pedido.
7. Salvar uma observação interna.
8. Cancelar um pedido de teste.
9. Conferir no backend:

```http
GET /api/pedidos
GET /api/pedidos/{venda_id}
GET /api/pedidos/status-log
```

## Observações

- A exclusão do pedido no painel é cancelamento lógico: status `Cancelado`.
- O estoque não é revertido automaticamente ao cancelar; isso deve ser uma fase futura para evitar erro operacional.
- A integração com Pix continua manual.
