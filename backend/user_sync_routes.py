import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, listar
from config import hash_password_pbkdf2

router = APIRouter()


class UsuarioSyncIn(BaseModel):
    nome: Optional[str] = None
    login: str = Field(min_length=1)
    senha_hash: str = Field(min_length=20)
    senha_salt: Optional[str] = None
    perfil: Optional[str] = "vendedor"
    ativo: int = 1


class UsuariosSyncPayload(BaseModel):
    usuarios: list[UsuarioSyncIn] = Field(default_factory=list)


class LoginPainelIn(BaseModel):
    login: str = Field(min_length=1)
    senha: str = Field(min_length=1)


def _log_auth(tag, detalhe):
    try:
        print(f"[{tag}] {datetime.now().isoformat(timespec='seconds')} - {detalhe}")
    except Exception:
        pass


def _normalizar_login(login):
    return str(login or "").strip().lower()


def _normalizar_perfil(perfil):
    texto = str(perfil or "vendedor").strip().lower()
    if texto in ("adm", "admin", "administrador"):
        return "adm"
    return "vendedor"


def _permissoes_por_perfil(perfil):
    if perfil == "adm":
        return {
            "produtos": True,
            "estoque": True,
            "vendas": True,
            "clientes": True,
            "fornecedores": True,
            "backup": True,
            "admin": True,
        }
    return {
        "produtos": True,
        "estoque": True,
        "vendas": True,
        "clientes": False,
        "fornecedores": False,
        "backup": False,
        "admin": False,
    }


def _validar_chave_sync(x_mistica_sync_key: str | None):
    chave = os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if chave and x_mistica_sync_key != chave:
        raise HTTPException(status_code=403, detail="Chave de sincronização inválida")


@router.post("/api/auth/login")
def login_painel_mobile(entrada: LoginPainelIn):
    """Login usado pelo painel mobile.

    Esta rota fica no router incluído antes das rotas principais, então evita
    diferenças entre maiúsculas/minúsculas e espaços no login sincronizado.
    """
    login = _normalizar_login(entrada.login)
    _log_auth("LOGIN_API", f"tentativa login={login}")
    with conectar() as conn:
        usuario = conn.execute(
            """
            SELECT id, nome, login, senha_hash, senha_salt, perfil, ativo
            FROM usuarios
            WHERE lower(trim(login))=? AND COALESCE(ativo,1)=1
            """,
            (login,),
        ).fetchone()
    if not usuario:
        _log_auth("LOGIN_FALHA", f"usuario nao encontrado login={login}")
        raise HTTPException(status_code=401, detail="Login ou senha inválidos")

    salt_txt = str(usuario["senha_salt"] or "mistica_presentes")
    senha_hash = hash_password_pbkdf2(entrada.senha, salt_txt.encode("utf-8"))
    if senha_hash != usuario["senha_hash"]:
        _log_auth("LOGIN_FALHA", f"senha nao confere login={login}")
        raise HTTPException(status_code=401, detail="Login ou senha inválidos")

    perfil = _normalizar_perfil(usuario["perfil"])
    _log_auth("LOGIN_SUCESSO", f"login={login} perfil={perfil}")
    return {
        "status": "ok",
        "usuario": {
            "id": usuario["id"],
            "nome": usuario["nome"] or usuario["login"],
            "login": usuario["login"],
            "perfil": perfil,
        },
        "permissoes": _permissoes_por_perfil(perfil),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/api/sync/usuarios")
def sincronizar_usuarios(payload: UsuariosSyncPayload, x_mistica_sync_key: str | None = Header(default=None)):
    """Recebe usuários do programa desktop e replica no servidor."""
    _validar_chave_sync(x_mistica_sync_key)
    total = 0
    recebidos = []
    with conectar() as conn:
        for usuario in payload.usuarios:
            login = _normalizar_login(usuario.login)
            if not login:
                continue
            perfil = _normalizar_perfil(usuario.perfil)
            ativo = 1 if int(usuario.ativo or 0) else 0
            existente = conn.execute("SELECT id FROM usuarios WHERE lower(trim(login))=?", (login,)).fetchone()
            if existente:
                conn.execute(
                    """
                    UPDATE usuarios
                    SET nome=?, login=?, senha_hash=?, senha_salt=?, perfil=?, ativo=?
                    WHERE id=?
                    """,
                    (
                        usuario.nome or login,
                        login,
                        usuario.senha_hash,
                        usuario.senha_salt or "mistica_presentes",
                        perfil,
                        ativo,
                        existente["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        usuario.nome or login,
                        login,
                        usuario.senha_hash,
                        usuario.senha_salt or "mistica_presentes",
                        perfil,
                        ativo,
                    ),
                )
            total += 1
            recebidos.append(f"{login}:{perfil}:{ativo}")
    _log_auth("SYNC_USUARIOS", f"total={total} usuarios={', '.join(recebidos[:30])}")
    return {"status": "ok", "usuarios_sincronizados": total, "data_hora": datetime.now().isoformat(timespec="seconds")}


@router.get("/api/usuarios")
def listar_usuarios_api():
    return listar(
        """
        SELECT id, nome, login, perfil, ativo
        FROM usuarios
        WHERE COALESCE(ativo,1)=1
        ORDER BY nome COLLATE NOCASE
        """
    )


@router.get("/api/auth/usuarios-debug")
def listar_usuarios_debug():
    """Lista usuários sem expor senha/hash, para auditoria de login."""
    return listar(
        """
        SELECT id, nome, login, perfil, COALESCE(ativo,1) AS ativo
        FROM usuarios
        ORDER BY login COLLATE NOCASE
        """
    )
