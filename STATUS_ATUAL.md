# Status atual do repositorio Mistica Presentes

Atualizado em: 2026-07-09

## Seguranca

- `.env` foi removido da branch `mistica-v2-rebuild`.
- `.env` tambem foi removido da branch `main`.
- `.env.example` permanece versionado apenas como modelo, sem valores reais.
- `.gitignore` bloqueia `.env`, bancos locais, chaves, backups, logs, builds, executaveis e arquivos `.spec`.
- Busca atual por nomes de variaveis sensiveis conhecidas nao encontrou valores expostos no conteudo indexado do repositorio.

## Atencao critica

Remover o arquivo do estado atual do Git nao limpa o historico antigo. Se em algum commit anterior existiram valores reais, eles devem ser substituidos nos servicos correspondentes.

Acoes manuais ainda necessarias:

1. Substituir valores antigos dos servicos externos.
2. Configurar os novos valores somente no Render, ambiente local ou GitHub Secrets.
3. Limpar o historico antigo com ferramenta propria de reescrita de historico.
4. Publicar o historico limpo apenas depois de confirmar backup local seguro.

## Limpeza ja aplicada

- Removido `.env` rastreado.
- Removido `Mistica Presentes.spec` rastreado.
- Removido `MisticaPresentes_CORRETO.spec` rastreado.
- Confirmado que `.env`, `Mistica Presentes.spec` e `MisticaPresentes_CORRETO.spec` nao existem mais na branch `mistica-v2-rebuild`.
- Criadas pastas de documentacao:
  - `docs/auditorias/`
  - `docs/admin/`
  - `docs/site/`
  - `docs/isis/`
- Movidos relatorios e auditorias da raiz para `docs/auditorias/`.
- Movidos documentos de Admin, backend, pedidos, Pix, produtos, estoque e uploads para `docs/admin/`.
- Movidos documentos do site publico, catalogo, SEO e paginas de produto para `docs/site/`.
- Movidos documentos da Isis, kits, pedidos e integracao com API para `docs/isis/`.
- Criados indices em cada pasta de documentacao.
- `INSTRUCOES_SITE.md` foi revisado ao mover, mantendo orientacao geral sem dados sensiveis antigos.

## Limpeza ainda recomendada

- Verificar se ha outros arquivos `.spec` rastreados.
- Verificar se ha `__pycache__/`, `backups/`, bancos `.db` ou logs ainda rastreados.
- Consolidar arquivos `patch` e `fix` dentro dos arquivos principais.
- Conferir localmente se ainda ha `.md` ou `.txt` soltos na raiz que devam ir para `docs/`.
- Manter na raiz apenas este `STATUS_ATUAL.md`, README, arquivos de configuracao e arquivos realmente necessarios.

## Regra de manutencao

Antes de novas features grandes, priorizar:

1. Seguranca de segredos.
2. Limpeza de arquivos indevidos.
3. Consolidacao dos patches.
4. Testes basicos de site, API e Admin.
5. So depois novas integracoes, como pagamento por cartao e antifraude.
