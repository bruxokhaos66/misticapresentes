# Relatorio - Pre-consolidacao de patches runtime

Data: 2026-07-09
Branch: `main`
Repositorio: `bruxokhaos66/misticapresentes`

## Objetivo

Registrar a analise inicial dos arquivos `patch` carregados em runtime pelo `app.py` antes de iniciar a consolidacao no codigo principal.

A limpeza estrutural da `main` ja foi concluida. Agora a pendencia principal e reduzir a dependencia de patches aplicados dinamicamente.

## Estado atual observado

O `app.py` ainda le `mistica_presentes.py` como texto e aplica uma sequencia de patches antes de compilar/executar o codigo.

Patches carregados:

- `app_backup_inicializacao_patch.py`
- `app_runtime_patch.py`
- `app_pagamento_misto_patch.py`
- `app_backup_painel_patch.py`
- `app_manutencao_segura_patch.py`
- `app_sync_status_patch.py`
- `app_painel_guard_patch.py`
- `app_scroll_patch.py`

## Analise dos patches ja inspecionados

### `app_scroll_patch.py`

Finalidade:

- Adicionar barras de rolagem em tabelas principais.
- Corrigir comportamento em que substituicoes nao eram aplicadas quando `adicionar_barra_rolagem_tree` ja existia no app principal.

Risco:

- Baixo.
- Alteracoes focadas em interface.
- Precisa de teste visual no Windows.

Observacao:

- O metodo `adicionar_barra_rolagem_tree` ja existe em `mistica_presentes.py`, mas a versao do app principal e mais simples.
- A versao do patch adiciona rolagem vertical, horizontal e suporte ao mouse wheel.

### `app_painel_guard_patch.py`

Finalidade:

- Proteger o painel mobile quando a API reinicia ou aparece zerada/incompleta.
- Adicionar verificacao automatica periodica.
- Atualizar status visual do painel mobile.

Risco:

- Medio.
- Depende de `services.painel_online_guard`.
- Deve ser testado com API online e com API temporariamente indisponivel.

### `app_sync_status_patch.py`

Finalidade:

- Ajustar mensagem do dashboard.
- Usar `services.dashboard_message_service.mensagem_atual`.
- Buscar frase online em segundo plano.
- Reaplicar parte do guard do painel mobile.

Risco:

- Medio.
- Pode duplicar logica do `app_painel_guard_patch.py`.
- Deve ser consolidado depois do guard para evitar sobreposicao.

### `app_runtime_patch.py`

Finalidade:

- Tornar backup de venda assíncrono.
- Remover popup extra de venda salva.
- Aplicar icone unico do app.
- Ajustar visual do Dashboard.
- Adicionar sincronizacao automatica de usuarios.
- Adicionar painel de vendas do dia.
- Atualizar cards do dashboard sem reconstruir toda a tela.

Risco:

- Alto.
- E um patch grande e mistura varias responsabilidades.
- Deve ser quebrado em partes menores antes da consolidacao completa.

## Estrategia recomendada

A consolidacao nao deve ser feita apagando patch de uma vez.

Ordem segura:

1. Consolidar apenas `app_scroll_patch.py`.
2. Testar localmente rolagem em Vendas, Estoque, Logs e Dashboard.
3. Remover a chamada de `app_scroll_patch` no `app.py`.
4. Rodar teste local.
5. Gerar relatorio da etapa.
6. So depois excluir `app_scroll_patch.py`.

Depois repetir para os outros patches.

## Por que nao remover agora

Remover qualquer patch agora sem incorporar a logica no arquivo principal pode quebrar funcionalidades ja ativas no programa.

Tambem nao e seguro consolidar todos os patches de uma vez porque:

- `app_runtime_patch.py` altera venda, dashboard, sincronizacao e icone;
- `app_sync_status_patch.py` chama logica do painel guard;
- `app_painel_guard_patch.py` depende de servicos online;
- a validacao correta exige abrir e testar o app no Windows.

## Issue de acompanhamento

Foi criada a issue:

- `#215 - Refatoração: consolidar patches runtime e arquivos -fix no código principal`

## Proxima acao

Preparar a consolidacao do `app_scroll_patch.py` em uma etapa pequena e reversivel, preferencialmente em uma branch separada ou com teste local imediato apos o commit.
