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


class VendaItemSyncIn(BaseModel):
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = 0
    custo_unitario: float = 0.0
    valor_unitario: float = 0.0
    valor_total: float = 0.0


class VendaSyncIn(BaseModel):
    local_id: Optional[int] = None
    cliente: Optional[str] = "Cliente não informado"
    subtotal: float = 0.0
    desconto: float = 0.0
    taxa: float = 0.0
    total_final: float = 0.0
    forma_pagamento: Optional[str] = None
    vendedor: Optional[str] = None
    status: Optional[str] = "Concluído"
    data_venda: Optional[str] = None
    data_iso: Optional[str] = None
    dia_operacional: Optional[str] = None
    itens: list[VendaItemSyncIn] = Field(default_factory=list)


class VendasLotePayload(BaseModel):
    vendas: list[VendaSyncIn] = Field(default_factory=list)


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


def _garantir_colunas_venda(conn):
    for sql in [
        "ALTER TABLE vendas ADD COLUMN origem_sync TEXT",
        "ALTER TABLE vendas ADD COLUMN local_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_vendas_local_id ON vendas(local_id)",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass


def _salvar_venda_conn(conn, venda: VendaSyncIn):
    _garantir_colunas_venda(conn)
    agora = datetime.now()
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    dia_operacional = venda.dia_operacional or agora.strftime("%Y-%m-%d")
    status_venda = venda.status or "Concluído"
    existente = None
    if venda.local_id:
        existente = conn.execute(
            "SELECT id FROM vendas WHERE local_id=? AND origem_sync='desktop'",
            (venda.local_id,),
        ).fetchone()
    if existente:
        venda_id = int(existente["id"])
        conn.execute(
            """
            UPDATE vendas
               SET cliente=?, data_venda=?, subtotal=?, desconto=?, taxa=?, total_final=?,
                   forma_pagamento=?, vendedor=?, status=?, data_iso=?, dia_operacional=?, origem_sync='desktop', local_id=?
             WHERE id=?
            """,
            (
                venda.cliente,
                data_venda,
                float(venda.subtotal or 0),
                float(venda.desconto or 0),
                float(venda.taxa or 0),
                float(venda.total_final or 0),
                venda.forma_pagamento,
                venda.vendedor,
                status_venda,
                data_iso,
                dia_operacional,
                venda.local_id,
                venda_id,
            ),
        )
        conn.execute("DELETE FROM vendas_itens WHERE venda_id=?", (venda_id,))
        resultado = "atualizado"
    else:
        cur = conn.execute(
            """
            INSERT INTO vendas (
                cliente, data_venda, subtotal, desconto, taxa, total_final,
                forma_pagamento, vendedor, status, data_iso, dia_operacional, origem_sync, local_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                venda.cliente,
                data_venda,
                float(venda.subtotal or 0),
                float(venda.desconto or 0),
                float(venda.taxa or 0),
                float(venda.total_final or 0),
                venda.forma_pagamento,
                venda.vendedor,
                status_venda,
                data_iso,
                dia_operacional,
                "desktop",
                venda.local_id,
            ),
        )
        venda_id = int(cur.lastrowid)
        resultado = "criado"
    for item in venda.itens:
        conn.execute(
            """
            INSERT INTO vendas_itens
            (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                venda_id,
                item.codigo_p,
                item.nome_p,
                int(item.quantidade or 0),
                float(item.custo_unitario or 0),
                float(item.valor_unitario or 0),
                float(item.valor_total or 0),
            ),
        )
    return {"id": venda_id, "local_id": venda.local_id, "status": resultado}


@router.post("/api/auth/login")
def login_painel_mobile(entrada: LoginPainelIn):
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
                    (usuario.nome or login, login, usuario.senha_hash, usuario.senha_salt or "mistica_presentes", perfil, ativo, existente["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (usuario.nome or login, login, usuario.senha_hash, usuario.senha_salt or "mistica_presentes", perfil, ativo),
                )
            total += 1
            recebidos.append(f"{login}:{perfil}:{ativo}")
    _log_auth("SYNC_USUARIOS", f"total={total} usuarios={', '.join(recebidos[:30])}")
    return {"status": "ok", "usuarios_sincronizados": total, "data_hora": datetime.now().isoformat(timespec="seconds")}


@router.post("/api/sync/venda")
def sincronizar_venda(venda: VendaSyncIn, x_mistica_sync_key: str | None = Header(default=None)):
    _validar_chave_sync(x_mistica_sync_key)
    with conectar() as conn:
        retorno = _salvar_venda_conn(conn, venda)
    _log_auth("SYNC_VENDA", f"local_id={venda.local_id} status={retorno['status']}")
    return retorno | {"data_hora": datetime.now().isoformat(timespec="seconds")}


@router.post("/api/sync/vendas-lote")
def sincronizar_vendas_lote(payload: VendasLotePayload, x_mistica_sync_key: str | None = Header(default=None)):
    _validar_chave_sync(x_mistica_sync_key)
    retornos = []
    with conectar() as conn:
        _garantir_colunas_venda(conn)
        for venda in payload.vendas:
            retornos.append(_salvar_venda_conn(conn, venda))
    criados = sum(1 for r in retornos if r.get("status") == "criado")
    atualizados = sum(1 for r in retornos if r.get("status") == "atualizado")
    _log_auth("SYNC_VENDAS_LOTE", f"total={len(retornos)} criados={criados} atualizados={atualizados}")
    return {"status": "ok", "total": len(retornos), "criados": criados, "atualizados": atualizados, "data_hora": datetime.now().isoformat(timespec="seconds")}


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
    return listar(
        """
        SELECT id, nome, login, perfil, COALESCE(ativo,1) AS ativo
        FROM usuarios
        ORDER BY login COLLATE NOCASE
        """
    )
