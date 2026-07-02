"""Inicia a API local do Mística Presentes.

Execute na raiz do projeto:
    python scripts/iniciar_servidor_local.py

Depois acesse em outro computador/celular no mesmo Wi-Fi:
    http://IP-DO-COMPUTADOR-SERVIDOR:8000
"""
from pathlib import Path
import os
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    os.chdir(ROOT)
    ip = ip_local()
    token = os.getenv("MISTICA_API_TOKEN", "").strip()
    if token:
        token_texto = token
    else:
        token_texto = "(configure MISTICA_API_TOKEN)"
    print("=" * 62)
    print("Mística Presentes - Servidor local da loja")
    print("=" * 62)
    print("Painel neste computador: http://127.0.0.1:8000")
    print(f"Painel na rede local:   http://{ip}:8000")
    print(f"Token local atual:      {token_texto}")
    print("\nAtenção: use apenas na rede da loja ou via VPN/Tailscale/Cloudflare Tunnel.")
    print("Para parar: CTRL+C")
    print("=" * 62)
    subprocess.run([
        sys.executable,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ], cwd=str(ROOT), check=False)


if __name__ == "__main__":
    main()
