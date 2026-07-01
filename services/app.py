"""Entrada alternativa da arquitetura 2.0.

Por enquanto, mantém compatibilidade chamando o arquivo principal antigo.
A interface será movida para cá nas próximas etapas.
"""
import os
import runpy

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents")
MAIN_FILE = os.path.join(DOCS_PATH, "mistica_presentes.py")

if __name__ == "__main__":
    runpy.run_path(MAIN_FILE, run_name="__main__")
