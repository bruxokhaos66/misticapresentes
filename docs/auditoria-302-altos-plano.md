# Issue #302 — correções altas de pedidos

## Objetivo

Eliminar os dois achados altos da primeira varredura pós-merge sem alterar outros subsistemas:

1. enumeração pública do histórico de pedidos por ID;
2. criação duplicada de pedidos/reservas por ausência de idempotência no checkout público.

## Correção 1 — acompanhamento protegido

- `GET /api/pedidos/{id}/status` deverá aceitar acesso somente quando:
  - o `txid` informado corresponder ao `pix_txid` persistido do pedido; ou
  - houver sessão/chave administrativa válida.
- Comparação de `txid` em tempo constante.
- Resposta 403 genérica quando o código estiver ausente ou incorreto.
- O frontend deverá guardar apenas em memória o `txid` retornado na criação e enviá-lo ao consultar o status.

## Correção 2 — idempotência ponta a ponta

- A rota pública deverá receber `Idempotency-Key` e propagá-la tanto para pedidos normais quanto para encomendas.
- O frontend deverá gerar uma chave aleatória por tentativa de checkout e reutilizá-la durante retries da mesma submissão.
- Pedidos sob encomenda deverão usar o mesmo armazenamento idempotente já utilizado pelo fluxo normal.
- A mesma chave com o mesmo pedido deve devolver a resposta original sem nova inserção nem nova reserva.

## Testes obrigatórios

- status sem `txid`: 403;
- status com `txid` incorreto: 403;
- status com `txid` correto: 200;
- sessão/chave administrativa continua acessando o status;
- duas submissões normais com a mesma chave criam um único pedido e uma única reserva;
- duas submissões sob encomenda com a mesma chave criam um único pedido;
- chaves diferentes continuam criando pedidos independentes;
- API, Playwright e Lighthouse verdes.

## Regra de merge

Manter o PR como draft até todos os testes passarem e a issue #302 receber evidências da correção. Não incluir os achados médios de SQLite/backup neste PR.