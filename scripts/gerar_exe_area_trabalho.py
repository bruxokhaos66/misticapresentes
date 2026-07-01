"""Gera o executavel do sistema Mistica Presentes e copia para a Area de Trabalho.

Execute na raiz do projeto:
    python scripts/gerar_exe_area_trabalho.py
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
DIST_DIR = ROOT / "dist"
EXE_NAME = "Mistica Presentes.exe"
EXE_ORIGEM = DIST_DIR / EXE_NAME

ARQUIVOS_DADOS = [
    ("mistica_presentes.py", "."),
    ("config.py", "."),
]

PASTAS_DADOS = [
    "database",
    "services",
    "repositories",
    "reports",
    "isis",
    "Isis",
]

HIDDEN_IMPORTS = [
    "customtkinter",
    "tkinter",
    "tkinter.ttk",
    "sqlite3",
    "speech_recognition",
    "pyttsx3",
    "ddgs",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
]


def desktop_path() -> Path:
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    area = Path.home() / "Área de Trabalho"
    if area.exists():
        return area
    return desktop


def add_data_arg(origem: Path, destino: str) -> str:
    return f"{origem}{os.pathsep}{destino}"


def rodar(cmd):
    print("Executando:", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def limpar_build_anterior():
    for caminho in [ROOT / "build", ROOT / "dist"]:
        if caminho.exists():
            print("Removendo build anterior:", caminho)
            shutil.rmtree(caminho, ignore_errors=True)
    spec = ROOT / "Mistica Presentes.spec"
    if spec.exists():
        try:
            spec.unlink()
        except Exception:
            pass


def montar_comando_pyinstaller():
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "Mistica Presentes",
    ]

    for arquivo, destino in ARQUIVOS_DADOS:
        origem = ROOT / arquivo
        if origem.exists():
            cmd.extend(["--add-data", add_data_arg(origem, destino)])

    for pasta in PASTAS_DADOS:
        origem = ROOT / pasta
        if origem.exists():
            cmd.extend(["--add-data", add_data_arg(origem, pasta)])

    cmd.extend(["--collect-all", "customtkinter"])

    for item in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", item])

    cmd.append("app.py")
    return cmd


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError(f"Nao encontrei o arquivo principal: {APP_FILE}")

    print("Atualizando dependencias...")
    rodar([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    limpar_build_anterior()

    print("Gerando executavel com PyInstaller e incluindo arquivos internos...")
    rodar(montar_comando_pyinstaller())

    if not EXE_ORIGEM.exists():
        raise FileNotFoundError(f"O executavel nao foi encontrado em: {EXE_ORIGEM}")

    destino = desktop_path() / EXE_NAME
    shutil.copy2(EXE_ORIGEM, destino)

    print("\nPronto!")
    print(f"Executavel criado em: {EXE_ORIGEM}")
    print(f"Copia enviada para a Area de Trabalho: {destino}")
    print("\nDica: no primeiro uso, o Windows pode demorar alguns segundos para abrir o EXE.")


if __name__ == "__main__":
    main()
