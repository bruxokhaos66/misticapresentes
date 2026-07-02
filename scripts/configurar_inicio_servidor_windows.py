"""Configura inicializacao automatica do servidor dedicado no Windows.

Cria um token forte para a API, salva no perfil do usuario e cria um arquivo
.bat na pasta Startup do Windows para iniciar o servidor ao fazer login.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path.home() / "Documents" / "Mistica_Servidor_Dedicado"
TOKEN_FILE = CONFIG_DIR / "api_token.txt"
STARTUP_DIR = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
BAT_FILE = STARTUP_DIR / "MisticaServidorDedicado.bat"


def gerar_ou_ler_token() -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token and token != "mistica-local" and len(token) >= 12:
            return token
    token = "Mistica-" + secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def criar_bat(token: str):
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    conteudo = f"""@echo off
cd /d "{ROOT}"
set MISTICA_API_TOKEN={token}
python scripts\iniciar_servidor_dedicado.py
"""
    BAT_FILE.write_text(conteudo, encoding="ascii")


def main():
    token = gerar_ou_ler_token()
    criar_bat(token)
    print("Configuração concluída.")
    print("Token salvo em:", TOKEN_FILE)
    print("Inicialização criada em:", BAT_FILE)
    print("Use este token no app Mística Painel:")
    print(token)
    print("Reinicie o Windows ou execute o arquivo .bat para testar.")


if __name__ == "__main__":
    main()
