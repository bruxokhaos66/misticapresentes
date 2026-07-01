"""Gera uma versao profissional em pasta (--onedir) do Mística Presentes.

Vantagens do onedir:
- abre mais rapido que onefile;
- gera menos erro de modulo faltando;
- facilita suporte tecnico;
- ideal para uso diario na loja.

Execute na raiz do projeto:
    python scripts/gerar_exe_profissional_onedir.py
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / "Desktop"
if not DESKTOP.exists():
    DESKTOP = Path.home() / "Área de Trabalho"

APP_FILE = ROOT / "app.py"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
APP_NAME = "Mistica Presentes"
APP_FOLDER = DIST_DIR / APP_NAME
DESKTOP_FOLDER = DESKTOP / APP_NAME
ICON_PATH = ROOT / "assets" / "mistica_xamanico_moderno.ico"

PASTAS_DADOS = ["database", "services", "repositories", "reports", "isis", "Isis"]
ARQUIVOS_DADOS = [("mistica_presentes.py", "."), ("config.py", ".")]
COLLECT_SUBMODULES = ["database", "services", "repositories", "reports", "isis"]
HIDDEN_IMPORTS = [
    "customtkinter", "tkinter", "tkinter.ttk", "sqlite3", "speech_recognition", "pyttsx3", "ddgs",
    "PIL", "PIL.Image", "PIL.ImageTk", "database", "services", "repositories", "reports", "isis",
]


def add_data(origem: Path, destino: str) -> str:
    return f"{origem}{os.pathsep}{destino}"


def rodar(cmd):
    print("Executando:", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def montar_cmd():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--name", APP_NAME]
    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])
    for arquivo, destino in ARQUIVOS_DADOS:
        origem = ROOT / arquivo
        if origem.exists():
            cmd.extend(["--add-data", add_data(origem, destino)])
    for pasta in PASTAS_DADOS:
        origem = ROOT / pasta
        if origem.exists():
            cmd.extend(["--add-data", add_data(origem, pasta)])
    cmd.extend(["--collect-all", "customtkinter"])
    for modulo in COLLECT_SUBMODULES:
        cmd.extend(["--collect-submodules", modulo])
    for item in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", item])
    cmd.append("app.py")
    return cmd


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError("app.py nao encontrado.")
    rodar([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
    if APP_FOLDER.exists():
        shutil.rmtree(APP_FOLDER, ignore_errors=True)
    rodar(montar_cmd())
    if not APP_FOLDER.exists():
        raise FileNotFoundError(f"Pasta gerada nao encontrada: {APP_FOLDER}")
    if DESKTOP_FOLDER.exists():
        shutil.rmtree(DESKTOP_FOLDER, ignore_errors=True)
    shutil.copytree(APP_FOLDER, DESKTOP_FOLDER)
    print("\nPronto!")
    print("Versao profissional enviada para:", DESKTOP_FOLDER)
    print("Abra o arquivo:", DESKTOP_FOLDER / f"{APP_NAME}.exe")


if __name__ == "__main__":
    main()
