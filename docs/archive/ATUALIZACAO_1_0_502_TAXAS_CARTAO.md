# Atualização Online 1.0.502

## Taxas fixas para cartão

**Status:** Preparada

## Objetivo
Alterar o cálculo das taxas de cartão para valor fixo, conforme regra comercial da loja.

---

## Nova regra

```text
Dinheiro: R$ 0,00
Pix: R$ 0,00
Débito: R$ 1,50
Crédito 1x: R$ 1,50
Crédito 2x: R$ 2,00
Crédito 3x: R$ 2,50
```

---

## Antes

O débito já usava taxa fixa de R$ 1,50.

O crédito usava porcentagem:

```text
Crédito 1x: 1,5%
Crédito 2x: 2,0%
Crédito 3x: 2,5%
```

---

## Agora

O crédito passou a usar taxa fixa:

```text
Crédito 1x: R$ 1,50
Crédito 2x: R$ 2,00
Crédito 3x: R$ 2,50
```

---

## Arquivo alterado

```text
services/venda_service.py
```

Foi criada a tabela:

```text
TAXAS_FIXAS_CARTAO
```

---

## Impacto

A regra vale para:

```text
- venda simples no débito
- venda simples no crédito
- pagamento misto com débito/crédito
- fluxo de caixa separado por forma
- total final da venda
```

---

## Versão

```text
1.0.502
```

---

## Como publicar

No GitHub Actions, rodar:

```text
Publish Online Update
```

Informar a versão:

```text
1.0.502
```

---

## Teste recomendado

Fazer vendas teste:

```text
Produto R$ 100,00 em Débito → total R$ 101,50
Produto R$ 100,00 Crédito 1x → total R$ 101,50
Produto R$ 100,00 Crédito 2x → total R$ 102,00
Produto R$ 100,00 Crédito 3x → total R$ 102,50
```
