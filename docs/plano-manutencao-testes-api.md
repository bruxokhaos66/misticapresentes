# Plano de manutenção dos testes da API

Data: 2026-07-06

## Status atual

Os testes locais foram executados com sucesso após a inclusão dos testes básicos da API.

Comando usado:

```bash
python -m pytest
```

Resultado informado:

```txt
8 passed, 7 warnings in 2.59s
```

Conclusão: os testes passaram. Os avisos exibidos não impediram a execução dos testes e não indicaram quebra imediata do sistema.

## Endpoints validados

Os testes básicos cobrem:

- `/api/health`
- `/api/status`
- `/api/diagnostico/sistema`
- `/api/backup/status`

## Impacto atual

- Não impede o deploy.
- Não impede os testes locais.
- Não altera vendas.
- Não altera estoque.
- Não altera Pix.
- Não altera caixa.
- Não altera login.

## Plano seguro para manutenção futura

### Fase futura 1 — Inicialização da API principal

Revisar a forma como o backend inicializa rotinas automáticas no arquivo:

```txt
backend/main.py
```

Essa revisão deve ser feita em uma PR própria, pequena e testada.

### Fase futura 2 — Inicialização da API paralela

Revisar também o arquivo:

```txt
api/main.py
```

### Fase futura 3 — Ferramentas de teste

Avaliar atualizações futuras das bibliotecas usadas nos testes, mantendo compatibilidade com o projeto.

## Regra de segurança

Não misturar essa manutenção com alterações de venda, estoque, Pix, login ou caixa.

Cada ajuste deve ser feito em PR própria e validado com:

```bash
python -m pytest
```

Critério de sucesso:

```txt
todos os testes passando
sem alteração funcional inesperada
sem quebra do deploy
```
