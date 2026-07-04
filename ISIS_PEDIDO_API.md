# Isis pedido na API

Esta fase permite que a Isis gere um pedido real no backend a partir de um kit sugerido.

Arquivos:

- isis-order-api.js
- product-extras.js

Funcionamento:

1. A Isis monta um kit.
2. O site mostra o botão `Gerar pedido na loja`.
3. O botão envia a venda para `POST /api/vendas`.
4. O pedido nasce com status `Aguardando pagamento`.
5. O WhatsApp abre com o número do pedido e os itens sugeridos.

Observação:

- O estoque não é baixado nessa etapa.
- A baixa fica para confirmação de pagamento ou separação do pedido.
