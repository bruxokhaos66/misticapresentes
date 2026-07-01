# Plano futuro: banco servidor / API para Mística Presentes

Este documento é um planejamento técnico para quando a loja precisar usar o sistema em mais de um computador ao mesmo tempo.

## Situação atual

O sistema usa SQLite local. Para um computador principal, isso é simples, rápido e funciona bem.

Para vários computadores em rede, SQLite pode funcionar em casos pequenos, mas não é a melhor solução profissional. Pode haver travamentos, lentidão, conflito de escrita ou risco de corrupção se a rede cair durante gravações.

## Objetivo futuro

Criar uma API central para controlar:

- produtos;
- estoque;
- vendas;
- caixa;
- clientes;
- fornecedores;
- usuários;
- permissões;
- logs;
- relatórios;
- Isis.

## Arquitetura recomendada

```text
Computador da loja / Caixa / Notebook
        ↓
Aplicativo Mística Presentes
        ↓
API local ou servidor em nuvem
        ↓
Banco PostgreSQL ou MySQL
```

## Etapa 1 — Preparar o sistema atual

- Separar regras de negócio em serviços.
- Evitar SQL direto na tela.
- Manter backups automáticos.
- Garantir logs de auditoria.
- Criar testes automáticos para venda, cancelamento, estoque e caixa.

## Etapa 2 — Criar API

Sugestão gratuita/local:

- Python + FastAPI.
- Banco PostgreSQL local ou em VPS.
- Autenticação com login e token.
- Rotas REST para produtos, vendas, caixa e clientes.

Exemplos de rotas:

```text
POST /login
GET /produtos
POST /produtos
PATCH /produtos/{codigo}/estoque
POST /vendas
POST /vendas/{id}/cancelar
GET /caixa/aberto
POST /caixa/abrir
POST /caixa/fechar
GET /relatorios/vendas
```

## Etapa 3 — Sincronização e segurança

- Permitir vários usuários conectados.
- Bloquear venda se estoque mudar no mesmo momento.
- Registrar IP, usuário e horário em logs.
- Backup automático do banco servidor.
- Controle de permissões: vendedor, gerente, administrador.

## Etapa 4 — Isis integrada à API

A Isis poderá consultar a API para:

- analisar vendas;
- prever reposição;
- buscar erros;
- sugerir compras;
- auditar caixa;
- ajudar no atendimento.

## Recomendação atual

Enquanto o sistema for usado em apenas um computador principal, SQLite continua aceitável.

Se for usar em 2 ou mais computadores ao mesmo tempo, o próximo passo profissional é migrar para API + banco servidor.
