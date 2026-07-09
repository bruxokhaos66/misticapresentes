# Testes manuais - Estoque do site

## Fluxo oficial

O site deve finalizar venda chamando somente:

```text
POST /api/vendas
```

O endpoint `/api/estoque/reservar` fica disponível apenas para testes, reserva manual ou uso futuro. Ele não deve ser usado automaticamente pelo site para evitar baixa dupla de estoque.

## Status usados

- Aguardando pagamento
- Pagamento confirmado
- Separando pedido
- Pronto para retirada
- Entregue
- Cancelado

## Teste 1 - Venda normal

1. Criar produto com estoque 10.
2. Vender 2 pelo site.
3. Resultado esperado: estoque final 8.
4. A venda deve aparecer em `/api/vendas`.
5. Deve existir registro em `movimentacao_estoque`.

## Teste 2 - Estoque insuficiente

1. Criar produto com estoque 1.
2. Tentar vender 2 pelo site.
3. Resultado esperado: API retorna erro de estoque insuficiente.
4. A venda não deve ser salva.
5. O estoque deve continuar 1.

## Teste 3 - API offline

1. Desligar API.
2. Gerar venda pelo site.
3. Resultado esperado: o site salva localmente e mostra aviso para conferir estoque manualmente.

## Teste 4 - Vitrine pública

1. Abrir o site sem parâmetro.
2. Resultado esperado: a seção Administração não aparece.

## Teste 5 - Acesso interno

1. Abrir o site com `?admin=mistica`.
2. Resultado esperado: a seção Administração aparece.

## Segurança

A API aceita a variável de ambiente `MISTICA_SITE_API_KEY`.

Quando configurada no servidor, o site deve enviar o header `X-Mistica-Api-Key`.

Não colocar chave real dentro do código do GitHub.
