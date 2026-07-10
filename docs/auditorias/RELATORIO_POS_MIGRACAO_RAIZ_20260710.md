# Relatório final pós-migração para a raiz

Data: 10/07/2026

## Escopo

Auditoria final da integração dos PRs #221 e #220, com foco na migração do frontend público de `mistica-v2/` para a raiz do domínio, preservação das correções de segurança/SEO/performance e verificação do estado do repositório após o merge na `main`.

## Resultado executivo

**Status geral: APROVADO COM RESSALVAS OPERACIONAIS**

A migração foi integrada com sucesso à `main` pelo merge do PR #220. Antes do merge, o commit de origem passou nos workflows:

- Testes da API: sucesso.
- Build Win7 x86 EXE: sucesso.

O site público atual está presente diretamente em `index.html` na raiz e usa caminhos relativos compatíveis com a nova estrutura.

## Evidências verificadas

### 1. Página principal na raiz

O arquivo `index.html` da `main` contém a home da versão V2 e carrega os recursos diretamente da raiz:

- `v2.css`
- `v2-commerce.css`
- `v2-shamanic-player.css`
- `seo-site.js`
- `app.js`
- `v2-commerce.js`
- `v2-admin-access.js`
- `v2-admin-products.js`

Não há redirecionamento da raiz para `mistica-v2/` e não há `noindex` no HTML principal.

### 2. Compatibilidade da URL antiga

`mistica-v2/index.html` foi mantido como página legada com:

- `noindex,follow`;
- canonical para a raiz;
- redirecionamento imediato para `/`;
- preservação de query string e hash pelo JavaScript.

### 3. SEO técnico

Verificado no repositório:

- `robots.txt` permite rastreamento da raiz;
- `robots.txt` aponta para o sitemap oficial;
- `sitemap.xml` lista a home na raiz;
- `sitemap.xml` lista `produto.html`;
- título e descrição estão presentes na home;
- favicon usa caminho relativo da raiz;
- script de SEO está carregado pela home.

### 4. Resíduos da estrutura antiga

A busca no código não retornou referências ativas para `mistica-v2/` fora da página legada/arquivos históricos previstos.

### 5. Testes automatizados anteriores ao merge

O head integrado ao PR #220 concluiu com sucesso:

- workflow `Testes da API`;
- workflow `Build Win7 x86 EXE`.

## Ressalvas e riscos restantes

### A. Redirecionamento antigo não é HTTP 301 real

O redirecionamento em `mistica-v2/index.html` usa `meta refresh` e JavaScript. Em hospedagem estática isso é funcional, mas não equivale tecnicamente a uma resposta HTTP 301/308.

**Impacto:** baixo a moderado para SEO, dependendo de quanto a URL antiga já foi indexada ou compartilhada.

**Recomendação:** quando o provedor permitir, configurar um redirecionamento HTTP permanente de `/mistica-v2/*` para `/*` no CDN, proxy ou servidor.

### B. Publicação ao vivo não foi comprovada por esta auditoria

O repositório foi auditado após o merge, porém o domínio público não pôde ser validado automaticamente neste ambiente no momento da conclusão.

**Recomendação:** confirmar no navegador após o GitHub Pages/deploy finalizar:

1. `/` abre a nova home;
2. `/mistica-v2/` redireciona para `/`;
3. produtos carregam;
4. busca e filtros funcionam;
5. carrinho soma corretamente;
6. Pix gera QR Code e copia e cola;
7. WhatsApp abre com o pedido;
8. player toca e para;
9. imagens e fontes não retornam 404;
10. `produto.html` abre sem erro no console.

### C. Chave Pix continua sendo CPF público

A decisão foi manter temporariamente a chave Pix atual. Isso permanece fora do escopo desta migração.

**Recomendação:** substituir futuramente por chave aleatória ou chave fornecida pelo PSP/banco, após validação do recebedor.

### D. APIs e painéis continuam duplicados

A consolidação de `api/`, `backend/`, `cloud_server/` e dos painéis administrativos foi deliberadamente adiada.

**Impacto:** aumenta custo de manutenção e risco de divergência futura, mas não bloqueia a migração atual.

### E. Validação Windows real

O workflow gerou o build Win7 x86 com sucesso, mas isso não substitui teste manual do executável em uma máquina Windows real.

## Conclusão

A migração de `mistica-v2/` para a raiz foi integrada de forma controlada, com validações automatizadas anteriores ao merge e estrutura final coerente no repositório.

Não foi identificado bloqueio técnico no código da `main` que exija rollback imediato.

A recomendação é manter a publicação, realizar o checklist manual de produção e monitorar:

- erros 404;
- console do navegador;
- Search Console;
- funcionamento de Pix, WhatsApp e player;
- logs da API;
- comportamento da URL antiga.

## Referências internas

- PR #221 — preparação e execução da migração.
- PR #220 — auditoria técnica e integração final na `main`.
- Commit de merge final na `main`: `222172ea2eec7cca85d812871371413ac13c7ec6`.
