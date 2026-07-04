import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import conectar, executar, listar, obter
from backend.user_sync_routes import router as user_sync_router
from backend.site_stock_routes import router as site_stock_router
from config import API_URL, DB_PATH, DEFAULT_API_URL, DEFAULT_SERVER_URL, OFFICIAL_DOMAIN, SERVER_URL, hash_password_pbkdf2
from database.migrations import init_db


app = FastAPI(
    title="Mística Presentes API",
    description="API oficial para sincronização do app Mística Presentes.",
    version="0.3.4",
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

app.include_router(user_sync_router)
app.include_router(site_stock_router)


class ProdutoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    preco: float = 0.0
    quantidade: int = 0
    categoria: Optional[str] = None
    custo: float = 0.0
    lucro: float = 0.0
    estoque_minimo: int = 0


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
    senha_admin = os.environ.get("MISTICA_ADMIN_PASSWORD", "Mistica@123").strip()
    if not senha_admin:
        return
    salt = "mistica_api_admin"
    senha_hash = hash_password_pbkdf2(senha_admin, salt.encode("utf-8"))
    existente = obter("SELECT id FROM usuarios WHERE login='admin'")
    if existente:
        executar(
            """
            UPDATE usuarios
            SET nome=?, senha_hash=?, senha_salt=?, perfil=?, ativo=1
            WHERE login='admin'
            """,
            ("Administrador", senha_hash, salt, "adm"),
        )
    else:
        executar(
            """
            INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo)
            VALUES (?,?,?,?,?,1)
            """,
            ("Administrador", "admin", senha_hash, salt, "adm"),
        )


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
    login = entrada.login.strip()
    usuario = obter(
        """
        SELECT id, nome, login, senha_hash, senha_salt, perfil, ativo
        FROM usuarios
        WHERE login=? AND COALESCE(ativo,1)=1
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


@app.post("/api/produtos")
def criar_produto(produto: ProdutoIn):
    novo_id = executar(
        """
        INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, ativo)
        VALUES (?,?,?,?,?,?,?,?,1)
        """,
        (
            produto.codigo_p,
            produto.nome,
            produto.preco,
            produto.quantidade,
            produto.categoria,
            produto.custo,
            produto.lucro,
            produto.estoque_minimo,
        ),
    )
    return {"id": novo_id, "status": "criado"}


@app.get("/api/produtos/{produto_id}")
def obter_produto(produto_id: int):
    produto = obter(
        """
        SELECT id, codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo
        FROM produtos
        WHERE id=? AND COALESCE(ativo,1)=1
        """,
        (produto_id,),
    )
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return produto


@app.get("/api/clientes")
def listar_clientes(busca: str = "", limite: int = Query(100, ge=1, le=500)):
    termo = f"%{busca.strip()}%"
    if busca.strip():
        return listar(
            """
            SELECT id, nome, telefone, cpf, endereco, nascimento
            FROM clientes
            WHERE COALESCE(ativo,1)=1 AND (nome LIKE ? OR telefone LIKE ? OR cpf LIKE ?)
            ORDER BY nome COLLATE NOCASE
            LIMIT ?
            """,
            (termo, termo, termo, limite),
        )
    return listar(
        """
        SELECT id, nome, telefone, cpf, endereco, nascimento
        FROM clientes
        WHERE COALESCE(ativo,1)=1
        ORDER BY nome COLLATE NOCASE
        LIMIT ?
        """,
        (limite,),
    )


@app.post("/api/clientes")
def criar_cliente(cliente: ClienteIn):
    novo_id = executar(
        """
        INSERT INTO clientes (nome, telefone, cpf, endereco, nascimento, ativo)
        VALUES (?,?,?,?,?,1)
        """,
        (cliente.nome, cliente.telefone, cliente.cpf, cliente.endereco, cliente.nascimento),
    )
    return {"id": novo_id, "status": "criado"}


@app.get("/api/vendas")
def listar_vendas(limite: int = Query(100, ge=1, le=500)):
    return listar(
        """
        SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
               forma_pagamento, vendedor, status, data_iso, dia_operacional,
               origem_sync, local_id
        FROM vendas
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,),
    )


def _buscar_produto_para_baixa(conn, item: VendaItemIn):
    if item.produto_id:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
            (item.produto_id,),
        ).fetchone()
        if produto:
            return produto
    if item.codigo_p:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (item.codigo_p,),
        ).fetchone()
        if produto:
            return produto
    return None


def _baixar_estoque_venda(conn, itens: list[VendaItemIn]):
    for item in itens:
        produto = _buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado: {item.codigo_p or item.nome_p}")
        estoque_atual = int(produto["quantidade"] or 0)
        quantidade = int(item.quantidade or 0)
        if estoque_atual < quantidade:
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {estoque_atual}")

    for item in itens:
        produto = _buscar_produto_para_baixa(conn, item)
        conn.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (int(item.quantidade or 0), produto["id"]))


def salvar_venda_online(venda: VendaIn, origem_sync="api"):
    garantir_colunas_sync_backend()
    agora = datetime.now()
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    dia_operacional = venda.dia_operacional or agora.strftime("%d/%m/%Y")

    if venda.local_id:
        existente = obter(
            "SELECT id FROM vendas WHERE local_id=? AND origem_sync='desktop'",
            (venda.local_id,),
        )
        if existente:
            return {"id": existente["id"], "local_id": venda.local_id, "status": "ja_sincronizado"}

    with conectar() as conn:
        if venda.baixa_estoque:
            _baixar_estoque_venda(conn, venda.itens)

        cur = conn.execute(
            """
            INSERT INTO vendas (
                cliente, data_venda, subtotal, desconto, taxa, total_final,
                forma_pagamento, vendedor, status, data_iso, dia_operacional,
                origem_sync, local_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                venda.cliente,
                data_venda,
                venda.subtotal,
                venda.desconto,
                venda.taxa,
                venda.total_final,
                venda.forma_pagamento,
                venda.vendedor,
                venda.status or "Concluído",
                data_iso,
                dia_operacional,
                origem_sync,
                venda.local_id,
            ),
        )
        venda_id = int(cur.lastrowid)
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
                    item.custo_unitario,
                    item.valor_unitario,
                    item.valor_total,
                ),
            )
    return {"id": venda_id, "local_id": venda.local_id, "status": "criado", "estoque_baixado": venda.baixa_estoque}


@app.post("/api/vendas")
def criar_venda(venda: VendaIn):
    return salvar_venda_online(venda, origem_sync="api")


@app.post("/api/sync/venda")
def sincronizar_venda(venda: VendaIn):
    return salvar_venda_online(venda, origem_sync="desktop")


@app.get("/api/estoque/baixo")
def estoque_baixo(limite: int = Query(100, ge=1, le=500)):
    return listar(
        """
        SELECT id, codigo_p, nome, quantidade, estoque_minimo, categoria
        FROM produtos
        WHERE COALESCE(ativo,1)=1
          AND COALESCE(estoque_minimo,0) > 0
          AND quantidade <= estoque_minimo
        ORDER BY quantidade ASC, nome COLLATE NOCASE
        LIMIT ?
        """,
        (limite,),
    )
