# Auditoria do site — Mística Presentes

Relatório consolidado da auditoria do site e painel da Mística Presentes.

## Escopo analisado

- `index.html` — site público, carrinho, Isis e área interna.
- `app.js` — catálogo base, carrinho, Pix, clientes, vendas, estoque e Admin local.
- `site-config.js` — configurações comerciais do domínio, WhatsApp e API.
- `commercial-layer.js` — camada comercial e carregamento de módulos extras.
- `admin-access.js` — exibição da área Admin.
- `admin-activity.js` — atividade recente do Admin e contato via WhatsApp.
- `api/painel.html` — painel mobile/web em tempo real.
- `product-admin.js` — cadastro de produtos pelo Admin.
- `styles.css` e `commercial.css` — identidade visual, responsividade e layout mobile.

## Correções já aplicadas na fase 2

### Segurança e estabilidade do Admin

- A atividade recente do Admin agora escapa dados vindos da API antes de inserir no HTML.
- O botão de WhatsApp da atividade recente normaliza o número para o formato aceito pelo `wa.me`.
- Links externos do WhatsApp usam `rel="noopener noreferrer"`.
- O intervalo de montagem da atividade admin para depois que o painel é montado.

### Painel mobile/web

- O painel não usa mais token padrão automaticamente no navegador.
- O painel mostra aviso quando o aparelho está sem token autorizado.
- O WebSocket ganhou controle para evitar conexões duplicadas ao entrar/sair.
- O painel ganhou fallback para campos ausentes da API.
- Tabelas do painel ganharam rolagem horizontal em celular.
- Botões e campos ganharam foco visual e área mínima de toque.

### Cadastro de produtos

- Bloqueio de produto sem nome.
- Bloqueio de produto sem categoria.
- Bloqueio de produto sem descrição.
- Bloqueio de preço inválido ou zerado.
- Bloqueio de estoque negativo/inválido.
- Validação melhor de URL externa/afiliada.
- Mensagem clara de erro ou sucesso no formulário.

## Pendências que exigem fase futura

### Crítico / precisa de backend

1. **Senha fixa do Admin no front-end**
   - A senha não deve ficar no JavaScript público.
   - Solução correta: autenticação real via backend, sessão/token e controle de permissões.

2. **Dados administrativos em `localStorage`**
   - Clientes, vendas, estoque, fornecedores e backups locais ainda dependem do navegador.
   - Solução correta: banco de dados no backend com autenticação.

3. **Separar site público e Admin**
   - Hoje a área Admin existe no mesmo `index.html`, apenas escondida/mostrada.
   - Solução correta: rota ou página protegida para Admin.

### Importante / organização

4. **Centralizar configurações comerciais**
   - WhatsApp, domínio, Pix e textos aparecem em mais de um arquivo.
   - Solução recomendada: usar `site-config.js` como fonte única.

5. **Revisar `.env` versionado**
   - Mesmo sem chaves reais, o ideal é manter somente `.env.example` no repositório.
   - O `.env` real deve ficar apenas local/servidor.

6. **Testes automatizados e ambiente local**
   - Validar suíte local com Python/venv funcionando.
   - Corrigir comandos de teste que dependem de ambiente fora do projeto.

## Checklist manual recomendado

1. Abrir o Admin e conferir se a atividade recente carrega.
2. Clicar no botão de WhatsApp em uma atividade recente.
3. Abrir o painel mobile sem token e confirmar que aparece aviso de token ausente.
4. Abrir o painel com `?app_token=TOKEN_FORTE` e confirmar acesso normal.
5. Entrar e sair do painel algumas vezes e verificar se não há notificações ou conexões duplicadas.
6. Cadastrar produto válido e confirmar que aparece no catálogo.
7. Tentar cadastrar produto sem preço, sem nome ou com estoque negativo e confirmar que o sistema bloqueia.
8. Testar painel em celular e conferir rolagem horizontal nas tabelas.
9. Conferir se todos os botões de WhatsApp apontam para o número correto da loja.
10. Conferir se Pix, domínio e Instagram estão corretos antes de divulgar.

## Próxima fase sugerida

A próxima fase ideal é **Admin seguro + banco de dados**:

- Criar login real no backend.
- Remover senha fixa do front-end.
- Migrar clientes, vendas, estoque e fornecedores do `localStorage` para banco.
- Separar área pública e área Admin.
- Criar `.env.example` e remover `.env` versionado se confirmado que não quebra o fluxo local.
