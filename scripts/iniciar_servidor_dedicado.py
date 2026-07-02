"""Servidor dedicado do Mística Presentes.

Roda separado do programa desktop. Ideal para deixar ativo no computador
principal da loja, permitindo acesso pelo app mesmo com o sistema desktop fechado.

Use junto com uma conexão segura para acesso externo, como Tailscale, VPN ou
Cloudflare Tunnel. Não é necessário abrir porta do roteador.
"""
from pathlib import Path
import os
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOST = os.getenv("MISTICA_SERVER_HOST", "0.0.0.0")
PORT = os.getenv("MISTICA_SERVER_PORT", "8000")
CONFIG_DIR = Path.home() / "Documents" / "Mistica_Servidor_Dedicado"
TOKEN_FILE = CONFIG_DIR / "api_token.txt"
TOKEN_PADRAO = "mistica-local"


def carregar_token_seguro():
    if os.getenv("MISTICA_API_TOKEN"):
        return os.getenv("MISTICA_API_TOKEN")
    try:
        if TOKEN_FILE.exists():
            token = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                os.environ["MISTICA_API_TOKEN"] = token
                return token
    except Exception:
        pass
    return TOKEN_PADRAO


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
    token_atual = carregar_token_seguro()
    ip = ip_local()
    print("=" * 68)
    print("Mística Presentes - Servidor dedicado")
    print("=" * 68)
    print("Este servidor roda separado do programa desktop.")
    print("O programa de vendas pode ficar fechado; o painel continua disponível.")
    print(f"Local:      http://127.0.0.1:{PORT}")
    print(f"Rede loja:  http://{ip}:{PORT}")
    print("Externo: use Tailscale, VPN ou Cloudflare Tunnel apontando para este servidor.")
    if token_atual == TOKEN_PADRAO:
        print("ATENÇÃO: usando token padrão. Para internet/Cloudflare, configure um token forte.")
        print("Rode: python scripts/configurar_inicio_servidor_windows.py")
    else:
        print("Token forte carregado para a API.")
    print("Para parar: CTRL+C")
    print("=" * 68)
    subprocess.run([
        sys.executable,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ], cwd=str(ROOT), check=False)


if __name__ == "__main__":
    main()
