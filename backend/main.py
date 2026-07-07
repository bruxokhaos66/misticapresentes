import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.backup_routes import router as backup_router
from backend.database import conectar, executar, listar, obter
from backend.order_status_routes import router as order_status_router
from backend.payment_routes import router as payment_router
from backend.product_routes import router as product_router
from backend.upload_routes import router as upload_router
from backend.user_sync_routes import router as user_sync_router
from backend.site_stock_routes import router as site_stock_router
from backend.system_status_routes import router as system_status_router
from config import API_URL, DB_PATH, DEFAULT_API_URL, DEFAULT_SERVER_URL, OFFICIAL_DOMAIN, SERVER_URL, hash_password_pbkdf2
from database.migrations import init_db


app = FastAPI(
    title="Mística Presentes API",
    description="API oficial para sincronização do app Mística Presentes.",
    version="0.3.9",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://misticaesotericos.com.br",
        "https://www.misticaesotericos.com.br",
        "https://api.misticaesotericos.com.br",
        "https://bruxokhaos66.github.io",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(product_router)
app.include_router(user_sync_router)
app.include_router(site_stock_router)
app.include_router(order_status_router)
app.include_router(payment_router)
app.include_router(upload_router)
app.include_router(system_status_router)
app.include_router(backup_router)


class ProdutoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    preco: float = 0.0
    quantidade: int = 0
    categoria: Optional[str] = None
    custo: float = 0.0
    lucro: float = 0.0
    estoque_minimo: int = 0


class ProdutosLotePayload(BaseModel):
    produtos: list[ProdutoIn] = Field(default_factory=list)


class ClienteIn(BaseModel):
    nome: str = Field(min_length=1)
    telefone: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    nascimento: Optional[str] = None


class VendaItemIn(BaseModel):
    produto_id: Optional[int] = None
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = 0
    custo_unitario: float = 0.0
    valor_unitario: float = 0.0
    valor_total: float = 0.0


class VendaIn(BaseModel):
    origem: Optional[str] = "api"
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
    baixa_estoque: bool = False
    itens: list[VendaItemIn] = Field(default_factory=list)


class LoginIn(BaseModel):
    login: str = Field(min_length=1)
    senha: str = Field(min_length=1)


@app.on_event("startup")
def startup():
    init_db()
    garantir_colunas_sync_backend()
    garantir_admin_api()


def garantir_colunas_sync_backend():
    comandos = [
        "ALTER TABLE vendas ADD COLUMN origem_sync TEXT",
        "ALTER TABLE vendas ADD COLUMN local_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_vendas_local_id ON vendas(local_id)",
    ]
    with conectar() as conn:
        for sql in comandos:
            try:
                conn.execute(sql)
            except Exception:
                pass


def garantir_admin_api():
    senha_admin = os.environ.get("MISTICA_ADMIN_PASSWORD", "").strip()
    if not senha_admin:
        print("[API] MISTICA_ADMIN_PASSWORD não configurada; admin automático não será criado ou redefinido.")
        return

    salt = "mistica_api_admin"
    senha_hash = hash_password_pbkdf2(senha_admin, salt.encode("utf-8"))
    admins = [
        ("admin", "Administrador"),
        ("bruxo", "Fredi Bach"),
        ("bruxa", "Natalia Grunwald"),
    ]

    for login, nome in admins:
        existente = obter("SELECT id FROM usuarios WHERE lower(trim(login))=lower(trim(?))", (login,))
        if existente:
            executar(
                """
                UPDATE usuarios
                SET nome=?, login=?, senha_hash=?, senha_salt=?, perfil=?, ativo=1
                WHERE id=?
                """,
                (nome, login, senha_hash, salt, "adm", existente["id"]),
            )
        else:
            executar(
                """
                INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo)
                VALUES (?,?,?,?,?,1)
                """,
                (nome, login, senha_hash, salt, "adm"),
            )
    print("[API] Administradores da API garantidos: admin, bruxo, bruxa.")


def _normalizar_perfil(perfil: str | None):
    texto = str(perfil or "vendedor").strip().lower()
    if texto in ("adm", "admin", "administrador"):
        return "adm"
    return "vendedor"


def _permissoes_por_perfil(perfil: str):
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


@app.get("/")
def raiz():
    return {
        "app": "Mística Presentes API",
        "status": "online",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "app": "Mística Presentes",
        "domain": OFFICIAL_DOMAIN,
        "server_url": SERVER_URL or DEFAULT_SERVER_URL,
        "api_url": API_URL or DEFAULT_API_URL,
        "database": DB_PATH,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/api/status")
def status():
    total_produtos = obter("SELECT COUNT(*) AS total FROM produtos WHERE COALESCE(ativo,1)=1") or {"total": 0}
    total_clientes = obter("SELECT COUNT(*) AS total FROM clientes WHERE COALESCE(ativo,1)=1") or {"total": 0}
    total_vendas = obter("SELECT COUNT(*) AS total FROM vendas WHERE COALESCE(status,'Concluído') NOT IN ('Cancelado','Cancelada')") or {"total": 0}
    return {
        "status": "online",
        "produtos": total_produtos["total"],
        "clientes": total_clientes["total"],
        "vendas": total_vendas["total"],
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@app.post("/api/auth/login")
def login_painel(entrada: LoginIn):
    login = entrada.login.strip().lower()
    usuario = obter(
        """
        SELECT id, nome, login, senha_hash, senha_salt, perfil, ativo
        FROM usuarios
        WHERE lower(trim(login))=? AND COALESCE(ativo,1)=1
        """,
        (login,),
    )
    if not usuario:
        raise HTTPException(status_code=401, detail="Login ou senha inválidos")

    salt = str(usuario.get("senha_salt") or "").encode("utf-8") if usuario.get("senha_salt") else b"mistica_presentes"
    senha_hash = hash_password_pbkdf2(entrada.senha, salt)
    if senha_hash != usuario.get("senha_hash"):
        raise HTTPException(status_code=401, detail="Login ou senha inválidos")

    perfil = _normalizar_perfil(usuario.get("perfil"))
    return {
        "status": "ok",
        "usuario": {
            "id": usuario.get("id"),
            "nome": usuario.get("nome") or usuario.get("login"),
            "login": usuario.get("login"),
            "perfil": perfil,
        },
        "permissoes": _permissoes_por_perfil(perfil),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/api/painel/resumo")
def painel_resumo():
    total_produtos = obter("SELECT COUNT(*) AS total FROM produtos WHERE COALESCE(ativo,1)=1") or {"total": 0}
    total_clientes = obter("SELECT COUNT(*) AS total FROM clientes WHERE COALESCE(ativo,1)=1") or {"total": 0}
    total_vendas = obter("SELECT COUNT(*) AS total FROM vendas WHERE COALESCE(status,'Concluído') NOT IN ('Cancelado','Cancelada')") or {"total": 0}
    venda_total = obter("SELECT COALESCE(SUM(total_final),0) AS total FROM vendas WHERE COALESCE(status,'Concluído') NOT IN ('Cancelado','Cancelada')") or {"total": 0}
    estoque_total = obter("SELECT COALESCE(SUM(quantidade),0) AS total FROM produtos WHERE COALESCE(ativo,1)=1") or {"total": 0}
    return {
        "produtos": total_produtos["total"],
        "clientes": total_clientes["total"],
        "vendas": total_vendas["total"],
        "faturamento_total": venda_total["total"],
        "pecas_estoque": estoque_total["total"],
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/api/produtos")
def listar_produtos(busca: str = "", limite: int = Query(100, ge=1, le=500)):
    termo = f"%{busca.strip()}%"
    if busca.strip():
        return listar(
            """
            SELECT id, codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo
            FROM produtos
            WHERE COALESCE(ativo,1)=1 AND (nome LIKE ? OR codigo_p LIKE ? OR categoria LIKE ?)
            ORDER BY nome COLLATE NOCASE
            LIMIT ?
            """,
            (termo, termo, termo, limite),
        )
    return listar(
        """
        SELECT id, codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo
        FROM produtos
        WHERE COALESCE(ativo,1)=1
        ORDER BY nome COLLATE NOCASE
        LIMIT ?
        """,
        (limite,),
    )
