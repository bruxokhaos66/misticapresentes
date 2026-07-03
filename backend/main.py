from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import executar, listar, obter
from config import API_URL, DB_PATH, DEFAULT_API_URL, DEFAULT_SERVER_URL, OFFICIAL_DOMAIN, SERVER_URL
from database.migrations import init_db


app = FastAPI(
    title="Mística Presentes API",
    description="API oficial para sincronização do app Mística Presentes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://misticaesotericos.com.br",
        "https://www.misticaesotericos.com.br",
        "https://api.misticaesotericos.com.br",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class VendaIn(BaseModel):
    cliente: Optional[str] = "Cliente não informado"
    subtotal: float = 0.0
    desconto: float = 0.0
    taxa: float = 0.0
    total_final: float = 0.0
    forma_pagamento: Optional[str] = None
    vendedor: Optional[str] = None
    data_venda: Optional[str] = None
    data_iso: Optional[str] = None
    dia_operacional: Optional[str] = None


@app.on_event("startup")
def startup():
    init_db()


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
    total_vendas = obter("SELECT COUNT(*) AS total FROM vendas WHERE COALESCE(status,'Concluído')!='Cancelada'") or {"total": 0}
    return {
        "status": "online",
        "produtos": total_produtos["total"],
        "clientes": total_clientes["total"],
        "vendas": total_vendas["total"],
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
               forma_pagamento, vendedor, status, data_iso, dia_operacional
        FROM vendas
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,),
    )


@app.post("/api/vendas")
def criar_venda(venda: VendaIn):
    agora = datetime.now()
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    dia_operacional = venda.dia_operacional or agora.strftime("%Y-%m-%d")
    novo_id = executar(
        """
        INSERT INTO vendas (
            cliente, data_venda, subtotal, desconto, taxa, total_final,
            forma_pagamento, vendedor, status, data_iso, dia_operacional
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
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
            "Concluído",
            data_iso,
            dia_operacional,
        ),
    )
    return {"id": novo_id, "status": "criado"}


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
