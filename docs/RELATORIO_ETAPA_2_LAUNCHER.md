# Relatório — Etapa 2

## Launcher inteligente e atualização online

**Status:** Concluída

## Objetivo
Criar um launcher separado que abre antes do sistema, detecta o Windows, verifica atualização online, mostra barra de progresso e abre a versão correta.

## O que foi feito

- Criado `MisticaLauncher.py`.
- Criado workflow `Build Mistica Launcher`.
- Launcher exibe janela antes do login.
- Launcher mostra barra de progresso.
- Launcher detecta Windows 7, 8, 8.1, 10 e 11.
- Launcher detecta 32 bits e 64 bits.
- Launcher mostra na tela o Windows detectado e o canal escolhido.
- `auto_updater.py` agora escolhe manifest por canal.

## Canais de atualização

- Windows 10/11 64 bits: `updates/manifest.json`.
- Windows 10 32 bits: `updates/manifest-win10-x86.json`.
- Windows 7/8/8.1 64 bits: `updates/manifest-win7-x64.json`.
- Windows 7/8/8.1 32 bits: `updates/manifest-win7-x86.json`.

## Segurança e estabilidade

- Se não houver internet, o sistema abre a versão local.
- Se a atualização falhar, o sistema faz rollback e abre a versão anterior.
- O pacote baixado é validado por SHA-256.
- O pacote é extraído com proteção contra caminhos inseguros.

## Compatibilidade Windows 7

- `auto_updater.py` foi ajustado para compatibilidade com Python 3.8.
- `MisticaLauncher.py` foi ajustado para compatibilidade com Python 3.8.
- Isso é importante para builds Legacy do Windows 7.

## Documentação criada

- `docs/ATUALIZACAO_POR_WINDOWS.md`

## Resultado
O projeto já possui base de launcher inteligente e compatível com canais por Windows.

## Próxima validação
Rodar os workflows:

- `Build Mistica Launcher`
- `Build Windows 7 Legacy EXE`
- `Build Win7 x86 EXE`

## Próxima etapa
Etapa 3 — Caixa e pagamento misto profissional.
