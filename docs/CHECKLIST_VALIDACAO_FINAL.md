# Checklist de Validação Final — Mística Presentes

Este checklist deve ser usado antes de distribuir o sistema para uso real na loja.

---

## 1. Workflows que devem ser validados

### Build Instalador Windows

Link:

```text
https://github.com/bruxokhaos66/misticapresentes/actions/workflows/build-instalador-windows.yml
```

Resultado esperado:

```text
Artifact: Instalador_Mistica_Presentes
Arquivo: Instalador_Mistica_Presentes.zip
```

---

### Build Mistica Launcher

Link:

```text
https://github.com/bruxokhaos66/misticapresentes/actions/workflows/build-launcher.yml
```

Resultado esperado:

```text
Artifact: MisticaLauncher-Windows
Arquivo: MisticaLauncher-Windows.zip
```

---

### Build Online Update Package

Link:

```text
https://github.com/bruxokhaos66/misticapresentes/actions/workflows/build-online-update-package.yml
```

Resultado esperado:

```text
Artifact: MisticaPresentes-Updates
Arquivo: MisticaPresentes-Updates.zip
```

---

### Publish Online Update

Link:

```text
https://github.com/bruxokhaos66/misticapresentes/actions/workflows/publish-online-update.yml
```

Resultado esperado:

```text
updates/manifest.json
updates/manifest-win10-x86.json
updates/manifest-win7-x64.json
updates/manifest-win7-x86.json
updates/mistica-update-<versao>.zip
```

---

## 2. Ordem recomendada para teste

```text
1. Rodar Build Instalador Windows
2. Baixar Instalador_Mistica_Presentes.zip
3. Instalar/testar em Windows principal
4. Rodar Build Mistica Launcher
5. Baixar MisticaLauncher-Windows.zip
6. Abrir MisticaLauncher.exe
7. Rodar Build Online Update Package
8. Rodar Publish Online Update com uma versão nova
9. Abrir Launcher novamente e verificar atualização
```

---

## 3. Testes dentro do sistema

### Login

```text
- Login com usuário válido
- Bloqueio de admin/admin
- Logout
- Fechar sistema
```

### Vendas

```text
- Venda simples em dinheiro
- Venda em Pix
- Venda em Débito
- Venda em Crédito 1x
- Venda mista com 2 formas
- Venda mista com 3 formas
- Venda mista com 4 formas
- Conferir cupom
- Conferir baixa de estoque
```

### Caixa

```text
- Abrir caixa
- Fazer venda
- Fazer sangria
- Fazer reforço
- Fechar caixa
- Conferir Dinheiro
- Conferir Pix
- Conferir Débito
- Conferir Crédito 1x
- Conferir Crédito 2x
- Conferir Crédito 3x
```

### Cancelamento

```text
- Cancelar venda simples
- Cancelar venda mista
- Conferir devolução de estoque
- Conferir saída no caixa
```

### Backup

```text
- Abrir o sistema e verificar backup automático
- Usar aba Manutenção > Fazer backup agora
- Usar aba Manutenção > Ver último backup
- Usar aba Manutenção > Abrir pasta de backups
```

### Sincronização

```text
- Ver status da sincronização
- Rodar sincronização manual
- Conferir pendências
```

### Atualizador

```text
- Abrir Launcher
- Conferir canal detectado
- Conferir barra de progresso
- Conferir abertura sem internet
- Conferir rollback se atualização falhar
```

---

## 4. Arquivos críticos incluídos nos builds

```text
app.py
auto_updater.py
mistica_presentes.py
app_runtime_patch.py
app_pagamento_misto_patch.py
app_sync_pagamento_misto_payload_patch.py
app_caixa_fechamento_avancado_patch.py
app_backup_inicializacao_patch.py
app_backup_painel_patch.py
app_manutencao_segura_patch.py
app_sync_status_patch.py
app_painel_guard_patch.py
app_scroll_patch.py
services/
database/
repositories/
isis/
backend/
assets/
```

---

## 5. Status esperado para distribuição controlada

O sistema pode ser testado de forma controlada quando os workflows abaixo estiverem verdes:

```text
Build Instalador Windows
Build Mistica Launcher
Build Online Update Package
Publish Online Update
```

Se algum workflow ficar vermelho, abrir o log da etapa que falhou e corrigir antes de distribuir.
