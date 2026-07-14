# Auditoria de segredos (detect-secrets) — Fase 1, PR 3

## Como rodar a auditoria localmente

```bash
pip install detect-secrets==1.5.0
detect-secrets scan --baseline .secrets.baseline
git diff -- .secrets.baseline   # se não houver diff (fora de "generated_at"), está tudo revisado
```

Se aparecer diferença além do campo `generated_at`, há achados novos para revisar.

## Como revisar a baseline

```bash
detect-secrets audit .secrets.baseline
```

O modo interativo mostra cada achado (mascarado) e pede uma decisão: `y` (é segredo real),
`n` (não é), `s` (pular). Nunca cole o valor real revelado em commits, PRs ou issues —
o relatório de auditoria deve citar apenas arquivo, linha e tipo do achado.

## Como tratar um alerta

1. Identifique o tipo (`type` no JSON) e o arquivo/linha.
2. Abra o arquivo e veja o valor em contexto (localmente, nunca em texto compartilhado).
3. Classifique:
   - **segredo real** → siga a seção abaixo;
   - **credencial de teste fictícia** (ex.: `"test-api-key"`, `usuario:senha@example.com`) → `is_secret: false`;
   - **dado público intencional / hash / identificador não sensível** → `is_secret: false`;
   - **inconclusivo** → não regenere a baseline sem decidir; peça uma segunda revisão.
4. Rode `detect-secrets audit .secrets.baseline` para gravar a decisão e comitar a baseline.

## Se um segredo real for encontrado

- Não repita o valor em logs, commits, PR ou relatório.
- Remova o valor do código e substitua por leitura de variável de ambiente
  (`os.environ.get("NOME_DA_VARIAVEL")`), falhando de forma segura (ex.: `HTTPException`)
  quando a variável não estiver definida — é o padrão já usado em `backend/api_security.py`
  para `MISTICA_SITE_API_KEY`/`MISTICA_SYNC_KEY`.
- Atualize `.env.example` só com o **nome** da variável, valor vazio.
- Identifique todos os pontos de uso da credencial no código e no histórico Git
  (`git log -p -- <arquivo> | grep -n "<parte do nome, nunca o valor>"`).
- Informe ao responsável pela conta/serviço que a credencial precisa ser **revogada e
  rotacionada por ele** — este processo não rotaciona credenciais automaticamente.
- Não reescreva o histórico Git (`filter-repo`, `rebase -i`, force-push) sem autorização
  explícita: o valor exposto já deve ser considerado comprometido e revogado
  independentemente da limpeza do histórico.

## Como atualizar a baseline corretamente

- Rode `detect-secrets scan --baseline .secrets.baseline` para mesclar achados novos.
- Rode `detect-secrets audit .secrets.baseline` para classificar cada achado novo.
- Revise o diff manualmente antes de commitar — cada entrada sem `"is_secret"` explícito
  é um achado pendente de decisão.
- Evite exclusões globais (`should_exclude_file`); prefira exclusão pontual e documentada.
- Nunca adicione um segredo real à baseline como "solução" — a baseline documenta decisões
  sobre falsos positivos, não esconde segredos reais.

## Arquivos que nunca devem ser versionados

Reforçados em `.gitignore`:

```
.env, .env.* (exceto .env.example)
*.pem, *.key, *.p12, *.pfx, *.jks, *.keystore
credentials.json, service-account*.json
*.db, *.sqlite, *.sqlite3
*.bak, backups/, *.log
```

## Workflow dedicado

`.github/workflows/security-secrets.yml` roda em pull requests, push para `main` e
manualmente (`workflow_dispatch`). Ele instala uma versão fixada do `detect-secrets`,
escaneia o repositório contra `.secrets.baseline` e falha o build se surgir uma
diferença real (ignorando apenas o timestamp `generated_at`). Não imprime valores
sensíveis e não depende de nenhum secret do GitHub para funcionar.
