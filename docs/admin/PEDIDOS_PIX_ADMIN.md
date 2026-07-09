# Fase 3 - Pedidos, status e confirmação manual de Pix

Esta fase adiciona um painel de acompanhamento de pedidos dentro do Admin.

## Recursos adicionados

- Painel de pedidos no Admin.
- Padronização de status:
  - Aguardando pagamento
  - Pagamento confirmado
  - Separando pedido
  - Pronto para retirada
  - Entregue
  - Cancelado
- Botão para confirmar Pix manualmente.
- Botão para marcar pedido como pronto para retirada.
- Botão para cancelar pedido.
- Botão para enviar resumo/status pelo WhatsApp.
- Botão para imprimir pedido.
- Linha do tempo simples de alterações de status.

## Como acessar

Acesse o Admin usando:

```text
?admin=mistica
```

Depois faça login no painel.

## Como testar

1. Gerar uma venda pelo site.
2. Acessar o Admin.
3. Conferir se o pedido aparece no painel `Confirmação de Pix e status`.
4. Clicar em `Confirmar Pix`.
5. Confirmar se o status muda para `Pagamento confirmado`.
6. Clicar em `Pronto retirada`.
7. Confirmar se o status muda para `Pronto para retirada`.
8. Testar o botão WhatsApp.
9. Testar o botão Imprimir.
10. Testar Cancelar.

## Observações

- Esta fase controla os pedidos salvos localmente no navegador e os pedidos sincronizados no array `sales`.
- A confirmação automática de Pix ainda não foi implementada.
- Para produção real, o ideal é gravar mudanças de status também na API/backend.
