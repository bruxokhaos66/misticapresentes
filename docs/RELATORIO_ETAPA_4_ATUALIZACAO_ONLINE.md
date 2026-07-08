# Relatório — Etapa 4

## Atualização online publicada pelo site

**Status:** Concluída

## Objetivo
Preparar o projeto para publicar atualizações online em `https://misticaesotericos.com.br/updates/`, permitindo que o Launcher baixe a versão correta antes do login.

## O que foi feito

- Criado script `scripts/gerar_manifestos_canais.py`.
- O script gera manifests separados por canal de Windows.
- Atualizado workflow `Build Online Update Package`.
- Atualizado workflow `Publish Online Update`.
- O pacote de atualização agora inclui manifests por canal.
- A publicação online copia todos os `.json` e o pacote `.zip` para a pasta `/updates`.

## Arquivos gerados para publicação

```text
updates/manifest.json
updates/manifest-win10-x86.json
updates/manifest-win7-x64.json
updates/manifest-win7-x86.json
updates/mistica-update-<versao>.zip
```

## Canais

```text
manifest.json              -> Windows 10/11 64 bits
manifest-win10-x86.json    -> Windows 10 32 bits
manifest-win7-x64.json     -> Windows 7/8/8.1 64 bits
manifest-win7-x86.json     -> Windows 7/8/8.1 32 bits
```

## Como publicar uma atualização

1. Abrir GitHub Actions.
2. Rodar o workflow `Publish Online Update`.
3. Informar a versão, por exemplo: `1.0.300`.
4. O workflow gera o pacote.
5. O workflow publica os arquivos na pasta `updates/`.
6. O GitHub Pages disponibiliza os arquivos no site.

## Resultado esperado

Depois de publicado, os arquivos devem abrir em:

```text
https://misticaesotericos.com.br/updates/manifest.json
https://misticaesotericos.com.br/updates/manifest-win7-x64.json
https://misticaesotericos.com.br/updates/manifest-win7-x86.json
```

## Próxima etapa
Etapa 5 — Auditoria geral do sistema.
