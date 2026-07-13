# CSP (Content Security Policy) — Nota para ativação futura

## Status atual

Após a remoção dos handlers inline no frontend público, nenhum `onclick` com
dados dinâmicos permanece nos arquivos públicos (`index.html`, `kit.html`,
`escola.html`, `admin.html`).

## O que impede uma CSP bloqueante hoje

### 1. Admin panels (fora do escopo público)

- `api/painel.html` — handlers `onclick="entrarApp()"`, `onclick="limparLogin()"`
- `painel-operacional.html` — handlers `onclick="entrar()"`, `onclick="sair()"`

Esses arquivos usam nomes de funções hardcoded (não dados do usuário) e só
devem ser servidos atrás de autenticação. Não representam risco XSS direto,
mas bloqueiam uma CSP `script-src` sem `'unsafe-inline'`.

**Solução:** Substituir por `addEventListener` nestes dois arquivos antes de
ativar CSP.

### 2. Backend server-rendered HTML

- `backend/aluno_auth.py` — botão `onclick="window.print()"`
- `backend/order_status_routes.py` — botão `onclick="window.print()"`

Botões de impressão estáticos. Para CSP, mover para `addEventListener`.

### 3. Estilos inline

Vários elementos usam `style="..."` inline (botões admin, status bar do
mobile-sync). Para CSP com `style-src`, seria necessário mover para classes
CSS.

### 4. Eval dinâmico no desktop

- `app.py` usa `compile()` + `eval()` para patches runtime.
  Isso é desktop-only e não afeta a CSP do site estático.

## Caminho para ativação

1. Substituir os 5 `onclick` restantes em `api/painel.html` e
   `painel-operacional.html` por `addEventListener`.
2. Substituir os 2 `onclick` no backend por `addEventListener`.
3. Mover estilos inline para classes CSS.
4. Ativar `Content-Security-Policy-Report-Only` primeiro.
5. Depois de validado, migrar para modo bloqueante.

## CSP sugerida (modo relatório)

```
Content-Security-Policy-Report-Only:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com;
  img-src 'self' data: https:;
  connect-src 'self' https://api.misticaesotericos.com.br;
  media-src 'self' blob:;
  report-uri /csp-report;
```

Nota: `'unsafe-inline'` em `style-src` é necessário temporariamente por
causa dos estilos inline existentes. Pode ser removido após migração para
classes CSS.
