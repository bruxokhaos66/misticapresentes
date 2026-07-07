# Google Drive como armazenamento da Mística Presentes

## Objetivo

Salvar músicas e futuros arquivos permanentes fora do Render, evitando perda em redeploy/restart.

## Variáveis no Render

Adicione em `misticapresentes-api > Environment`:

```text
GOOGLE_SERVICE_ACCOUNT_JSON={...json completo da conta de serviço...}
GOOGLE_DRIVE_FOLDER_MUSICAS=id_da_pasta_musicas
```

Opcional para o futuro:

```text
GOOGLE_DRIVE_FOLDER_PRODUTOS=id_da_pasta_produtos
GOOGLE_DRIVE_FOLDER_BACKUPS=id_da_pasta_backups
```

## Como criar

1. Acesse Google Cloud Console.
2. Crie ou selecione um projeto.
3. Ative a Google Drive API.
4. Crie uma Service Account.
5. Gere uma chave JSON.
6. Copie o JSON inteiro para `GOOGLE_SERVICE_ACCOUNT_JSON` no Render.
7. No Google Drive, crie a pasta `Mística Presentes/Músicas`.
8. Compartilhe essa pasta com o email da service account.
9. Copie o ID da pasta da URL do Drive e coloque em `GOOGLE_DRIVE_FOLDER_MUSICAS`.

## Observação

A API mantém fallback local caso o Drive não esteja configurado, mas o armazenamento local do Render Free pode ser perdido. O Drive é o caminho permanente.
