"""Entrada alternativa do sistema Mistica Presentes.

Funciona tanto em modo Python normal quanto dentro do EXE gerado pelo
PyInstaller. O patch temporario da Isis fica em services.launcher_patch para
evitar erro de string quebrada no executavel.
"""
from pathlib import Path
import sys

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MAIN_FILE = BASE_DIR / "mistica_presentes.py"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.launcher_patch import carregar_codigo_corrigido


if __name__ == "__main__":
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {MAIN_FILE}")

    fonte = carregar_codigo_corrigido(MAIN_FILE)
    globais = {
        "__name__": "__main__",
        "__file__": str(MAIN_FILE),
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(fonte, str(MAIN_FILE), "exec"), globais)
