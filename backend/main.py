import asyncio
import contextlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.backup_routes import router as backup_router
from backend.course_routes import router as course_router
from backend.database import conectar, executar, listar, obter
from backend.order_status_routes import expirar_pedidos_pendentes, router as order_status_router
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.payment_routes import router as payment_router
from backend.product_routes import router as product_router, validar_site_api_key
from backend.review_routes import router as review_router
from backend.upload_routes import router as upload_router
from backend.user_sync_routes import router as user_sync_router
from backend.site_stock_routes import router as site_stock_router
from backend.system_status_routes import router as system_status_router
from config import hash_password_pbkdf2
from database.migrations import init_db


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    garantir_admin_api()
    tarefa_expiracao = asyncio.create_task(_expirar_pedidos_periodicamente())
    try:
        yield
    finally:
        tarefa_expiracao.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa_expiracao


app = FastAPI(
    title="Mística Presentes API",
    description="API oficial para sincronização do app Mística Presentes.",
    version="0.3.8",
    lifespan=lifespan,
    # A documentação interativa expõe todos os endpoints, schemas e exemplos da
    # API; deixá-la pública facilita reconhecimento para ataques. As rotas
    # nativas ficam desativadas e são substituídas abaixo por versões que
    # exigem sessão de administrador (mesma dependência usada no painel).
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_OPENAPI_URL = "/openapi.json"


@app.get("/openapi.json", include_in_schema=False)
def openapi_protegido(sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def swagger_docs_protegido(sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    return get_swagger_ui_html(openapi_url=_OPENAPI_URL, title=f"{app.title} - Swagger UI")


@app.get("/redoc", include_in_schema=False)
def redoc_protegido(sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    return get_redoc_html(openapi_url=_OPENAPI_URL, title=f"{app.title} - ReDoc")

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
app.include_router(course_router)
app.include_router(review_router)


class ProdutoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    preco: float = Field(default=0.0, ge=0)
    quantidade: int = Field(default=0, ge=0)
    categoria: Optional[str] = None
    custo: float = Field(default=0.0, ge=0)
    lucro: float = 0.0
    estoque_minimo: int = Field(default=0, ge=0)


class ProdutosLotePayload(BaseModel):
    produtos: list[ProdutoIn] = Field(default_factory=list)


async def _expirar_pedidos_periodicamente():
    """Cancela pedidos pendentes vencidos e devolve a reserva de estoque, mesmo
    sem ninguém consultar a API no momento (antes isso só acontecia sob demanda
    em GET /api/pedidos)."""
    while True:
        try:
            with conectar() as conn:
                expirar_pedidos_pendentes(conn)
        except Exception as exc:
            print(f"[API] Aviso: varredura de expiração de pedidos falhou: {exc}")
        await asyncio.sleep(60)


def garantir_admin_api():
    senha_admin = os.environ.get("MISTICA_ADMIN_PASSWORD", "").strip()
    if not senha_admin:
        print("[API] MISTICA_ADMIN_PASSWORD não configurada; admin automático não será criado ou redefinido.")
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


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    # Endpoint público e sem autenticação (usado por monitores de uptime como
    # UptimeRobot): não deve expor caminhos de arquivo, credenciais ou outros
    # detalhes de infraestrutura interna, só a confirmação de que está online.
    return {
        "status": "online",
        "app": "Mística Presentes",
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


@app.get("/api/painel/resumo")
def painel_resumo(sessao: dict = Depends(exigir_sessao_ou_chave_api())):
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


@app.post("/api/sync/produtos-lote")
def sincronizar_produtos_lote(payload: ProdutosLotePayload, x_mistica_sync_key: str | None = Header(default=None)):
    _validar_chave_sync(x_mistica_sync_key)
    criados = 0
    atualizados = 0
    ignorados = 0
    with conectar() as conn:
        for produto in payload.produtos:
            nome = str(produto.nome or "").strip()
            codigo = str(produto.codigo_p or "").strip()
            if not nome:
                ignorados += 1
                continue
            existente = None
            if codigo:
                existente = conn.execute(
                    "SELECT id FROM produtos WHERE codigo_p=?",
                    (codigo,),
                ).fetchone()
            if not existente:
                existente = conn.execute(
                    "SELECT id FROM produtos WHERE lower(trim(nome))=lower(trim(?))",
                    (nome,),
                ).fetchone()
            if existente:
                conn.execute(
                    """
                    UPDATE produtos
                       SET codigo_p=?, nome=?, preco=?, quantidade=?, categoria=?,
                           custo=?, lucro=?, estoque_minimo=?, ativo=1
                     WHERE id=?
                    """,
                    (
                        codigo or None,
                        nome,
                        produto.preco,
                        produto.quantidade,
                        produto.categoria,
                        produto.custo,
                        produto.lucro,
                        produto.estoque_minimo,
                        existente["id"],
                    ),
                )
                atualizados += 1
            else:
                conn.execute(
                    """
                    INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, ativo)
                    VALUES (?,?,?,?,?,?,?,?,1)
                    """,
                    (
                        codigo or None,
                        nome,
                        produto.preco,
                        produto.quantidade,
                        produto.categoria,
                        produto.custo,
                        produto.lucro,
                        produto.estoque_minimo,
                    ),
                )
                criados += 1
    return {
        "status": "ok",
        "criados": criados,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "total": criados + atualizados,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


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
def listar_clientes(
    busca: str = "",
    limite: int = Query(100, ge=1, le=500),
    x_mistica_api_key: str | None = Header(default=None),
):
    validar_site_api_key(x_mistica_api_key)
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


@app.get("/api/vendas")
def listar_vendas(
    limite: int = Query(100, ge=1, le=500),
    x_mistica_api_key: str | None = Header(default=None),
):
    validar_site_api_key(x_mistica_api_key)
    vendas = listar(
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
    if not vendas:
        return vendas

    ids = [int(venda["id"]) for venda in vendas if venda.get("id") is not None]
    if not ids:
        return vendas

    placeholders = ",".join("?" for _ in ids)
    itens_por_venda = {venda_id: [] for venda_id in ids}
    with conectar() as conn:
        itens = conn.execute(
            f"""
            SELECT venda_id, codigo_p, nome_p, quantidade, valor_unitario, valor_total
            FROM vendas_itens
            WHERE venda_id IN ({placeholders})
            ORDER BY id
            """,
            ids,
        ).fetchall()
        for item in itens:
            itens_por_venda.setdefault(int(item["venda_id"]), []).append(
                {
                    "codigo_p": item["codigo_p"],
                    "nome_p": item["nome_p"],
                    "quantidade": int(item["quantidade"] or 0),
                    "valor_unitario": float(item["valor_unitario"] or 0),
                    "valor_total": float(item["valor_total"] or 0),
                }
            )

    for venda in vendas:
        venda["itens"] = itens_por_venda.get(int(venda.get("id") or 0), [])
    return vendas


class EstornoVendaIn(BaseModel):
    usuario: str = "Admin"
    observacao: Optional[str] = None


@app.post("/api/vendas/{venda_id}/estornar")
def estornar_venda(venda_id: int, payload: EstornoVendaIn | None = None, x_mistica_api_key: str | None = Header(default=None)):
    """Cancela uma venda de caixa já registrada no banco, devolvendo o estoque dos
    itens vendidos. Equivalente ao cancelamento com reposição que os pedidos do
    site já tinham (ver backend/order_status_routes.py::cancelar_com_reposicao),
    agora disponível também para vendas."""
    validar_site_api_key(x_mistica_api_key)
    payload = payload or EstornoVendaIn()
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        venda = conn.execute("SELECT id, status FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Venda não encontrada")
        ja_cancelada = str(venda["status"] or "").lower().startswith("cancel")
        if not ja_cancelada:
            itens = conn.execute(
                "SELECT codigo_p, nome_p, quantidade FROM vendas_itens WHERE venda_id=? ORDER BY id ASC",
                (venda_id,),
            ).fetchall()
            for item in itens:
                quantidade = int(item["quantidade"] or 0)
                codigo = item["codigo_p"]
                if quantidade <= 0 or not codigo:
                    continue
                conn.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE codigo_p=?", (quantidade, codigo))
        conn.execute("UPDATE vendas SET status='Cancelado' WHERE id=?", (venda_id,))
        registrar_auditoria(conn, "venda", venda_id, "estornar", payload.usuario, antes={"status": venda["status"]}, depois={"status": "Cancelado", "ja_cancelada": ja_cancelada})
        conn.commit()
    return {
        "ok": True,
        "venda_id": venda_id,
        "status": "Cancelado",
        "ja_cancelada": ja_cancelada,
        "usuario": payload.usuario,
        "observacao": payload.observacao,
        "data_hora": agora,
    }


def _intervalo_vendas_hoje_backend(agora=None):
    from datetime import time, timedelta

    agora = agora or datetime.now()
    fechamento = time(23, 0, 0)
    inicio = datetime.combine(agora.date(), time.min)
    if agora.time() >= fechamento:
        inicio = datetime.combine(agora.date(), fechamento)
        fim = datetime.combine((inicio + timedelta(days=1)).date(), fechamento)
        dia_ref = agora.date() + timedelta(days=1)
    else:
        fim = datetime.combine(inicio.date(), fechamento)
        dia_ref = agora.date()
    return (
        inicio.strftime("%Y-%m-%d %H:%M:%S"),
        fim.strftime("%Y-%m-%d %H:%M:%S"),
        dia_ref.strftime("%d/%m/%Y"),
    )


def _anexar_itens_vendas(vendas: list[dict]) -> list[dict]:
    ids = [int(venda["id"]) for venda in vendas if venda.get("id") is not None]
    if not ids:
        return vendas

    placeholders = ",".join("?" for _ in ids)
    itens_por_venda = {venda_id: [] for venda_id in ids}
    with conectar() as conn:
        itens = conn.execute(
            f"""
            SELECT venda_id, codigo_p, nome_p, quantidade, valor_unitario, valor_total
            FROM vendas_itens
            WHERE venda_id IN ({placeholders})
            ORDER BY id
            """,
            ids,
        ).fetchall()
        for item in itens:
            itens_por_venda.setdefault(int(item["venda_id"]), []).append(
                {
                    "codigo_p": item["codigo_p"],
                    "nome_p": item["nome_p"],
                    "quantidade": int(item["quantidade"] or 0),
                    "valor_unitario": float(item["valor_unitario"] or 0),
                    "valor_total": float(item["valor_total"] or 0),
                }
            )

    for venda in vendas:
        venda["itens"] = itens_por_venda.get(int(venda.get("id") or 0), [])
    return vendas


@app.get("/api/painel/dashboard")
def painel_dashboard(meta_mes: float = Query(1500.0, ge=0), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    inicio_hoje, fim_hoje, dia_operacional = _intervalo_vendas_hoje_backend()
    mes = datetime.now().strftime("/%m/%Y")
    with conectar() as conn:
        vendas_hoje = conn.execute(
            """
            SELECT COALESCE(SUM(total_final),0) AS total
            FROM vendas
            WHERE COALESCE(status,'Concluído') != 'Cancelado'
              AND (
                  COALESCE(dia_operacional,'') = ?
                  OR (datetime(data_iso) >= datetime(?) AND datetime(data_iso) < datetime(?))
              )
            """,
            (dia_operacional, inicio_hoje, fim_hoje),
        ).fetchone()["total"] or 0.0
        vendas_mes = conn.execute(
            """
            SELECT COALESCE(SUM(total_final),0) AS total
            FROM vendas
            WHERE COALESCE(status,'Concluído') != 'Cancelado'
              AND (COALESCE(data_venda,'') LIKE ? OR COALESCE(data_iso,'') LIKE ?)
            """,
            (f"%{mes}%", f"%{mes}%"),
        ).fetchone()["total"] or 0.0
        qtd_vendas_mes = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM vendas
            WHERE COALESCE(status,'Concluído') != 'Cancelado'
              AND (COALESCE(data_venda,'') LIKE ? OR COALESCE(data_iso,'') LIKE ?)
            """,
            (f"%{mes}%", f"%{mes}%"),
        ).fetchone()["total"] or 0
        produto_mais_vendido = conn.execute(
            """
            SELECT vi.nome_p AS nome, SUM(vi.quantidade) AS quantidade
            FROM vendas_itens vi
            JOIN vendas v ON v.id = vi.venda_id
            WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
              AND (COALESCE(v.data_venda,'') LIKE ? OR COALESCE(v.data_iso,'') LIKE ?)
            GROUP BY vi.nome_p
            ORDER BY quantidade DESC
            LIMIT 1
            """,
            (f"%{mes}%", f"%{mes}%"),
        ).fetchone()
        avaliacoes_loja = conn.execute(
            "SELECT COUNT(*) AS total, AVG(nota) AS media FROM avaliacoes_produtos WHERE COALESCE(aprovado,1)=1"
        ).fetchone()
        vendas_do_dia = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem_sync, local_id
                FROM vendas
                WHERE COALESCE(status,'Concluído') != 'Cancelado'
                  AND (
                      COALESCE(dia_operacional,'') = ?
                      OR (datetime(data_iso) >= datetime(?) AND datetime(data_iso) < datetime(?))
                  )
                ORDER BY id DESC
                LIMIT 300
                """,
                (dia_operacional, inicio_hoje, fim_hoje),
            ).fetchall()
        ]

    falta_meta = max(float(meta_mes or 0) - float(vendas_mes or 0), 0.0)
    return {
        "vendas_hoje": float(vendas_hoje or 0),
        "vendas_mes": float(vendas_mes or 0),
        "meta_mes": float(meta_mes or 0),
        "falta_meta": falta_meta,
        "meta_completa": falta_meta <= 0,
        "ticket_medio_mes": round(float(vendas_mes or 0) / qtd_vendas_mes, 2) if qtd_vendas_mes else 0.0,
        "produto_mais_vendido_mes": produto_mais_vendido["nome"] if produto_mais_vendido else None,
        "produto_mais_vendido_qtd": produto_mais_vendido["quantidade"] if produto_mais_vendido else 0,
        "avaliacoes_total": avaliacoes_loja["total"] or 0,
        "avaliacoes_media": round(avaliacoes_loja["media"], 1) if avaliacoes_loja["media"] else 0.0,
        "dia_operacional": dia_operacional,
        "inicio_vendas_hoje": inicio_hoje,
        "fim_vendas_hoje": fim_hoje,
        "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        "vendas_do_dia": _anexar_itens_vendas(vendas_do_dia),
    }


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
