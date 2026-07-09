# Integração Programa da Loja + Site Mística Presentes

Este arquivo descreve como o programa da loja deve conversar com o site para sincronizar produtos, vendas e estoque.

## Objetivo

Quando uma venda for feita no site, o estoque do programa da loja deve baixar automaticamente, desde que o produto exista no estoque da loja.

Quando uma venda for feita no programa da loja, o site deve receber o estoque atualizado na próxima sincronização.

## Endereço da API

O site está configurado para usar:

```text
https://api.misticaesotericos.com.br
```

Esse endereço deve apontar para o backend/API do programa da loja.

## Fluxo correto

1. O programa da loja mantém o cadastro real dos produtos.
2. O site busca produtos em `/api/produtos`.
3. O cliente adiciona itens ao carrinho no site.
4. Ao gerar Pix/venda, o site envia a venda para `/api/vendas`.
5. O site também tenta reservar/baixar estoque em `/api/estoque/reservar`.
6. A API baixa o estoque no banco do programa.
7. O site sincroniza novamente e mostra o estoque atualizado.

## Endpoints necessários

### 1. Status da API

```http
GET /api/status
```

Resposta esperada:

```json
{
  "ok": true,
  "produtos": 120,
  "vendas": 50
}
```

### 2. Listar produtos

```http
GET /api/produtos?limite=500
```

Resposta esperada:

```json
[
  {
    "id": 1,
    "codigo_p": "INC001",
    "nome": "Incenso Natural",
    "categoria": "Incensos",
    "descricao": "Incenso para harmonização do ambiente",
    "preco": 12.9,
    "quantidade": 30,
    "imagem": "https://exemplo.com/foto.jpg",
    "imagens": [
      "https://exemplo.com/foto1.jpg",
      "https://exemplo.com/foto2.jpg"
    ]
  }
]
```

Campos importantes:

- `id`: ID interno do banco.
- `codigo_p`: código usado pelo programa da loja.
- `nome`: nome do produto.
- `preco`: valor de venda.
- `quantidade`: estoque atual.

### 3. Registrar venda do site

```http
POST /api/vendas
```

Payload enviado pelo site:

```json
{
  "origem": "site",
  "cliente": "Pedido site/celular",
  "subtotal": 25.8,
  "desconto": 0,
  "taxa": 0,
  "total_final": 25.8,
  "forma_pagamento": "Pix site/celular",
  "vendedor": "Site/Celular",
  "status": "Aguardando conferência do pagamento",
  "baixa_estoque": true,
  "itens": [
    {
      "produto_id": 1,
      "codigo_p": "INC001",
      "nome_p": "Incenso Natural",
      "quantidade": 2,
      "valor_unitario": 12.9,
      "valor_total": 25.8
    }
  ]
}
```

A API deve:

1. Validar se o produto existe.
2. Validar se há estoque suficiente.
3. Registrar a venda.
4. Baixar o estoque.
5. Retornar sucesso.

Resposta esperada:

```json
{
  "ok": true,
  "venda_id": 123,
  "estoque_baixado": true
}
```

### 4. Reservar ou baixar estoque

```http
POST /api/estoque/reservar
```

Payload enviado pelo site:

```json
{
  "origem": "site",
  "venda_id": "MISTICA123456789",
  "itens": [
    {
      "produto_id": 1,
      "codigo_p": "INC001",
      "nome_p": "Incenso Natural",
      "quantidade": 2
    }
  ]
}
```

Resposta esperada:

```json
{
  "ok": true,
  "reservado": true
}
```

## Observações importantes

- O site estático sozinho não consegue alterar o estoque do computador da loja sem uma API online.
- A API deve ser a fonte principal dos dados.
- O programa da loja e o site devem usar o mesmo banco ou a mesma API.
- Se a API estiver offline, o site salva a venda localmente e mostra aviso de API offline.
- Para segurança real, a API deve ter login, token, CORS configurado e HTTPS.

## Arquivo do site que envia a venda

A sincronização do site fica no arquivo:

```text
mobile-sync.js
```

Ele já está configurado para:

- buscar produtos da API;
- buscar vendas;
- buscar clientes;
- enviar venda do site;
- tentar reservar/baixar estoque;
- sincronizar a cada 5 segundos.
