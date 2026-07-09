# Relatorio - Limpeza de backups e pycache

Data: 2026-07-09

## Objetivo

Remover do Git arquivos que nao devem permanecer versionados, especialmente bytecode Python e backups locais antigos.

## Etapa 1 - Remocao de pycache da raiz

Foram removidos arquivos rastreados dentro de `__pycache__/`.

Arquivos removidos:

- `__pycache__/__init__.cpython-314.pyc`
- `__pycache__/app.cpython-314.pyc`
- `__pycache__/config.cpython-314.pyc`

## Etapa 2 - Remocao de pycache de backups

Foram removidos os arquivos `.pyc` rastreados dentro de `backups/__pycache__/`.

Arquivos removidos:

- `backups/__pycache__/__init__.cpython-314.pyc`
- `backups/__pycache__/actions_isis_produtos_backup.cpython-314.pyc`
- `backups/__pycache__/actions_nome_produto_isis_backup.cpython-314.pyc`
- `backups/__pycache__/intent_detector_isis_produtos_backup.cpython-314.pyc`
- `backups/__pycache__/mistica_presentes_etapa3_backup.cpython-314.pyc`
- `backups/__pycache__/mistica_presentes_etapa4_backup.cpython-314.pyc`
- `backups/__pycache__/mistica_presentes_isis_inteligente_backup.cpython-314.pyc`
- `backups/__pycache__/router_env_backup_20260701_110521.cpython-314.pyc`
- `backups/__pycache__/voice_backup_20260701_105715.cpython-314.pyc`
- `backups/__pycache__/web_search_backup_20260701_110651.cpython-314.pyc`
- `backups/__pycache__/web_search_titulos_backup_20260701_110726.cpython-314.pyc`

## Etapa 3 - Remocao de backups rastreados

A pasta `backups/` estava rastreada apesar de estar prevista para ser ignorada. Foram removidos os backups antigos do Git.

Arquivos removidos:

- `backups/.env.example.backup_20260701_110203`
- `backups/__init__.py`
- `backups/actions_isis_produtos_backup.py`
- `backups/actions_nome_produto_isis_backup.py`
- `backups/gemini_client.py.backup_20260701_110455`
- `backups/groq_client.py.backup_20260701_110455`
- `backups/intent_detector_isis_produtos_backup.py`
- `backups/local_llm.py.backup_20260701_110203`
- `backups/local_llm.py.backup_20260701_110455`
- `backups/mistica_presentes_etapa3_backup.py`
- `backups/mistica_presentes_etapa4_backup.py`
- `backups/mistica_presentes_isis_inteligente_backup.py`
- `backups/router.py.backup_20260701_110455`
- `backups/router_env_backup_20260701_110521.py`
- `backups/voice_backup_20260701_105715.py`
- `backups/web_search_backup_20260701_110651.py`
- `backups/web_search_titulos_backup_20260701_110726.py`

## Resultado

- `__pycache__/` nao deve mais aparecer em `git ls-files`.
- `backups/__pycache__/` nao deve mais aparecer em `git ls-files`.
- `backups/` nao deve mais conter arquivos rastreados nesta branch.
- O `.gitignore` passa a cumprir seu papel daqui para frente, impedindo que novos arquivos ignorados sejam adicionados acidentalmente.

## Observacao importante

Esta limpeza remove os arquivos do estado atual da branch, mas nao reescreve o historico antigo do Git. Caso algum backup antigo tenha contido valores reais, os segredos devem continuar sendo considerados expostos e substituidos nos servicos externos.

## Comandos de validacao local

Depois de puxar a branch, validar com:

```powershell
git pull --rebase origin mistica-v2-rebuild
git ls-files "__pycache__/*"
git ls-files "backups/*"
git status
```
