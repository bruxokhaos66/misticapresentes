import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, hash_password_pbkdf2
from database import init_db, query_db


def resetar_senha(login, nova_senha):
    login = str(login or "").strip().lower()
    nova_senha = str(nova_senha or "")
    if not login:
        raise SystemExit("Informe o login.")
    if len(nova_senha) < 4:
        raise SystemExit("A senha precisa ter pelo menos 4 caracteres.")

    init_db()
    usuario = query_db(
        "SELECT id, nome, login, perfil, COALESCE(ativo,1) FROM usuarios WHERE lower(trim(login))=?",
        (login,),
    )
    if not usuario:
        existentes = query_db("SELECT login, nome, perfil, COALESCE(ativo,1) FROM usuarios ORDER BY login")
        print(f"Usuario '{login}' nao encontrado no banco local: {DB_PATH}")
        print("Usuarios encontrados:")
        for u in existentes:
            print(f"- login={u[0]} | nome={u[1]} | perfil={u[2]} | ativo={u[3]}")
        raise SystemExit(1)

    salt = secrets.token_hex(16)
    senha_hash = hash_password_pbkdf2(nova_senha, salt.encode("utf-8"))
    query_db(
        "UPDATE usuarios SET senha_hash=?, senha_salt=?, ativo=1 WHERE lower(trim(login))=?",
        (senha_hash, salt, login),
        commit=True,
    )
    u = usuario[0]
    print("Senha local atualizada com sucesso.")
    print(f"Banco: {DB_PATH}")
    print(f"Login: {u[2]}")
    print(f"Nome: {u[1]}")
    print(f"Perfil: {u[3]}")

    try:
        from services.usuario_sync_service import sincronizar_usuarios_com_api
        retorno = sincronizar_usuarios_com_api(timeout=8)
        print("Sincronizacao com API:", retorno)
    except Exception as exc:
        print("Aviso: senha local foi atualizada, mas a sincronizacao com a API falhou:", exc)
        print("Abra o desktop ou rode a sincronizacao manual depois.")


def listar_usuarios():
    init_db()
    print(f"Banco: {DB_PATH}")
    rows = query_db("SELECT login, nome, perfil, COALESCE(ativo,1) FROM usuarios ORDER BY login")
    if not rows:
        print("Nenhum usuario encontrado.")
        return
    for r in rows:
        print(f"login={r[0]} | nome={r[1]} | perfil={r[2]} | ativo={r[3]}")


def main():
    parser = argparse.ArgumentParser(description="Reseta senha de usuario local da Mistica Presentes.")
    parser.add_argument("login", nargs="?", help="Login do usuario, exemplo: bruxo")
    parser.add_argument("senha", nargs="?", help="Nova senha")
    parser.add_argument("--listar", action="store_true", help="Lista usuarios locais")
    args = parser.parse_args()

    if args.listar:
        listar_usuarios()
        return
    if not args.login or not args.senha:
        parser.print_help()
        raise SystemExit(1)
    resetar_senha(args.login, args.senha)


if __name__ == "__main__":
    main()
