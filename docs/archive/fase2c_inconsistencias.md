# Fase 2C — Relatório de inconsistências

- Banco analisado: C:\Users\fredi\Documents\mistica_gestao_v20.db
- Ação executada: apenas leitura, sem alterar dados nem schema.

## BAIXO — Produtos duplicados
- Nenhum produto duplicado encontrado.

## BAIXO — Produtos sem código
- Nenhum produto sem código encontrado.

## BAIXO — Estoque negativo
- Nenhum produto com estoque negativo encontrado.

## ALTO — Vendas sem itens
- {"id": 1, "total_final": 174.42}
- {"id": 2, "total_final": 18.0}
- {"id": 3, "total_final": 18.0}
- {"id": 4, "total_final": 18.0}
- {"id": 5, "total_final": 38.0}
- {"id": 6, "total_final": 73.644}
- {"id": 7, "total_final": 20.0}
- {"id": 8, "total_final": 190.0}
- {"id": 9, "total_final": 190.0}
- {"id": 10, "total_final": 47.0}
- {"id": 11, "total_final": 63.0}

## BAIXO — Itens sem venda
- Nenhum item sem venda encontrado.

## BAIXO — Itens com produto inexistente
- Todos os itens referenciam produtos existentes.

## BAIXO — Movimentações com produto inexistente
- Todas as movimentações referenciam produtos existentes.

## BAIXO — Fluxo de caixa sem caixa
- Nenhum fluxo de caixa aponta para caixa inexistente.

## BAIXO — Vendas com total negativo
- Nenhuma venda com total negativo encontrada.

## ALTO — Vendas com datas inválidas ou vazias
- {"id": 1, "data_venda": "30/06/2026 13:45", "data_iso": null}
- {"id": 2, "data_venda": "30/06/2026 14:01", "data_iso": null}
- {"id": 3, "data_venda": "30/06/2026 14:14", "data_iso": null}
- {"id": 4, "data_venda": "30/06/2026 14:15", "data_iso": null}
- {"id": 5, "data_venda": "30/06/2026 14:24", "data_iso": null}
- {"id": 6, "data_venda": "30/06/2026 14:26", "data_iso": null}
- {"id": 7, "data_venda": "30/06/2026 14:50", "data_iso": null}
- {"id": 8, "data_venda": "30/06/2026 15:46", "data_iso": null}
- {"id": 9, "data_venda": "30/06/2026 15:47", "data_iso": null}
- {"id": 10, "data_venda": "30/06/2026 15:51", "data_iso": null}
- {"id": 11, "data_venda": "30/06/2026 16:28", "data_iso": null}
- {"id": 12, "data_venda": "30/06/2026 17:16", "data_iso": null}
- {"id": 13, "data_venda": "30/06/2026 21:32", "data_iso": null}
- {"id": 14, "data_venda": "30/06/2026 22:25", "data_iso": null}
- {"id": 15, "data_venda": "30/06/2026 22:31", "data_iso": null}
- {"id": 16, "data_venda": "30/06/2026 22:47", "data_iso": null}

## BAIXO — Clientes duplicados
- Nenhum cliente duplicado encontrado.

## MÉDIO — Coluna telephone duplicada/legada
- A tabela clientes possui a coluna telephone, que pode ser um campo legado/duplicado de telefone.

