"""Gera o executavel do sistema Mistica Presentes e copia para a Area de Trabalho.

Execute na raiz do projeto:
    python scripts/gerar_exe_area_trabalho.py
"""
from pathlib import Path
import math
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
DIST_DIR = ROOT / "dist"
ASSETS_DIR = ROOT / "assets"
ICON_PATH = ASSETS_DIR / "mistica_xamanico_moderno.ico"
EXE_NAME = "Mistica Presentes.exe"
EXE_ORIGEM = DIST_DIR / EXE_NAME

ARQUIVOS_DADOS = [
    ("mistica_presentes.py", "."),
    ("config.py", "."),
]

PASTAS_DADOS = [
    "assets",
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
    "database",
    "services",
    "repositories",
    "reports",
    "reports.estoque_report",
    "reports.financeiro_report",
    "reports.vendas_report",
    "reports.produtos_vendidos_report",
    "isis",
]

COLLECT_SUBMODULES = [
    "database",
    "services",
    "repositories",
    "reports",
    "isis",
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


def gerar_icone_xamanico():
    """Cria um icone .ico moderno com tema mistico/xamanico."""
    from PIL import Image, ImageDraw, ImageFilter

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)

    for r in range(125, 0, -1):
        t = r / 125
        red = int(18 + 25 * (1 - t))
        green = int(22 + 45 * (1 - t))
        blue = int(34 + 35 * (1 - t))
        draw.ellipse((128 - r, 128 - r, 128 + r, 128 + r), fill=(red, green, blue, 255))

    draw.ellipse((10, 10, 246, 246), outline=(218, 181, 109, 255), width=7)
    draw.ellipse((22, 22, 234, 234), outline=(116, 92, 50, 190), width=2)

    draw.ellipse((72, 42, 154, 124), fill=(226, 198, 126, 255))
    draw.ellipse((92, 36, 174, 118), fill=(25, 40, 48, 255))

    cristal = [(128, 66), (166, 124), (145, 202), (111, 202), (90, 124)]
    draw.polygon(cristal, fill=(72, 153, 133, 255), outline=(226, 198, 126, 255))
    draw.line((128, 66, 128, 202), fill=(205, 244, 220, 190), width=3)
    draw.line((90, 124, 166, 124), fill=(205, 244, 220, 130), width=2)
    draw.line((111, 202, 128, 124, 145, 202), fill=(30, 77, 70, 170), width=2)

    for lado in [-1, 1]:
        base_x = 128 + lado * 42
        pontos = []
        for i in range(9):
            y = 92 + i * 13
            x = base_x + lado * int(math.sin(i / 2) * 9)
            pontos.append((x, y))
        draw.line(pontos, fill=(226, 198, 126, 230), width=4)
        for x, y in pontos[1:8:2]:
            draw.line((x, y, x + lado * 22, y - 8), fill=(78, 160, 130, 220), width=3)
            draw.line((x, y, x + lado * 18, y + 8), fill=(78, 160, 130, 190), width=3)

    for x, y, rr in [(58, 161, 3), (199, 161, 3), (64, 82, 2), (193, 82, 2), (128, 34, 2)]:
        draw.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(226, 198, 126, 230))

    sombra = bg.filter(ImageFilter.GaussianBlur(0.4))
    img.alpha_composite(sombra)
    tamanhos = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ICON_PATH, format="ICO", sizes=tamanhos)
    print("Icone criado:", ICON_PATH)


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

    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])

    for arquivo, destino in ARQUIVOS_DADOS:
        origem = ROOT / arquivo
        if origem.exists():
            cmd.extend(["--add-data", add_data_arg(origem, destino)])

    for pasta in PASTAS_DADOS:
        origem = ROOT / pasta
        if origem.exists():
            cmd.extend(["--add-data", add_data_arg(origem, pasta)])

    cmd.extend(["--collect-all", "customtkinter"])

    for modulo in COLLECT_SUBMODULES:
        cmd.extend(["--collect-submodules", modulo])

    for item in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", item])

    cmd.append("app.py")
    return cmd


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError(f"Nao encontrei o arquivo principal: {APP_FILE}")

    print("Atualizando dependencias...")
    rodar([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    gerar_icone_xamanico()
    limpar_build_anterior()

    print("Gerando executavel com PyInstaller, icone xamanico e arquivos internos...")
    rodar(montar_comando_pyinstaller())

    if not EXE_ORIGEM.exists():
        raise FileNotFoundError(f"O executavel nao foi encontrado em: {EXE_ORIGEM}")

    destino = desktop_path() / EXE_NAME
    shutil.copy2(EXE_ORIGEM, destino)

    print("\nPronto!")
    print(f"Executavel criado em: {EXE_ORIGEM}")
    print(f"Copia enviada para a Area de Trabalho: {destino}")
    print(f"Icone usado: {ICON_PATH}")
    print("\nDica: se o Windows mostrar o icone antigo, reinicie o Explorer ou crie um atalho novo.")


if __name__ == "__main__":
    main()
