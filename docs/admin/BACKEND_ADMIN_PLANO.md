# Plano técnico — Admin seguro e banco de dados

Este documento define o próximo passo para transformar o Admin da Mística Presentes em uma área realmente segura e persistente.

## Por que isso é necessário

Hoje parte dos dados administrativos ainda depende do navegador. Isso é útil para protótipo, mas não é ideal para operação real da loja.

Riscos atuais:

- senha ou regra de acesso no front-end pode ser vista no código;
- limpar navegador pode apagar dados locais;
- outro computador não enxerga os mesmos dados;
- não há controle real de usuários e permissões;
- não há histórico confiável por operador.

## Objetivo da próxima fase

Criar um backend com:

- login real;
- sessão ou token seguro;
- banco de dados;
- rotas protegidas para Admin;
- separação entre site público e área administrativa;
- trilha de auditoria de alterações.

## Tabelas recomendadas

### users

- id
- name
- email
- password_hash
- role
- active
- created_at
- updated_at

### products

- id
- name
- category
- description
- price
- cost
- margin
- stock
- tag
- image_url
- external_url
- active
- created_at
- updated_at

### stock_movements

- id
- product_id
- type: entrada, venda, cancelamento, ajuste
- quantity
- cost
- price
- note
- user_id
- created_at

### customers

- id
- name
- whatsapp
- email
- notes
- created_at
- updated_at

### sales

- id
- customer_id
- status
- payment_method
- total
- user_id
- created_at
- updated_at

### sale_items

- id
- sale_id
- product_id
- product_name
- quantity
- price
- cost
- total

### special_orders

- id
- customer_name
- whatsapp
- item
- status
- expected_date
- notes
- created_at
- updated_at

### audit_logs

- id
- user_id
- action
- entity
- entity_id
- before_json
- after_json
- created_at

## Rotas mínimas da API

### Autenticação

- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/me

### Produtos e estoque

- GET /api/products
- POST /api/products
- PATCH /api/products/:id
- POST /api/products/:id/stock-entry
- GET /api/stock-movements

### Clientes

- GET /api/customers
- POST /api/customers
- PATCH /api/customers/:id

### Vendas

- GET /api/sales
- POST /api/sales
- PATCH /api/sales/:id/status
- POST /api/sales/:id/cancel

### Relatórios

- GET /api/reports/sales
- GET /api/reports/payments
- GET /api/reports/cash-closing
- GET /api/reports/top-products
- GET /api/reports/vip-customers
- GET /api/reports/slow-products

## Migração do localStorage para banco

1. Exportar backup atual pelo painel.
2. Validar JSON de produtos, estoque, clientes, vendas e encomendas.
3. Criar script de importação.
4. Inserir dados no banco.
5. Conferir totais de vendas e estoque.
6. Trocar leitura do front-end para API.
7. Manter backup local apenas como emergência.

## Ações que precisam ser feitas fora do código front-end

- escolher hospedagem/backend;
- definir banco: PostgreSQL, MySQL ou SQLite inicial;
- criar senha forte de Admin;
- definir usuários da loja;
- configurar variáveis em `.env` real no servidor;
- ativar HTTPS no domínio.

## Próximo PR recomendado

Criar `.env.example`, `api-contract.md` e iniciar um backend simples com login e banco SQLite ou PostgreSQL.
