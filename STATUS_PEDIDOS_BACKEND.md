# Fase 4 - Status de pedidos no backend

Esta fase leva o controle de status dos pedidos para a API/backend, evitando que o status fique apenas no navegador.

## Recursos adicionados

- Novo arquivo `backend/order_status_routes.py`.
- Rotas adicionadas:

```http
POST /api/pedidos/{venda_id}/status
GET /api/pedidos/{venda_id}/status
GET /api/pedidos/status-log
```

- Tabela automática para histórico:

```text
pedido_status_log
```

- O painel do Admin agora tenta salvar o status também na API.
- Se a API estiver offline, o status continua salvo localmente e aparece aviso na linha do tempo.

## Status aceitos

- Aguardando pagamento
- Pagamento confirmado
- Separando pedido
- Pronto para retirada
- Entregue
- Cancelado
- Concluído

## Segurança

A rota de alteração de status aceita a variável de ambiente:

```text
MISTICA_SITE_API_KEY
```

Quando configurada, o site precisa enviar:

```http
X-Mistica-Api-Key
```

## Como testar

1. Subir o backend.
2. Criar uma venda via site ou API.
3. Abrir Admin com `?admin=mistica`.
4. Alterar status do pedido.
5. Conferir no backend:

```http
GET /api/pedidos/{venda_id}/status
```

6. Confirmar que `vendas.status` foi atualizado.
7. Confirmar que `pedido_status_log` recebeu o histórico.

## Observação

Pedidos locais com ID não numérico, como `MISTICA123456789`, continuam com status local. Pedidos salvos na API com ID numérico são sincronizados com o backend.
