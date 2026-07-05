# Auditoria do site — Mística Presentes

Auditoria realizada sobre a main atual após o PR #40 (`Admin contato`) ter sido mesclado.

## Escopo analisado

- `api/painel.html` — painel mobile/web em tempo real.
- `admin-activity.js` — painel de atividade recente do Admin e botão de WhatsApp.
- `.gitignore` e `.env` — checagem de risco de configuração local.
- `commercial.css` — leitura da responsividade relacionada ao Admin.

## Achados e correções aplicadas

### Crítico / segurança

1. **Token padrão no painel web**
   - Antes, o painel usava `mistica-local` como fallback no navegador.
   - Isso podia gerar chamadas com token fraco/padrão e confundia testes em ambiente limpo.
   - Correção: o painel agora exige token configurado no aparelho ou recebido por `app_token`/`token` na URL autorizada. Sem token, a tela mostra aviso e não inicia API/WebSocket.

2. **HTML vindo da API no painel de atividade admin**
   - Alguns campos de atividade recente entravam no HTML sem escape completo.
   - Correção: status, pedido, cliente, observação, data e mensagens de erro agora passam por escape antes de renderizar.

3. **Número do WhatsApp sem normalização**
   - O número vindo da configuração podia carregar caracteres fora do padrão.
   - Correção: o link `wa.me` agora usa apenas dígitos e mantém fallback seguro.

### Importante / estabilidade

4. **Múltiplas conexões WebSocket no painel**
   - Entrar/sair ou recarregar fluxo podia deixar conexões e timers duplicados.
   - Correção: foi criado controle único de WebSocket, retry e encerramento limpo ao sair.

5. **Renderização frágil quando a API retorna campos ausentes**
   - Se algum bloco viesse vazio/ausente (`caixa`, `vendas_hoje`, `estoque_baixo`, `alertas_isis`, etc.), o painel podia quebrar.
   - Correção: adicionados defaults e validações com `Array.isArray`/objetos vazios.

6. **Intervalo de montagem do painel admin rodando sempre**
   - O `admin-activity.js` tentava montar o painel a cada 1,5s indefinidamente.
   - Correção: o intervalo agora para assim que o painel é montado.

### Melhoria visual / mobile

7. **Tabelas do painel em telas pequenas**
   - Em celular, tabelas podiam ficar apertadas ou perder colunas.
   - Correção: tabelas ganharam wrapper com rolagem horizontal e largura mínima controlada.

8. **Acessibilidade básica de foco e toque**
   - Botões e campos ganharam foco visível e altura mínima de toque.

## Pontos ainda recomendados para próxima fase

- Remover o `.env` versionado e manter apenas um `.env.example`, mesmo que hoje ele esteja sem chaves reais.
- Validar testes automatizados em ambiente local com `python`/venv funcionando no PATH.
- Fazer uma varredura completa de acentuação em todos os arquivos visuais, pois o Codex anterior relatou textos quebrados em alguns pontos.
- Testar manualmente em celular real: login do painel, atividade recente, botão de WhatsApp e atualização em tempo real.

## Checklist de testes sugeridos

1. Abrir o painel sem token e confirmar que aparece aviso de token não configurado.
2. Abrir o painel com `?app_token=TOKEN_FORTE` e confirmar que a URL limpa o token após salvar no `localStorage`.
3. Entrar como Administrador e confirmar que vendas, estoque, contas e cancelamentos aparecem sem erro.
4. Entrar/sair algumas vezes e confirmar que não aparecem várias notificações duplicadas.
5. Abrir o Admin no site e conferir se a atividade recente carrega e se o botão de WhatsApp abre com mensagem correta.
6. Testar o painel em largura de celular e confirmar que as tabelas têm rolagem horizontal quando necessário.
