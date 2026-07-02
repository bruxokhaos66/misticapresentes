from __future__ import annotations

import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = Path.home() / "Documents"
LOG_DIR = DOCS / "Mistica_Servidor_Dedicado"
CLOUDFLARE_LOG = LOG_DIR / "cloudflared_ultimo.log"
PORTA = "8000"
LOCAL = f"http://127.0.0.1:{PORTA}"


def abrir_janela(titulo: str, comando: str) -> None:
    processo = [
        "powershell",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"$host.UI.RawUI.WindowTitle='{titulo}'; {comando}",
    ]
    subprocess.Popen(processo, cwd=str(ROOT))


def abrir_desktop() -> None:
    opcoes = [
        Path.home() / "Desktop" / "MisticaPresentes.exe",
        Path.home() / "Área de Trabalho" / "MisticaPresentes.exe",
        Path.home() / "OneDrive" / "Desktop" / "MisticaPresentes.exe",
        Path.home() / "OneDrive" / "Área de Trabalho" / "MisticaPresentes.exe",
    ]
    for exe in opcoes:
        if exe.exists():
            subprocess.Popen([str(exe)], cwd=str(ROOT))
            print(f"[OK] Sistema desktop aberto: {exe}")
            return
    abrir_janela("Mistica Presentes - Desktop", "python app.py")
    print("[OK] Sistema desktop iniciado pelo codigo.")


def servidor_online() -> bool:
    try:
        with urllib.request.urlopen(f"{LOCAL}/health", timeout=2) as resposta:
            return resposta.status == 200
    except Exception:
        return False


def esperar_servidor() -> bool:
    for _ in range(25):
        if servidor_online():
            return True
        time.sleep(1)
    return False


def iniciar_servidor() -> None:
    if servidor_online():
        print("[OK] Servidor local ja esta online.")
        return
    abrir_janela("Mistica Presentes - Servidor", "python scripts\\iniciar_servidor_dedicado.py")
    print("[OK] Servidor dedicado iniciado.")
    if esperar_servidor():
        print(f"[OK] Servidor respondendo em {LOCAL}")
    else:
        print("[AVISO] Servidor ainda nao respondeu. Confira a janela do servidor.")


def iniciar_cloudflare() -> str | None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if CLOUDFLARE_LOG.exists():
            CLOUDFLARE_LOG.unlink()
    except Exception:
        pass
    comando = f"cloudflared tunnel --url {LOCAL} 2>&1 | Tee-Object -FilePath '{CLOUDFLARE_LOG}'"
    abrir_janela("Mistica Presentes - Cloudflare", comando)
    print("[OK] Cloudflare iniciado.")
    print("[INFO] Aguardando endereco trycloudflare...")

    padrao = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    for _ in range(40):
        time.sleep(1)
        if CLOUDFLARE_LOG.exists():
            texto = CLOUDFLARE_LOG.read_text(encoding="utf-8", errors="ignore")
            achou = padrao.search(texto)
            if achou:
                return achou.group(0)
    return None


def main() -> None:
    os.chdir(ROOT)
    print("=" * 72)
    print("Mistica Presentes - Iniciador do Dia")
    print("=" * 72)
    print(f"Projeto: {ROOT}")

    abrir_desktop()
    iniciar_servidor()
    endereco = iniciar_cloudflare()

    print("\n" + "=" * 72)
    print("COPIE ESTE SERVIDOR NO APLICATIVO")
    print("=" * 72)
    if endereco:
        print(endereco)
    else:
        print("Nao consegui detectar automaticamente. Veja a janela Cloudflare e copie o link trycloudflare.com.")

    print("\nDepois, no app, confira se o token salvo continua correto.")
    print("Deixe abertas as janelas do Servidor e do Cloudflare durante o dia.")
    input("\nPressione ENTER para fechar somente este resumo...")


if __name__ == "__main__":
    main()
