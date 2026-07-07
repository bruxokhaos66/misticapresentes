from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from backend.database import conectar
from config import API_URL, DB_PATH, OFFICIAL_DOMAIN, SERVER_URL

router = APIRouter(prefix="/api", tags=["status-sistema"])

TABELAS_PRINCIPAIS = [
    "produtos",
    "clientes",
    "vendas",
    "vendas_itens",
    "usuarios",
    "fornecedores",
    "movimentacao_estoque",
    "site_acessos",
]


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para acessar diagnóstico do sistema.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def tabela_existe(conn, nome: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone()
    return row is not None


def contar_registros(conn, nome: str) -> int | None:
    if not tabela_existe(conn, nome):
        return None
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {nome}").fetchone()
    return int(row["total"] or 0)


@router.get("/status")
def status_publico():
    return {
        "status": "online",
        "api": "mistica",
        "app": "Mística Presentes",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/diagnostico/sistema")
def status_sistema(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    db_path = Path(DB_PATH)
    tabelas = []
    erros = []

    try:
        with conectar() as conn:
            for tabela in TABELAS_PRINCIPAIS:
                total = contar_registros(conn, tabela)
                tabelas.append({"nome": tabela, "existe": total is not None, "registros": total if total is not None else 0})
    except Exception as exc:
        erros.append(str(exc))

    return {
        "status": "ok" if not erros else "verificar",
        "app": "Mística Presentes",
        "dominio": OFFICIAL_DOMAIN,
        "server_url": SERVER_URL,
        "api_url": API_URL,
        "banco": {"caminho": str(db_path), "arquivo_existe": db_path.exists(), "pasta_existe": db_path.parent.exists()},
        "tabelas": tabelas,
        "erros": erros,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
