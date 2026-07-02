"""Assistente local de recuperacao do administrador.

Este script nao altera o banco de dados e nao grava credenciais no GitHub.
Ele apenas localiza os arquivos locais de recuperacao gerados pelo proprio
sistema no computador da loja.
"""
from __future__ import annotations

from pathlib import Path

DOCS = Path.home() / "Documents"
ARQUIVOS = [
    DOCS / "mistica_senha_admin_inicial.txt",
    DOCS / "mistica_senha_admin_recuperada.txt",
]


def main():
    print("=" * 68)
    print("Mistica Presentes - Ajuda para recuperar acesso admin")
    print("=" * 68)
    print("Este assistente nao altera o banco de dados.")
    print("Ele apenas mostra onde estao os arquivos locais de recuperacao.")
    print()

    encontrados = []
    for caminho in ARQUIVOS:
        if caminho.exists():
            encontrados.append(caminho)
            print("Arquivo encontrado:")
            print(caminho)
            print()

    if not encontrados:
        print("Nenhum arquivo de recuperacao foi encontrado em Documents.")
        print("Aguarde 5 minutos se o login estiver bloqueado por tentativas.")
        print("Depois tente entrar com uma conta de administrador cadastrada.")
        return

    print("Abra o arquivo acima no Bloco de Notas para consultar o login temporario.")
    print("Depois de entrar no sistema, troque a senha do administrador.")
    print("Se o sistema estiver bloqueado por tentativas, feche e abra novamente ou aguarde 5 minutos.")


if __name__ == "__main__":
    main()
