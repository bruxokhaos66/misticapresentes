# Auditoria do Atualizador — Julho/2026

## Status

Auditoria realizada após relato de que o sistema não atualizava mesmo com o manifesto publicado.

---

## 1. Verificação do GitHub

Foi conferido que:

```text
updates/manifest.json estava publicado
mistica-update-1.0.506.zip existia na pasta updates
package_url apontava para a fonte direta do repositório
```

Conclusão:

```text
O problema não estava na publicação do pacote.
```

---

## 2. Problema encontrado

Arquivo auditado:

```text
MisticaLauncher.py
```

Foi identificado que o Launcher ainda aplicava uma lista antiga de patches:

```text
app_runtime_patch
app_pagamento_misto_patch
app_sync_status_patch
app_painel_guard_patch
app_scroll_patch
```

Mas o sistema atual já dependia também de:

```text
app_backup_inicializacao_patch
app_sync_pagamento_misto_payload_patch
app_caixa_fechamento_avancado_patch
app_backup_painel_patch
app_manutencao_segura_patch
```

---

## 3. Risco causado

Mesmo quando a atualização baixava, o Launcher poderia abrir o sistema atualizado sem aplicar todos os patches necessários.

Isso poderia causar:

```text
- sistema abrir incompleto
- aba Manutenção não aparecer
- backup não inicializar
- fechamento avançado não aplicar
- erro ao abrir a versão atualizada
- rollback para versão anterior
```

---

## 4. Correção aplicada

Arquivo alterado:

```text
MisticaLauncher.py
```

Agora o Launcher aplica todos os patches atuais:

```text
app_backup_inicializacao_patch
app_runtime_patch
app_pagamento_misto_patch
app_sync_pagamento_misto_payload_patch
app_caixa_fechamento_avancado_patch
app_backup_painel_patch
app_manutencao_segura_patch
app_sync_status_patch
app_painel_guard_patch
app_scroll_patch
```

---

## 5. Versão preparada

```text
1.0.508
```

---

## 6. Observação importante

Se a máquina da loja ainda usa um Launcher antigo, pode ser necessário baixar o novo `MisticaLauncher-Windows` uma vez.

Depois disso, as próximas atualizações devem funcionar de forma mais confiável.

---

## Próximo teste recomendado

1. Rodar `Build Mistica Launcher`.
2. Baixar o novo `MisticaLauncher-Windows`.
3. Substituir o Launcher antigo da máquina.
4. Rodar `Publish Online Update` com versão `1.0.508`.
5. Abrir o novo Launcher e conferir se sobe para `1.0.508`.
