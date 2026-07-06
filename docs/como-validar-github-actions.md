# Como validar os testes automáticos no GitHub Actions

Data: 2026-07-06

## Objetivo

O projeto agora possui um workflow de testes automáticos em:

```txt
.github/workflows/testes-api.yml
```

Esse workflow roda:

```bash
python -m pytest
```

## Quando os testes rodam

Os testes rodam automaticamente quando:

- uma PR é aberta para a branch `main`;
- uma alteração é enviada para a branch `main`.

## Como conferir no GitHub

1. Abra o repositório no GitHub.
2. Clique na aba **Actions**.
3. Procure o workflow **Testes da API**.
4. Clique na execução mais recente.
5. Verifique se o job **Rodar testes Python** ficou verde.

## Resultado esperado

O resultado esperado é:

```txt
python -m pytest
```

com todos os testes passando.

No último teste local registrado, o resultado foi:

```txt
8 passed
```

## O que fazer se falhar

Se o GitHub Actions ficar vermelho:

1. Abra a execução com erro.
2. Veja em qual etapa parou.
3. Se falhou em dependência, revisar `requirements.txt`.
4. Se falhou em teste, rodar localmente:

```bash
python -m pytest
```

5. Corrigir em uma PR pequena.

## Regra de segurança

Não corrigir falha de teste junto com mudanças grandes de venda, estoque, Pix, caixa ou login.

Cada correção deve ser isolada para facilitar rollback e revisão.
