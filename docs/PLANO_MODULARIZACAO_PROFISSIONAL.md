# Plano de modularização profissional

## Objetivo

Reduzir a dependência do arquivo grande `mistica_presentes.py` e deixar o sistema mais fácil de manter, testar e evoluir.

## Já iniciado

O sistema já possui módulos separados para:

- API local;
- serviços de venda;
- serviços de caixa;
- repositórios de venda e estoque;
- relatórios;
- backup;
- servidor dedicado;
- app Android;
- auditoria de acesso da API.

## Próximas extrações recomendadas

### 1. Autenticação e usuários

Criar módulos dedicados:

```text
services/auth_service.py
repositories/usuarios.py
```

### 2. Telas do desktop

Separar cada aba em arquivo próprio:

```text
ui/vendas_tab.py
ui/estoque_tab.py
ui/clientes_tab.py
ui/caixa_tab.py
ui/isis_tab.py
```

### 3. Configuração

Centralizar configuração em:

```text
services/config_service.py
```

### 4. Testes

Criar testes para:

```text
tests/test_vendas.py
tests/test_caixa.py
tests/test_estoque.py
tests/test_api_security.py
```

### 5. API futura de escrita

Só liberar venda/estoque/caixa pela rede depois de:

- autenticação por usuário;
- permissão por perfil;
- logs completos;
- backup antes de operações críticas;
- testes automatizados.

## Observação

A modularização deve ser feita em etapas pequenas para não quebrar o sistema da loja em produção.
