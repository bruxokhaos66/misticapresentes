# Correção repositories no instalador Windows 7 32 bits

O erro abaixo indica que o PyInstaller não copiou a pasta `repositories` para o pacote final:

```text
ModuleNotFoundError: No module named 'repositories'
```

A correção adiciona ao build:

- `repositories;repositories` em `--add-data`
- `--hidden-import=repositories`
- `--collect-submodules=repositories`
- validação final de `dist/MisticaPresentes/repositories`

Também mantém as correções anteriores de SQLite e valida `services` no pacote final.
