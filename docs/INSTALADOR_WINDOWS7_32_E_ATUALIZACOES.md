# Instalador Windows 7 32 bits e atualizações online

Este guia é para gerar o instalador do programa desktop da Mística Presentes e permitir atualizações online sem precisar ir até a loja.

## 1. Gerar instalador pelo GitHub Actions

1. Abra o repositório no GitHub.
2. Entre em **Actions**.
3. Selecione **Build Windows 7 32-bit Installer**.
4. Clique em **Run workflow**.
5. Aguarde terminar.
6. Baixe o artifact **MisticaPresentes-Win7-32bit-Setup**.
7. Dentro dele estará o instalador `MisticaPresentes-Win7-32bit-Setup.exe`.

O workflow usa Python 3.8 x86 e PyInstaller com dependências congeladas em `requirements-win7-32.txt`.

## 2. Instalar na loja

No computador da loja:

1. Baixe o instalador gerado.
2. Execute `MisticaPresentes-Win7-32bit-Setup.exe`.
3. Crie atalho na área de trabalho se desejar.
4. Abra o programa uma vez para validar banco, telas e sincronização.

## 3. Atualizações online

O programa consulta automaticamente este manifesto:

```text
https://misticaesotericos.com.br/updates/manifest.json
```

Se o manifesto tiver uma versão maior que `app_version.py`, o programa baixa o pacote `.zip`, confere o SHA256 e ativa a atualização.

Se a atualização quebrar ao abrir, o `app.py` faz rollback para a versão base instalada.

## 4. Gerar pacote de atualização

Quando alterar o programa desktop e quiser publicar uma atualização online:

```powershell
python scripts/build_update_package.py --version 1.0.2 --notes "Correções de estoque, vendas e sincronização."
```

Isso cria:

```text
updates/mistica-update-1.0.2.zip
updates/manifest.json
```

Depois faça commit e push desses arquivos. Como a pasta `updates/` fica publicada no site, os computadores da loja recebem a nova versão ao abrir o programa.

## 5. Arquivos incluídos no pacote online

O pacote inclui:

- `mistica_presentes.py`
- `config.py`
- `app_version.py`
- patches de runtime do app
- pasta `database/`
- pasta `services/`
- pasta `assets/`

O pacote online não substitui o banco da loja. Ele atualiza o código do programa.

## 6. Observações importantes

- Windows 7 32 bits é ambiente antigo. Use o instalador 32 bits apenas para esse computador.
- O computador precisa ter internet para baixar atualizações online.
- O atualizador exige HTTPS e SHA256 para evitar pacote corrompido.
- Se quiser desativar uma atualização ruim, apague o manifesto publicado ou publique uma versão nova corrigida.
