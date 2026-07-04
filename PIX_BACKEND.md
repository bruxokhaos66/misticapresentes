# Pix e pagamentos no backend

Esta fase adiciona registro profissional de pagamentos no backend.

## Recursos adicionados

Novo arquivo:

```text
backend/payment_routes.py
```

Novas rotas:

```http
POST /api/pagamentos
GET /api/pagamentos
PUT /api/pagamentos/{pagamento_id}/status
```

## O que o backend registra

- venda vinculada;
- forma de pagamento;
- valor;
- status do pagamento;
- identificação do comprovante;
- observação;
- usuário responsável;
- data e hora.

## Status de pagamento

- Aguardando
- Confirmado
- Recusado
- Cancelado
- Estornado

## Integração com pedidos

Quando um pagamento é registrado como `Confirmado`:

1. A venda recebe status `Pagamento confirmado`.
2. Um registro é criado no histórico do pedido.
3. O Admin recarrega os pedidos da API.

## Admin

No painel de pedidos, o botão antes chamado `Confirmar Pix` agora registra o pagamento em:

```http
POST /api/pagamentos
```

O Admin pode informar uma identificação simples do comprovante Pix.

## Segurança

Se `MISTICA_SITE_API_KEY` estiver configurada, as rotas sensíveis exigem:

```http
X-Mistica-Api-Key
```

## Como testar

1. Criar pedido pelo site.
2. Abrir Admin com `?admin=mistica`.
3. Clicar em `Registrar Pix`.
4. Informar identificação do comprovante.
5. Verificar se o pedido muda para `Pagamento confirmado`.
6. Conferir:

```http
GET /api/pagamentos?venda_id=ID_DO_PEDIDO
GET /api/pedidos/ID_DO_PEDIDO/status
```

## Observação

Esta fase ainda é confirmação manual. Integração automática com banco, webhook Pix ou PSP fica para fase futura.
