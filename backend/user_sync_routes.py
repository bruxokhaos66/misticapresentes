import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, listar

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


def _normalizar_perfil(perfil):
    texto = str(perfil or "vendedor").strip().lower()
    if texto in ("adm", "admin", "administrador"):
        return "adm"
    return "vendedor"


def _validar_chave_sync(x_mistica_sync_key: str | None):
    chave = os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if chave and x_mistica_sync_key != chave:
        raise HTTPException(status_code=403, detail="Chave de sincronização inválida")


@router.post("/api/sync/usuarios")
def sincronizar_usuarios(payload: UsuariosSyncPayload, x_mistica_sync_key: str | None = Header(default=None)):
    """Recebe usuários do programa desktop e replica no servidor.

    Não recebe senha em texto puro. O desktop envia somente senha_hash e senha_salt.
    Assim o aplicativo de celular consegue usar o mesmo login e senha cadastrados no programa.
    """
    _validar_chave_sync(x_mistica_sync_key)
    total = 0
    with conectar() as conn:
        for usuario in payload.usuarios:
            login = usuario.login.strip()
            if not login:
                continue
            perfil = _normalizar_perfil(usuario.perfil)
            ativo = 1 if int(usuario.ativo or 0) else 0
            existente = conn.execute("SELECT id FROM usuarios WHERE login=?", (login,)).fetchone()
            if existente:
                conn.execute(
                    """
                    UPDATE usuarios
                    SET nome=?, senha_hash=?, senha_salt=?, perfil=?, ativo=?
                    WHERE login=?
                    """,
                    (
                        usuario.nome or login,
                        usuario.senha_hash,
                        usuario.senha_salt or "mistica_presentes",
                        perfil,
                        ativo,
                        login,
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
