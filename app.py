"""Entrada alternativa do sistema Mistica Presentes.

Funciona em modo Python normal e dentro do EXE gerado pelo PyInstaller.
Antes de executar, aplica migracoes pontuais no arquivo principal para deixar o
mistica_presentes.py limpo fisicamente.
"""
from pathlib import Path
import sys

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MAIN_FILE = BASE_DIR / "mistica_presentes.py"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.manutencao_codigo_service import limpar_mistica_presentes


if __name__ == "__main__":
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {MAIN_FILE}")

    limpar_mistica_presentes(MAIN_FILE)

    fonte = MAIN_FILE.read_text(encoding="utf-8-sig")
    globais = {
        "__name__": "__main__",
        "__file__": str(MAIN_FILE),
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(fonte, str(MAIN_FILE), "exec"), globais)
