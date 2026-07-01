"""Gera o executavel do sistema Mistica Presentes e copia para a Area de Trabalho.

Execute na raiz do projeto:
    python scripts/gerar_exe_area_trabalho.py
"""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
DIST_DIR = ROOT / "dist"
EXE_NAME = "Mistica Presentes.exe"
EXE_ORIGEM = DIST_DIR / EXE_NAME


def desktop_path() -> Path:
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    area = Path.home() / "Área de Trabalho"
    if area.exists():
        return area
    return desktop


def rodar(cmd):
    print("Executando:", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError(f"Nao encontrei o arquivo principal: {APP_FILE}")

    print("Atualizando dependencias...")
    rodar([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    print("Gerando executavel com PyInstaller...")
    rodar([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "Mistica Presentes",
        "app.py",
    ])

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
