"""Isola o banco usado pela suíte de testes do banco real da aplicação.

`config.DB_PATH` é uma constante calculada uma única vez, na primeira vez
que qualquer módulo importa `config` (import é cacheado por processo) --
sem isso, ela cai no padrão de `config.carregar_db_path()`
(`Documents/mistica_gestao_v20.db`, o MESMO arquivo usado pela aplicação
real quando rodada localmente). Isso faz duas execuções de pytest no mesmo
processo/máquina compartilharem estado (ex.: `UNIQUE constraint failed` em
`tentativas_pagamento` quando um teste reutiliza um id fixo de uma execução
anterior) e, pior, gravar dados de teste dentro do banco de verdade.

Este conftest.py roda ANTES de qualquer módulo de teste ser importado
(pytest sempre coleta `conftest.py` primeiro) e só define
`MISTICA_DB_PATH` se o ambiente já não tiver configurado um -- nunca
sobrescreve uma configuração explícita (ex.: um pipeline de CI que já
aponta para um caminho próprio). Nunca apaga nem toca no banco real: só
evita que os testes cheguem perto dele.
"""

import atexit
import os
import tempfile

if not os.environ.get("MISTICA_DB_PATH", "").strip() and not os.environ.get("DATABASE_PATH", "").strip():
    _handle, _caminho_db_teste = tempfile.mkstemp(prefix="mistica_pytest_", suffix=".db")
    os.close(_handle)
    os.environ["MISTICA_DB_PATH"] = _caminho_db_teste

    def _limpar_banco_de_teste(caminho: str = _caminho_db_teste) -> None:
        for sufixo in ("", "-wal", "-shm"):
            try:
                os.remove(caminho + sufixo)
            except OSError:
                pass

    atexit.register(_limpar_banco_de_teste)
