# Relatório por Etapas — Mística Presentes

Este documento registra as etapas de evolução do sistema Mística Presentes.

---

## Etapa 1 — Estabilização dos builds e instaladores

**Status:** Concluída

### Objetivo
Garantir que o projeto volte a gerar arquivos para teste e instalação sem quebrar por falhas de workflow.

### O que foi feito

- Corrigido erro do PyInstaller causado por ícone inexistente.
- O arquivo `assets/mistica_xamanico_moderno.ico` agora é opcional.
- Se o ícone existir, o build usa.
- Se o ícone não existir, o build continua normalmente sem quebrar.
- Adicionado `app_pagamento_misto_patch.py` ao pacote do instalador.
- Melhorada a inclusão de arquivos e pastas no `MisticaPresentes_CORRETO.spec`.
- Separados os workflows para evitar que uma falha de atualização online quebre o build do `.exe`.

### Workflows organizados

- `Build Windows EXE` — gera somente o executável principal.
- `Build Instalador Windows` — gera o instalador completo.
- `Build Mistica Launcher` — gera o launcher com atualização online.
- `Build Online Update Package` — gera pacote de atualização online.
- `Publish Online Update` — publica atualização em `/updates`.
- `Build Windows 7 Legacy EXE` — gera versão legacy para Windows 7.
- `Build Win7 x86 EXE` — gera versão 32 bits para Windows 7.

### Resultado
O workflow `Build Instalador Windows` voltou a finalizar com sucesso após a correção do ícone.

### Próxima etapa
Etapa 2 — Launcher inteligente e atualização online por versão do Windows.

---

## Etapa 2 — Launcher inteligente e atualização online

**Status:** Em andamento

### Objetivo
Criar um launcher separado que abre antes do sistema, detecta o Windows, verifica atualização online, mostra barra de progresso e abre a versão correta.

### Itens planejados

- Detectar Windows 7, 8, 10 e 11.
- Detectar 32 bits e 64 bits.
- Escolher canal correto de atualização.
- Exibir canal detectado na tela.
- Baixar pacote compatível.
- Aplicar rollback em caso de falha.
- Abrir versão local caso não exista internet.

---

## Etapa 3 — Caixa e pagamento misto profissional

**Status:** Planejada

### Objetivo
Evoluir o PDV para aceitar múltiplas formas de pagamento no mesmo cupom.

### Itens planejados

- Pagamento misto com mais de 2 formas.
- Débito + dinheiro.
- Pix + dinheiro.
- Crédito + débito.
- Vale/fiado opcional.
- Troco automático.
- Cupom detalhado.
- Lançamento separado no fluxo de caixa.

---

## Etapa 4 — Atualização online publicada pelo site

**Status:** Planejada

### Objetivo
Permitir que o sistema baixe atualizações diretamente de `misticaesotericos.com.br/updates`.

### Itens planejados

- Publicar `manifest.json`.
- Publicar pacote `.zip` da atualização.
- Gerar pacotes por canal.
- Canal principal Windows 10/11.
- Canal legacy Windows 7 64 bits.
- Canal legacy Windows 7 32 bits.

---

## Etapa 5 — Auditoria geral do sistema

**Status:** Planejada

### Objetivo
Revisar fluxo de vendas, estoque, caixa, recibos, backup, sincronização e telas para reduzir bugs antes de distribuir para uso real.
