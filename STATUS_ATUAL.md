# Status atual do repositório Mística Presentes

Atualizado em: 2026-07-09

## Segurança

- `.env` foi removido da branch `mistica-v2-rebuild`.
- `.env` também foi removido da branch `main`.
- `.env.example` permanece versionado apenas como modelo, sem chaves reais.
- `.gitignore` já bloqueia `.env`, bancos locais, chaves, backups, logs, builds, executáveis e arquivos `.spec`.
- Busca atual por nomes de variáveis sensíveis conhecidas não encontrou valores expostos no conteúdo indexado do repositório.

## Atenção crítica

Remover o arquivo do estado atual do Git **não limpa o histórico antigo**. Se em algum commit anterior existiram chaves reais, elas devem ser tratadas como comprometidas.

Ações manuais ainda necessárias:

1. Revogar chaves antigas da Gemini, Groq, Render, banco, APIs de pagamento e qualquer outro serviço conectado.
2. Gerar novas chaves.
3. Configurar as novas chaves somente no Render, ambiente local ou GitHub Secrets.
4. Limpar o histórico antigo com `git filter-repo` ou BFG Repo-Cleaner.
5. Fazer force-push do histórico limpo apenas depois de confirmar backup local seguro.

## Limpeza já aplicada

- Removido `.env` rastreado.
- Removido `Mistica Presentes.spec` rastreado.
- Removido `MisticaPresentes_CORRETO.spec` rastreado.
- Confirmado que `.env`, `Mistica Presentes.spec` e `MisticaPresentes_CORRETO.spec` não existem mais na branch `mistica-v2-rebuild`.

## Limpeza ainda recomendada

- Verificar se há outros arquivos `.spec` rastreados.
- Verificar se há `__pycache__/`, `backups/`, bancos `.db` ou logs ainda rastreados.
- Consolidar arquivos `patch` e `fix` dentro dos arquivos principais.
- Mover relatórios antigos para `docs/auditorias/`.
- Manter na raiz apenas este `STATUS_ATUAL.md`, README, arquivos de configuração e arquivos realmente necessários.

## Regra de manutenção

Antes de novas features grandes, priorizar:

1. Segurança de segredos.
2. Limpeza de arquivos indevidos.
3. Consolidação dos patches.
4. Testes básicos de site, API e Admin.
5. Só depois novas integrações, como pagamento por cartão e antifraude.
