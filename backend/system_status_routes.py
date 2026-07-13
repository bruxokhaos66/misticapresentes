from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar
from backend.infra_diagnostics import banco_acessivel, diagnostico_disco_completo
from backend.logging_config import get_logger
from config import API_URL, DB_PATH, OFFICIAL_DOMAIN, SERVER_URL

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["status-sistema"])

TABELAS_PRINCIPAIS = [
    "produtos",
    "clientes",
    "vendas",
    "vendas_itens",
    "pedidos",
    "pedidos_itens",
    "usuarios",
    "fornecedores",
    "movimentacao_estoque",
    "site_acessos",
]


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para acessar diagnóstico do sistema.")


def tabela_existe(conn, nome: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone()
    return row is not None


def contar_registros(conn, nome: str) -> int | None:
    if not tabela_existe(conn, nome):
        return None
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {nome}").fetchone()
    return int(row["total"] or 0)


@router.api_route("/status", methods=["GET", "HEAD"])
def status_publico():
    # Rota pública e sem autenticação (mesma superfície de /api/health): não
    # deve expor contagem de clientes, vendas ou qualquer outro dado de
    # negócio. Esses números continuam disponíveis, mas só com sessão de
    # painel ou chave de API, em /api/painel/resumo.
    return {
        "status": "online",
        "api": "mistica",
        "app": "Mística Presentes",
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/diagnostico/sistema")
def status_sistema(x_mistica_api_key: str | None = Header(default=None)):
    # A autenticação é a primeira coisa verificada: nenhuma checagem de
    # banco/disco roda antes disso, e sem chave válida o chamador só recebe
    # o erro genérico de autenticação (nunca dados de diagnóstico).
    validar_site_api_key(x_mistica_api_key)

    db_path = Path(DB_PATH)
    tabelas = []
    teve_erro = False

    try:
        with conectar() as conn:
            for tabela in TABELAS_PRINCIPAIS:
                try:
                    total = contar_registros(conn, tabela)
                    tabelas.append({"nome": tabela, "existe": total is not None, "registros": total if total is not None else 0})
                except Exception:
                    # O detalhe da exceção (que pode incluir texto de erro do
                    # SQLite) só vai para o log interno; a resposta ao
                    # cliente nunca inclui stack trace ou mensagem crua.
                    logger.exception("falha ao contar registros de tabela no diagnostico", extra={"tabela": tabela})
                    teve_erro = True
    except Exception:
        logger.exception("falha ao conectar ao banco no diagnostico")
        teve_erro = True

    disco = diagnostico_disco_completo()

    return {
        "status": "ok" if (not teve_erro and disco["acessivel"] and disco["classificacao"] != "critico") else "verificar",
        "app": "Mística Presentes",
        "dominio": OFFICIAL_DOMAIN,
        "server_url": SERVER_URL,
        "api_url": API_URL,
        # Nunca o caminho absoluto -- só booleanos que confirmam se o
        # arquivo/pasta existem, úteis para o painel sem revelar estrutura
        # de disco do servidor.
        "banco": {
            "acessivel": banco_acessivel(),
            "arquivo_existe": db_path.exists(),
            "pasta_existe": db_path.parent.exists(),
        },
        "disco": disco,
        "tabelas": tabelas,
        "teve_erro": teve_erro,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
