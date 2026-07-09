# Auditoria profunda do sistema Mística Presentes

Data: 03/07/2026

## Veredito geral

Status: **aprovado para uso interno com atenção em pontos pendentes**.

A auditoria revisou programa desktop, caixa, vendas, cancelamento, estoque, sincronização, API, instalador, painel mobile, Isis, botões e barras.

## Correções aplicadas nesta rodada

### 1. Barras de rolagem do desktop

Arquivo corrigido: `app_scroll_patch.py`

Problema encontrado: o patch retornava cedo quando encontrava `def adicionar_barra_rolagem_tree(self, tree):` no programa principal. Como esse método já existe em `mistica_presentes.py`, as substituições que adicionam barras nas tabelas não eram executadas.

Correção aplicada: o patch agora aplica as substituições mesmo quando o método já existe.

Status: **corrigido**.

### 2. Cancelamento de venda no desktop

Arquivo corrigido: `services/venda_service.py`

Problema encontrado: o cancelamento devolvia estoque, marcava a venda como cancelada e registrava saída no caixa, mas não tentava reenviar a alteração para a API.

Correção aplicada: após cancelar uma venda, o sistema agora chama a sincronização da venda novamente para o painel/app receber a alteração de status.

Status: **corrigido parcialmente**.

Ponto pendente: a API ainda precisa aceitar atualização de uma venda que já foi sincronizada antes. Sem isso, o app pode manter uma venda antiga como concluída mesmo depois do cancelamento local.

## Auditoria por módulo

### Caixa

Arquivos revisados: `services/caixa_service.py`, `services/venda_service.py`.

Pontos positivos:

- Não permite venda sem caixa aberto.
- Não permite cancelamento sem caixa aberto.
- Abertura de caixa cria fluxo inicial.
- Fechamento calcula entradas, saídas e formas de pagamento.
- Fechamento conferido grava valores informados e diferença de caixa.

Risco encontrado:

- O cálculo de cartão considera taxas dentro do total final da venda. Confirmar se a loja repassa taxa ao cliente ou se a taxa é custo interno.

Status: **operacional, com regra financeira a confirmar**.

### Vendas

Arquivo revisado: `services/venda_service.py`.

Pontos positivos:

- Valida carrinho vazio.
- Valida estoque antes da venda.
- Usa transação: se erro ocorrer, desfaz venda e estoque.
- Baixa estoque dentro da mesma transação da venda.
- Registra item, fluxo de caixa e movimentação de estoque.

Correção aplicada:

- Cancelamento agora tenta sincronizar a venda cancelada com a API.

Status: **corrigido no desktop**.

### Cancelamento / estorno

Arquivo revisado: `services/venda_service.py`.

Pontos positivos:

- Bloqueia cancelamento duplicado.
- Devolve estoque dos itens vendidos.
- Registra movimentação de estoque tipo `Cancelamento`.
- Cria saída no fluxo de caixa.

Ponto pendente crítico:

- `backend/main.py` precisa atualizar vendas já existentes por `local_id` quando a venda local mudar para cancelada.

Status: **desktop corrigido; API ainda precisa de ajuste**.

### Estoque

Arquivos revisados: `services/estoque_service.py`, `repositories/estoque.py`, `repositories/produtos.py`.

Pontos positivos:

- Não permite venda acima do estoque.
- Soma itens iguais no carrinho antes de validar.
- Baixa estoque com condição SQL para não ficar negativo.
- Inventário registra diferença e movimentação.
- Inativação de produto preserva histórico.

Status: **operacional**.

### Faturamento

Arquivos revisados: `services/venda_service.py`, `services/caixa_service.py`, `backend/main.py`.

Pontos positivos:

- Faturamento do painel ignora vendas canceladas.
- Vendas concluídas entram no fluxo de caixa.
- Estorno entra como saída.

Risco encontrado:

- A API precisa receber a mudança de status no cancelamento para o painel online não contar venda cancelada.

Status: **desktop operacional; painel online depende do ajuste pendente da API**.

### Sincronização

Arquivo revisado: `services/sync_service.py`.

Pontos positivos:

- Vendas são enfileiradas para sincronização.
- Falhas de internet não impedem a venda local.
- Pendências ficam registradas para tentativa posterior.
- Status online/offline é calculado pela API.

Risco encontrado:

- Venda já sincronizada é tratada pela API como duplicada e não atualiza status.

Status: **funcional para novas vendas; pendente para cancelamento de venda já enviada**.

### API / servidor

Arquivos revisados: `backend/main.py`, `backend/user_sync_routes.py`, `servidor_app.py`.

Pontos positivos:

- API possui rotas de login, status, produtos, clientes, vendas e estoque baixo.
- Rota de sincronização de usuários existe.
- Servidor local inicia `backend.main:app` em `127.0.0.1:8000`.

Pendência:

- Ajustar `salvar_venda_online` para atualizar venda existente por `local_id` quando o status mudar.

Status: **operacional, com correção recomendada**.

### Painel mobile / app

Arquivos revisados: `painel/index.html`, `config.py`, arquivos de configuração.

Pontos positivos:

- Painel correto é `https://misticaesotericos.com.br/painel/`.
- API correta é `https://api.misticaesotericos.com.br`.
- Login usa a API oficial.

Pendências conhecidas:

- Confirmar visualmente a opção de visualizar campo protegido no login.
- Frajola precisa ser reinserido no layout atual se o Codex ainda não tiver reaplicado.

Status: **operacional, com melhorias visuais pendentes**.

### Isis

Arquivos revisados de forma estrutural: `services/isis_service.py`, `isis/*`, `app_sync_status_patch.py`.

Pontos positivos:

- Isis possui comandos, memória, pesquisa, diagnóstico e mensagens do dashboard.
- Frases do dashboard foram movidas para serviço próprio.

Risco:

- Como várias funções da Isis são opcionais e dependem de serviços externos/internet, falhas devem continuar sendo tratadas sem travar o sistema.

Status: **operacional, manter logs observados**.

### Instalador / atualização online

Arquivos revisados: `.github/workflows/build-instalador-windows.yml`, `installer/*`, `MisticaPresentes_CORRETO.spec`.

Pontos positivos:

- Workflow automático ficou verde no GitHub Actions.
- Instalador local foi gerado com sucesso.
- Pacote inclui programa principal e servidor do aplicativo.
- Atualizador online foi criado.

Status: **aprovado**.

### Botões e barras

Arquivos revisados: `mistica_presentes.py`, `app_scroll_patch.py`, `app_runtime_patch.py`.

Correção aplicada:

- Barras de rolagem não eram aplicadas por retorno antecipado no patch. Corrigido.

Pendências:

- Confirmar visualmente no programa se as barras apareceram nas listas principais.
- Confirmar retorno da barra/aba Frajola.

Status: **corrigido parcialmente; requer teste visual**.

## Pendências para aprovação total

1. Ajustar API para atualizar venda já sincronizada quando o desktop enviar status cancelado.
2. Confirmar se a taxa de cartão deve somar no total final ou ser custo interno da loja.
3. Confirmar visualmente a opção de visualizar campo protegido no login do desktop e painel mobile.
4. Confirmar retorno da barra/aba Frajola.
5. Rodar novo build do EXE e instalador.

## Testes recomendados

```bash
cd /c/Users/fredi/BruxoBR/misticapresentes
git pull origin main
python app.py
```

Teste manual:

1. Abrir caixa.
2. Fazer venda de produto com estoque.
3. Verificar baixa no estoque.
4. Cancelar venda.
5. Verificar retorno do estoque.
6. Verificar saída de estorno no caixa.
7. Rodar sincronização pendente.
8. Conferir painel online.

Gerar EXE correto:

```bash
./installer/Gerar_EXE_CORRETO_Area_Trabalho.bat
```

Gerar instalador:

```bash
./installer/Gerar_Instalador_Area_Trabalho.bat
```

## Conclusão

O sistema está em bom estado para teste interno e uso controlado. Foram encontrados e corrigidos problemas reais em barras de interface e sincronização local de cancelamentos. Ainda falta corrigir a API para aceitar atualização de vendas já sincronizadas, o que é importante para que o painel online reflita cancelamentos corretamente.
