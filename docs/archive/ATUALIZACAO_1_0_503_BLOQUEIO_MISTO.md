# Atualização Online 1.0.503

## Bloqueio de venda mista sem fechamento do valor

**Status:** Preparada

## Objetivo
Garantir que uma venda com pagamento misto só seja finalizada quando a soma das formas de pagamento fechar exatamente o valor base da venda.

---

## Nova regra

Se a forma de pagamento for:

```text
Misto
```

O sistema deve bloquear a venda quando:

```text
- não houver nenhum valor informado
- a soma das formas for menor que o total da venda
- a soma das formas for maior que o total da venda
```

---

## Onde bloqueia agora

A proteção foi reforçada em dois pontos:

```text
1. Na tela, antes de abrir a conferência da venda.
2. No serviço de venda, antes de gravar no banco.
```

---

## Mensagens esperadas

Quando faltar valor:

```text
A venda não será finalizada. Ainda falta dividir R$ ...
```

Quando passar do total:

```text
A venda não será finalizada. O pagamento está acima do total em R$ ...
```

---

## Arquivos alterados

```text
app_pagamento_misto_patch.py
services/venda_service.py
app_version.py
```

---

## Versão

```text
1.0.503
```

---

## Teste recomendado

### Venda total R$ 100,00

Teste 1 — deve bloquear:

```text
Dinheiro R$ 50,00
Pix R$ 20,00
Total informado: R$ 70,00
Resultado: bloquear, falta R$ 30,00
```

Teste 2 — deve bloquear:

```text
Dinheiro R$ 80,00
Pix R$ 40,00
Total informado: R$ 120,00
Resultado: bloquear, passou R$ 20,00
```

Teste 3 — deve liberar:

```text
Dinheiro R$ 50,00
Pix R$ 50,00
Total informado: R$ 100,00
Resultado: venda liberada
```

---

## Como publicar

No GitHub Actions, rodar:

```text
Publish Online Update
```

Versão:

```text
1.0.503
```
