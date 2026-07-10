# Relatório — Etapa 12

## Preparação da entrega para teste real da loja

**Status:** Concluída

## Contexto

Os workflows principais foram informados como verdes:

```text
Build Instalador Windows
Build Mistica Launcher
Build Online Update Package
Publish Online Update
```

Com isso, a base está pronta para teste controlado na máquina real da loja.

---

## 1. Guia de entrega criado

Arquivo criado:

```text
docs/GUIA_ENTREGA_TESTE_REAL_LOJA.md
```

O guia explica:

```text
- quais artifacts baixar
- como instalar
- como usar o Launcher
- como testar atualização online
- como testar venda simples
- como testar pagamento misto
- como testar caixa
- como testar backup
- como testar sincronização
- cuidados antes de venda real
```

---

## 2. Artifacts principais

### Instalador

```text
Instalador_Mistica_Presentes
```

Uso:

```text
Instalar ou reinstalar o sistema completo.
```

### Launcher

```text
MisticaLauncher-Windows
```

Uso:

```text
Abrir o sistema no dia a dia com atualização online antes do login.
```

### Atualização online

```text
MisticaPresentes-Updates
```

Uso:

```text
Validar ou publicar atualização online.
```

---

## 3. Ordem de teste recomendada

```text
1. Baixar Instalador_Mistica_Presentes.zip
2. Instalar na máquina real
3. Baixar MisticaLauncher-Windows.zip
4. Abrir pelo MisticaLauncher.exe
5. Fazer login
6. Abrir caixa
7. Testar venda simples
8. Testar venda mista
9. Testar cancelamento
10. Testar backup
11. Testar sincronização
12. Fechar caixa
```

---

## 4. Pontos obrigatórios antes de venda real

```text
- conferir estoque inicial
- fazer backup manual
- testar caixa
- testar cupom
- testar pagamento misto
- testar fechamento
- testar backup
- testar sincronização
```

---

## 5. Resultado

O projeto está pronto para sair da fase de construção e entrar em fase de teste controlado na loja.

---

## Próxima etapa sugerida

Etapa 13 — Correção pós-teste real.

Após testar na máquina da loja, qualquer erro deve ser corrigido com base em:

```text
- print da tela
- log do erro
- ação feita no momento
- se havia internet
- se era venda, caixa, backup, sincronização ou atualização
```
