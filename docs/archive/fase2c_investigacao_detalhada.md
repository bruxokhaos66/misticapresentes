# Investigação detalhada — Fase 2C ampliada

- Banco analisado: C:\Users\fredi\Documents\mistica_gestao_v20.db
- Ação executada: apenas leitura, sem alterar dados nem schema.

## 1. Todas as vendas sem itens

Foram encontradas 11 vendas sem itens vinculados.

- id: 1 | cliente: Consumidor Final | data: 30/06/2026 13:45 | valor: 174.42 | status: Cancelado
- id: 2 | cliente: Consumidor Final | data: 30/06/2026 14:01 | valor: 18.0 | status: Cancelado
- id: 3 | cliente: Consumidor Final | data: 30/06/2026 14:14 | valor: 18.0 | status: Cancelado
- id: 4 | cliente: Fredi Bach | data: 30/06/2026 14:15 | valor: 18.0 | status: Cancelado
- id: 5 | cliente: Natalia Grunwald | data: 30/06/2026 14:24 | valor: 38.0 | status: Cancelado
- id: 6 | cliente: (vazio) | data: 30/06/2026 14:26 | valor: 73.644 | status: Cancelado
- id: 7 | cliente: fredi | data: 30/06/2026 14:50 | valor: 20.0 | status: Cancelado
- id: 8 | cliente: Natalia Grunwald | data: 30/06/2026 15:46 | valor: 190.0 | status: Cancelado
- id: 9 | cliente: Natalia Grunwald | data: 30/06/2026 15:47 | valor: 190.0 | status: Cancelado
- id: 10 | cliente: Consumidor Final | data: 30/06/2026 15:51 | valor: 47.0 | status: Cancelado
- id: 11 | cliente: Fredi Bach | data: 30/06/2026 16:28 | valor: 63.0 | status: Cancelado

## 2. Todas as vendas com datas inválidas

Foram encontradas 16 vendas com data_venda preenchida em formato legível, mas sem data_iso válida ou vazia.

- id: 1 | valor atual: 174.42 | data armazenada: 30/06/2026 13:45 | data_iso: null | status: Cancelado
- id: 2 | valor atual: 18.0 | data armazenada: 30/06/2026 14:01 | data_iso: null | status: Cancelado
- id: 3 | valor atual: 18.0 | data armazenada: 30/06/2026 14:14 | data_iso: null | status: Cancelado
- id: 4 | valor atual: 18.0 | data armazenada: 30/06/2026 14:15 | data_iso: null | status: Cancelado
- id: 5 | valor atual: 38.0 | data armazenada: 30/06/2026 14:24 | data_iso: null | status: Cancelado
- id: 6 | valor atual: 73.644 | data armazenada: 30/06/2026 14:26 | data_iso: null | status: Cancelado
- id: 7 | valor atual: 20.0 | data armazenada: 30/06/2026 14:50 | data_iso: null | status: Cancelado
- id: 8 | valor atual: 190.0 | data armazenada: 30/06/2026 15:46 | data_iso: null | status: Cancelado
- id: 9 | valor atual: 190.0 | data armazenada: 30/06/2026 15:47 | data_iso: null | status: Cancelado
- id: 10 | valor atual: 47.0 | data armazenada: 30/06/2026 15:51 | data_iso: null | status: Cancelado
- id: 11 | valor atual: 63.0 | data armazenada: 30/06/2026 16:28 | data_iso: null | status: Cancelado
- id: 12 | valor atual: 38.0 | data armazenada: 30/06/2026 17:16 | data_iso: null | status: Cancelado
- id: 13 | valor atual: 27.0 | data armazenada: 30/06/2026 21:32 | data_iso: null | status: Cancelado
- id: 14 | valor atual: 96.0 | data armazenada: 30/06/2026 22:25 | data_iso: null | status: Cancelado
- id: 15 | valor atual: 140.8 | data armazenada: 30/06/2026 22:31 | data_iso: null | status: Cancelado
- id: 16 | valor atual: 165.73225 | data armazenada: 30/06/2026 22:47 | data_iso: null | status: Cancelado

## 3. Verificação da coluna telephone versus telefone

Foi encontrada 1 diferença entre as colunas telephone e telefone.

- id: 1 | nome: Fredi Bach | telefone: 49984090802 | telephone: null

## 4. Classificação das ocorrências

- venda sem itens #1: venda cancelada
- venda sem itens #2: venda cancelada
- venda sem itens #3: venda cancelada
- venda sem itens #4: venda cancelada
- venda sem itens #5: venda cancelada
- venda sem itens #6: venda cancelada
- venda sem itens #7: venda cancelada
- venda sem itens #8: venda cancelada
- venda sem itens #9: venda cancelada
- venda sem itens #10: venda cancelada
- venda sem itens #11: venda cancelada
- venda com data inválida #1: venda cancelada
- venda com data inválida #2: venda cancelada
- venda com data inválida #3: venda cancelada
- venda com data inválida #4: venda cancelada
- venda com data inválida #5: venda cancelada
- venda com data inválida #6: venda cancelada
- venda com data inválida #7: venda cancelada
- venda com data inválida #8: venda cancelada
- venda com data inválida #9: venda cancelada
- venda com data inválida #10: venda cancelada
- venda com data inválida #11: venda cancelada
- venda com data inválida #12: venda cancelada
- venda com data inválida #13: venda cancelada
- venda com data inválida #14: venda cancelada
- venda com data inválida #15: venda cancelada
- venda com data inválida #16: venda cancelada
- cliente #1: dado legado
