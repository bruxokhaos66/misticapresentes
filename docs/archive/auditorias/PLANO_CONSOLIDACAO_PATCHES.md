# Plano de consolidacao de patches

Data: 2026-07-09

## Objetivo

Reduzir a dependencia de alteracoes aplicadas em tempo de execucao e incorporar correcoes estaveis nos arquivos principais do projeto.

## Estado atual observado

O arquivo `app.py` carrega `mistica_presentes.py` como texto, aplica patches em tempo de execucao e depois executa o codigo compilado.

Patches carregados atualmente:

- `app_runtime_patch.py`
- `app_sync_status_patch.py`
- `app_painel_guard_patch.py`
- `app_scroll_patch.py`

## Por que consolidar

O modelo atual ajuda a aplicar correcoes sem reescrever o arquivo principal, mas aumenta complexidade para manutencao futura.

Riscos do modelo atual:

- alteracoes por `replace` podem falhar se o texto do arquivo principal mudar;
- fica mais dificil entender onde uma funcionalidade realmente nasceu;
- testes ficam menos claros;
- build e instalador precisam carregar os patches corretamente;
- novos desenvolvimentos podem conflitar com correcoes aplicadas em runtime.

## Consolidacao recomendada por ordem

### 1. `app_scroll_patch.py`

Baixo risco relativo.

Incorporar diretamente em `mistica_presentes.py`:

- chamadas de `self.adicionar_barra_rolagem_tree(...)` nas tabelas principais;
- metodo `adicionar_barra_rolagem_tree` se ainda nao estiver completo no arquivo principal.

Depois testar:

- vendas;
- estoque;
- logs;
- dashboard;
- metas de vendedores;
- rolagem vertical e horizontal.

### 2. `app_painel_guard_patch.py`

Risco medio.

Incorporar:

- metodos de verificacao do painel mobile;
- agendamento periodico de verificacao;
- atualizacao do status visual do painel;
- verificacao apos abertura, login e venda.

Depois testar:

- abertura do programa;
- login;
- venda;
- API online;
- API offline;
- API zerada/incompleta.

### 3. `app_sync_status_patch.py`

Risco medio.

Incorporar:

- uso de `services.dashboard_message_service`;
- mensagem da Isis por bloco de horario;
- busca online em segundo plano;
- agendamento de atualizacao.

Depois testar:

- dashboard;
- frase motivacional;
- funcionamento offline;
- travamentos de interface.

### 4. `app_runtime_patch.py`

Risco maior.

Esse patch altera comportamento de venda, backup, icone, cards do dashboard e outros ajustes visuais. Deve ser consolidado por partes, com commit separado para cada bloco.

Sequencia sugerida:

1. icone do aplicativo;
2. backup em thread;
3. remocao de popup apos venda;
4. cards do dashboard;
5. demais ajustes visuais.

## Regra para cada consolidacao

1. Aplicar apenas um patch por vez.
2. Rodar o programa localmente.
3. Testar fluxo minimo.
4. Commitar.
5. So entao remover a chamada do patch em `app.py`.
6. Remover o arquivo patch somente depois de confirmar que a funcao esta dentro do arquivo principal.

## Teste minimo apos cada etapa

- abrir programa;
- fazer login;
- abrir dashboard;
- abrir caixa;
- cadastrar produto de teste;
- vender produto;
- cancelar venda;
- conferir estoque;
- conferir painel/API se estiver online;
- fechar e abrir novamente.

## Status

Nao foi aplicada consolidacao automatica neste momento para evitar quebrar o programa principal sem teste local. A proxima etapa deve ser feita com apoio do Codex/local, aplicando um patch por vez e validando no Windows antes de remover arquivos.
