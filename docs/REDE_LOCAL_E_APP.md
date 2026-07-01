# Mística Presentes em rede local e painel mobile

## Objetivo

Criar uma arquitetura cliente-servidor sem quebrar o sistema desktop atual.

Nesta primeira fase, a API e o painel são somente leitura. As vendas continuam sendo feitas no programa principal.

## O que foi criado

- Pasta `api/` com FastAPI.
- Painel web/mobile inicial.
- Rotas de leitura para vendas, caixa, estoque, contas e alertas da Isis.
- Atualização em tempo real via WebSocket.
- Script para iniciar o servidor local.
- Teste básico da API.

## Como instalar

Na pasta do projeto:

```bash
pip install -r requirements.txt
```

## Como iniciar o servidor

No computador principal da loja:

```bash
python scripts/iniciar_servidor_local.py
```

O terminal mostrará o endereço local e o endereço da rede.

## Como acessar na loja

Conecte o celular ou outro computador no mesmo Wi-Fi da loja e abra o endereço mostrado pelo servidor.

Exemplo de formato:

```text
http://IP-DO-COMPUTADOR-SERVIDOR:8000
```

## Segurança

Não coloque o banco SQLite diretamente em uma pasta compartilhada para vários computadores escreverem ao mesmo tempo.

Não abra porta do roteador diretamente para a internet.

Para acesso fora da loja, use uma solução segura como VPN, Tailscale ou Cloudflare Tunnel.

## Rotas principais

```text
GET /health
GET /api/dashboard
GET /api/vendas/hoje
GET /api/vendas/recentes
GET /api/vendas/cancelamentos
GET /api/caixa/status
GET /api/estoque/baixo
GET /api/contas/alertas
GET /api/alertas/isis
WS  /ws/dashboard
```

As rotas protegidas usam cabeçalho de token.

## Migração gradual recomendada

1. Painel mobile somente leitura.
2. Operações controladas de estoque via API.
3. Vendas via API.
4. Múltiplos caixas.
5. Migração para PostgreSQL ou MySQL.
6. Aplicativo PWA avançado ou app Android/iOS.

## Teste básico

```bash
python tests/api_smoke_test.py
```

Se aparecer OK, a API local respondeu corretamente.
