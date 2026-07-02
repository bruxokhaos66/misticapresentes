"""Logs simples de acesso da API.

Nao grava tokens nem corpos de requisicao. Serve para diagnostico operacional.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    from config import ERROR_LOG_DIR
except Exception:
    ERROR_LOG_DIR = str(Path.home() / "Documents" / "Mística_Erros")

LOG_PATH = Path(ERROR_LOG_DIR) / "api_acessos.log"


def registrar_acesso_api(metodo: str, caminho: str, status: int | str, cliente: str = "-"):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        linha = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {cliente} | {metodo} | {caminho} | {status}\n"
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(linha)
    except Exception:
        pass
