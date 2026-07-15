import asyncio
import contextlib
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.aluno_auth import _validar_sessao_aluno, aluno_tem_acesso, router as aluno_router
from backend.audio_table import migrar_musicas_blob_para_arquivo
from backend.audit import registrar_auditoria
from backend.backup_routes import router as backup_router
from backend.campaign_routes import router as campaign_router
from backend.course_routes import router as course_router
from backend.lms_routes import router as lms_router
from backend.lms_admin_routes import router as lms_admin_router
from backend.lms_content_xamanismo import (
    instalar_conteudo_xamanismo,
    instalar_conteudo_modulo2_xamanismo,
    instalar_capas_modulo1_xamanismo,
    instalar_capas_v2_modulo1_xamanismo,
    instalar_capas_modulo2_xamanismo,
    instalar_capas_modulos_xamanismo,
    instalar_capa_foto_aula_origem_termo_xama,
    instalar_legenda_imagem_exclusiva_xamanismo,
    instalar_capa_loading_eager_xamanismo,
)
from backend.database import conectar, executar, listar, obter
from backend.infra_diagnostics import banco_acessivel, disco_diretorio_disponivel
from backend.logging_config import configurar_logging, get_logger
from backend.order_status_routes import expirar_pedidos_pendentes, router as order_status_router
from backend.panel_sessions import exigir_sessao_ou_chave_api, validar_sessao
from backend.payment_routes import router as payment_router
from backend.api_security import APP_ENV, ORIGENS_PERMITIDAS, validar_site_api_key as validar_chave_api
from backend.product_routes import router as product_router, validar_site_api_key
from backend.review_routes import router as review_router
from backend.upload_routes import CURSOS_DIR, router as upload_router
from backend.user_sync_routes import router as user_sync_router
from backend.site_stock_routes import router as site_stock_router
from backend.system_status_routes import router as system_status_router
from config import hash_password_pbkdf2
from database.migrations import init_db
from database.backup import backup_habilitado, scheduler_backup
from database.backup_remote import shutdown_remote_uploads, start_remote_uploads

configurar_logging()
logger = get_logger(__name__)


def _verificar_persistencia_banco() -> None:
    """Registra no startup se o banco está num caminho persistente ou efêmero.

    Serve para confirmar objetivamente, nos logs do Render, o item mais crítico
    da auditoria: no plano Free (sem Persistent Disk) o SQLite volta vazio a
    cada redeploy/sleep. Se MISTICA_DB_PATH não estiver configurada apontando
    para um disco montado (ex.: /data), este aviso alto sinaliza o risco.

    O log nunca inclui o caminho (nem o diretório) configurado -- só o
    booleano `persistente`, para nunca vazar estrutura de disco do servidor.
    """
    from config import DB_PATH

    db_path = str(DB_PATH)
    env_configurada = bool(
        os.environ.get("MISTICA_DB_PATH", "").strip() or os.environ.get("DATABASE_PATH", "").strip()
    )
    parece_persistente = env_configurada and db_path.startswith(("/data", "/var/data", "/mnt"))
    if parece_persistente:
        logger.info(
            "banco em caminho persistente",
            extra={"evento": "startup_persistencia", "persistente": True},
        )
    else:
        logger.warning(
            "ATENCAO: banco pode estar em disco EFEMERO (dados podem ser perdidos em redeploy/sleep). "
            "Configure MISTICA_DB_PATH para um Persistent Disk.",
            extra={"evento": "startup_persistencia", "persistente": False},
        )


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    inicio = datetime.now()
    init_db()
    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        instalar_conteudo_modulo2_xamanismo(conn)
        instalar_capas_modulo1_xamanismo(conn)
        instalar_capas_v2_modulo1_xamanismo(conn)
        instalar_capas_modulo2_xamanismo(conn)
        instalar_capas_modulos_xamanismo(conn)
        instalar_capa_foto_aula_origem_termo_xama(conn)
        instalar_legenda_imagem_exclusiva_xamanismo(conn)
        instalar_capa_loading_eager_xamanismo(conn)
    _verificar_persistencia_banco()
    migrar_musicas_blob_para_arquivo()
    garantir_admin_api()
    duracao_ms = (datetime.now() - inicio).total_seconds() * 1000
    logger.info(
        "inicializacao concluida",
        extra={
            "evento": "startup_concluido",
            "versao": app.version,
            "ambiente": APP_ENV,
            "banco_ok": banco_acessivel(),
            "disco_ok": disco_diretorio_disponivel(),
            "duracao_ms": round(duracao_ms, 1),
        },
    )
    tarefa_expiracao = asyncio.create_task(_expirar_pedidos_periodicamente())
    tarefa_backup = asyncio.create_task(scheduler_backup()) if backup_habilitado() else None
    start_remote_uploads()
    try:
        yield
    finally:
        tarefas = [tarefa_expiracao]
        if tarefa_backup is not None:
            tarefas.append(tarefa_backup)
        for tarefa in tarefas:
            tarefa.cancel()
        for tarefa in tarefas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa
        uploads_finalizados = await asyncio.to_thread(shutdown_remote_uploads, 30.0)
        if not uploads_finalizados:
            logger.warning(
                "encerramento prosseguiu com upload remoto ainda ativo",
                extra={"evento": "backup_remoto_shutdown_timeout"},
            )


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
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Mistica-Api-Key", "X-Mistica-Sync-Key", "Idempotency-Key"],
)


@app.middleware("http")
async def cabecalhos_seguranca(request, call_next):
    """Defesa em profundidade: adiciona cabeçalhos de segurança a todas as
    respostas da API. As respostas são JSON/arquivos (não HTML de app), então
    estes headers têm baixo risco de quebrar o front e melhoram a postura de
    segurança (sniffing, clickjacking, vazamento de referer). HSTS só é
    enviado sob HTTPS, para não atrapalhar desenvolvimento local em HTTP."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # cross-origin (não same-site): a API serve imagens de produto, áudio de
    # ambiente e prévias públicas que o site carrega legitimamente de outra
    # origem; same-site bloquearia esse carregamento.
    response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
# Só produtos e músicas (conteúdo público da loja) vão para o mount estático
# sem autenticação. Cursos pagos NÃO entram aqui -- ver
# servir_material_curso_protegido abaixo, que confere sessão de aluno com
# acesso liberado (ou sessão/chave de admin) antes de devolver o arquivo.
# Antes, tudo em backend/uploads/ (incluindo cursos/) era servido por um
# único StaticFiles público, então quem tivesse a URL do material -- que
# pode vazar por histórico do navegador, log de rede ou print -- baixava o
# conteúdo pago sem ter comprado.
(UPLOADS_DIR / "produtos").mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "musicas").mkdir(parents=True, exist_ok=True)
app.mount("/uploads/produtos", StaticFiles(directory=str(UPLOADS_DIR / "produtos")), name="uploads-produtos")
app.mount("/uploads/musicas", StaticFiles(directory=str(UPLOADS_DIR / "musicas")), name="uploads-musicas")


@app.get("/uploads/cursos/{filename}")
def servir_material_curso_protegido(
    filename: str,
    mistica_painel_sessao: str | None = Cookie(default=None),
    mistica_aluno_sessao: str | None = Cookie(default=None),
    x_mistica_api_key: str | None = Header(default=None),
):
    nome = Path(filename).name
    caminho = CURSOS_DIR / nome
    if not caminho.exists() or not caminho.is_file():
        raise HTTPException(status_code=404, detail="Material não encontrado.")

    if validar_sessao(mistica_painel_sessao):
        return FileResponse(caminho)

    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if chave and x_mistica_api_key and secrets.compare_digest(str(x_mistica_api_key), chave):
        return FileResponse(caminho)

    sessao_aluno = _validar_sessao_aluno(mistica_aluno_sessao)
    if not sessao_aluno:
        raise HTTPException(status_code=401, detail="Faça login para acessar este material.")

    url_arquivo = f"/uploads/cursos/{nome}"
    with conectar() as conn:
        material = conn.execute(
            "SELECT categoria FROM cursos_materiais WHERE url=?", (url_arquivo,)
        ).fetchone()
        tem_acesso = bool(material) and aluno_tem_acesso(conn, aluno_id=sessao_aluno["aluno_id"], slug=material["categoria"])
    if not tem_acesso:
        raise HTTPException(status_code=403, detail="Você ainda não tem acesso a este curso.")
    return FileResponse(caminho)


app.include_router(product_router)
app.include_router(user_sync_router)
app.include_router(site_stock_router)
app.include_router(order_status_router)
app.include_router(payment_router)
app.include_router(upload_router)
app.include_router(system_status_router)
app.include_router(backup_router)
app.include_router(course_router)
app.include_router(aluno_router)
app.include_router(review_router)
app.include_router(campaign_router)
app.include_router(lms_router)
app.include_router(lms_admin_router)


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
            logger.warning("varredura de expiração de pedidos falhou", extra={"evento": "expiracao_pedidos", "erro": str(exc)})
        await asyncio.sleep(60)


def garantir_admin_api():
    senha_admin = os.environ.get("MISTICA_ADMIN_PASSWORD", "").strip()
    if not senha_admin:
        logger.info(
            "MISTICA_ADMIN_PASSWORD não configurada; admin automático não será criado ou redefinido.",
            extra={"evento": "startup_aviso"},
        )
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


@app.get("/")
def raiz():
    return {
        "app": "Mística Presentes API",
        "status": "online",
        "docs": "/docs",
        "health": "/api/health",
    }


_BUILD_ID_SEGURO_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _build_id_sanitizado() -> str:
    """Identificador curto e seguro do build, sem branch, sem usuário, sem
    caminho: só o SHA curto de MISTICA_BUILD_ID/RENDER_GIT_COMMIT, filtrado
    para conter apenas caracteres inofensivos e truncado a 12 posições."""
    bruto = (os.environ.get("MISTICA_BUILD_ID", "").strip() or os.environ.get("RENDER_GIT_COMMIT", "").strip())[:12]
    limpo = _BUILD_ID_SEGURO_RE.sub("", bruto)
    return limpo or "unknown"


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    # Endpoint público e sem autenticação (usado por monitores de uptime como
    # UptimeRobot): resposta mínima, sem caminhos, hostnames, variáveis de
    # ambiente, versões de dependências ou mensagens internas de exceção. A
    # checagem de disco aqui é só leitura de permissão (sem criar/remover
    # arquivo) para não gerar I/O a cada chamada de monitor externo.
    banco_ok = banco_acessivel()
    disco_ok = disco_diretorio_disponivel()
    saudavel = banco_ok and disco_ok
    corpo = {
        "status": "ok" if saudavel else "error",
        "service": "mistica-api",
        "version": app.version,
        "database": "available" if banco_ok else "unavailable",
    }
    if not saudavel:
        return JSONResponse(status_code=503, content=corpo)
    return corpo


@app.api_route("/api/version", methods=["GET", "HEAD"])
def versao():
    # Público como /api/health: só dados controlados por variável de
    # ambiente própria da aplicação -- nunca branch, usuário de build, URL
    # interna ou lista de dependências. Nenhum comando git é executado por
    # requisição; o identificador de build vem só de env var, sanitizado.
    return {
        "app": "Mística Presentes",
        "version": app.version,
        "build": _build_id_sanitizado(),
        "release_date": os.environ.get("MISTICA_BUILD_DATE", "").strip() or None,
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


@app.post("/api/sync/produtos-lote")
def sincronizar_produtos_lote(payload: ProdutosLotePayload, x_mistica_sync_key: str | None = Header(default=None)):
    validar_chave_api(x_mistica_sync_key, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir sincronização.")
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
    """Rota pública: não inclui custo, lucro nem estoque mínimo (dados internos)."""
    produto = obter(
        """
        SELECT id, codigo_p, nome, preco, quantidade, categoria
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
def painel_dashboard(response: Response, meta_mes: float = Query(1500.0, ge=0), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
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
