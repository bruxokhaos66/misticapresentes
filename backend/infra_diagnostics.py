"""Verificações seguras de infraestrutura (banco e disco).

Usadas pelos endpoints públicos /api/health e /api/version e pelo diagnóstico
autenticado em system_status_routes.py. Nenhuma função aqui deve devolver
caminhos, variáveis de ambiente ou mensagens de erro internas: apenas
booleans e números, seguros para expor sem autenticação.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from config import DB_PATH


def banco_acessivel() -> bool:
    """Confirma que o banco abre e responde a uma consulta simples."""
    try:
        from backend.database import conectar

        with conectar() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def disco_acessivel() -> bool:
    """Confirma que a pasta do banco existe e aceita criar/remover um arquivo."""
    try:
        pasta = Path(DB_PATH).parent
        pasta.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=pasta, prefix=".mistica_health_"):
            pass
        return True
    except Exception:
        return False


def espaco_disco_bytes() -> dict[str, int] | None:
    """Espaço livre/total/usado (em bytes) do disco onde o banco vive.

    Só números, sem caminho: quem chama decide se e como expor o resultado
    (hoje, apenas o diagnóstico autenticado em /api/diagnostico/sistema).
    """
    try:
        pasta = Path(DB_PATH).parent
        uso = shutil.disk_usage(pasta)
        return {"livre_bytes": uso.free, "total_bytes": uso.total, "usado_bytes": uso.used}
    except Exception:
        return None
