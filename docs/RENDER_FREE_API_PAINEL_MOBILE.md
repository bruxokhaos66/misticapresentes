# API online no Render Free

## Causa do problema

O Render Free pode reiniciar, dormir ou fazer redeploy da API. Como o plano Free nao oferece Persistent Disk, qualquer SQLite gravado no filesystem da API pode voltar vazio depois desses eventos.

Quando isso acontece, o painel mobile consulta a API online e passa a mostrar produtos, vendas ou faturamento zerados/incompletos, mesmo com o desktop local contendo os dados corretos.

## Solucao gratuita aplicada

O desktop continua sendo a fonte confiavel dos dados. A API agora aceita reparo por sincronizacao completa:

- usuarios do painel;
- produtos com atualizacao de preco, estoque e cadastro;
- vendas recentes com `local_id` e `origem_sync='desktop'`.

As vendas usam `local_id` para evitar duplicidade. Se a mesma venda local for enviada mais de uma vez, a API atualiza o registro existente em vez de duplicar.

O desktop diagnostica automaticamente quando a API esta indisponivel, zerada ou incompleta. A primeira verificacao roda ao abrir o programa e as proximas rodam a cada 10 minutos em segundo plano.

Se a API estiver zerada ou incompleta, o reparo roda sozinho:

- sincroniza usuarios;
- sincroniza produtos;
- sincroniza vendas;
- compara novamente depois.

Se uma verificacao ainda estiver rodando, a proxima e ignorada. Se a API estiver indisponivel, o programa nao trava e tenta de novo na proxima rodada.

O status aparece no painel como:

- `Painel Mobile: OK`
- `Painel Mobile: Verificando...`
- `Painel Mobile: Sincronizando...`
- `Painel Mobile: API zerada - reparando automaticamente`
- `Painel Mobile: API incompleta - reparando automaticamente`
- `Painel Mobile: API indisponivel`
- `Ultima verificacao: HH:MM`

## Comandos simples

Testar login, status e resumo do painel:

```bash
python tools/testar_painel_mobile.py
```

Comparar desktop com API/app:

```bash
python tools/comparar_dashboard_app.py
```

Reparar a API online manualmente, apenas se quiser forcar um teste:

```bash
python tools/reparar_api_painel_mobile.py
```

Sincronizacao direta, se precisar:

```bash
python tools/sincronizar_painel_online.py
```

## Solucao definitiva

Para eliminar a perda de banco no servidor, use uma destas opcoes:

1. Render pago com Persistent Disk e `MISTICA_DB_PATH=/data/mistica_gestao_v20.db`.
2. PostgreSQL gerenciado e uma futura configuracao `DATABASE_URL`.

Hoje o sistema usa SQLite local e online. Para PostgreSQL, sera necessario criar uma camada de banco que detecte `DATABASE_URL`, use driver PostgreSQL na API online, mantenha SQLite no desktop local e rode migracoes equivalentes para tabelas de produtos, usuarios, vendas e itens de venda.

Enquanto `DATABASE_URL` nao estiver implementado, nao configure essa variavel esperando troca automatica de banco. Use `MISTICA_DB_PATH` ou `DATABASE_PATH` apenas para SQLite.
