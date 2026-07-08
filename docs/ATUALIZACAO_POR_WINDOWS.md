# Atualização por versão do Windows

O `MisticaLauncher.exe` detecta automaticamente o Windows e escolhe o canal correto de atualização.

## Canais

| Sistema detectado | Arquivo manifest usado | Uso |
|---|---|---|
| Windows 10/11 64 bits | `updates/manifest.json` | Canal principal |
| Windows 10 32 bits | `updates/manifest-win10-x86.json` | Canal 32 bits moderno |
| Windows 7/8/8.1 64 bits | `updates/manifest-win7-x64.json` | Canal legacy 64 bits |
| Windows 7/8/8.1 32 bits | `updates/manifest-win7-x86.json` | Canal legacy 32 bits |

## Comportamento

1. O launcher abre antes do login.
2. Detecta Windows e arquitetura.
3. Mostra na tela o canal escolhido.
4. Busca o manifest correto.
5. Se existir atualização compatível, baixa e instala.
6. Se não houver internet ou pacote compatível, abre a versão local.

## Observação

Para o canal principal continuar funcionando, publique:

```text
https://misticaesotericos.com.br/updates/manifest.json
https://misticaesotericos.com.br/updates/mistica-update-<versao>.zip
```

Para Windows 7, publique também:

```text
https://misticaesotericos.com.br/updates/manifest-win7-x64.json
https://misticaesotericos.com.br/updates/manifest-win7-x86.json
```

Caso um manifest específico não exista, o launcher abre a versão local normalmente.
