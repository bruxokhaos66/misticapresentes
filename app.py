"""Entrada alternativa do sistema Mistica Presentes.

Usa caminho relativo ao proprio repositorio para evitar erro quando o projeto
for movido de pasta ou usado para gerar EXE.
"""
from pathlib import Path
import runpy

BASE_DIR = Path(__file__).resolve().parent
MAIN_FILE = BASE_DIR / "mistica_presentes.py"

if __name__ == "__main__":
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {MAIN_FILE}")
    runpy.run_path(str(MAIN_FILE), run_name="__main__")
