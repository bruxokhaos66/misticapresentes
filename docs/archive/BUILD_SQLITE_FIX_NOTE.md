# Correção SQLite no instalador Windows 7 32 bits

O erro abaixo indica que o PyInstaller não empacotou o módulo SQLite do Python:

```text
ModuleNotFoundError: No module named 'sqlite3'
```

A correção adiciona ao build:

- `--hidden-import=sqlite3`
- `--hidden-import=_sqlite3`
- `--collect-submodules=sqlite3`
- inclusão explícita de `_sqlite3.pyd`
- inclusão explícita de `sqlite3.dll`
- validação final confirmando que ambos estão em `dist/MisticaPresentes/`

Depois de aplicar esta correção, gere novamente o artifact pelo workflow:

```text
Actions → Build Windows 7 32-bit Installer → Run workflow
```
