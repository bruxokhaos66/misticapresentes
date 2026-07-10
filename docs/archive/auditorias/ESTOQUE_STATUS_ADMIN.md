# Status de estoque no Admin

Esta fase mostra no painel de pedidos se o estoque do pedido já foi baixado.

Recursos:

- Lê `estoque_baixado` da API.
- Lê `estoque_baixado_em` da API.
- Mostra `Estoque baixado` ou `Estoque pendente` em cada pedido.
- Mostra contador de pedidos com estoque baixado.
- Inclui o status de estoque na mensagem enviada pelo WhatsApp.

Objetivo:

Evitar que o operador baixe estoque mais de uma vez ou separe pedido que ainda não teve estoque confirmado.

Arquivo alterado:

- `pedido-status.js`
