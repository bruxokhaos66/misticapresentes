from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api", tags=["avaliacoes"])
limitar_criacao_avaliacao = limitar_requisicoes("criar_avaliacao", limite=5, janela_segundos=300)


class AvaliacaoIn(BaseModel):
    nome_cliente: str = Field(min_length=2, max_length=60)
    nota: int = Field(ge=1, le=5)
    comentario: str = Field(default="", max_length=500)


def _ip_hash(request: Request) -> str:
    encaminhado = request.headers.get("x-forwarded-for", "")
    ip = encaminhado.split(",")[0].strip() or (request.client.host if request.client else "")
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


@router.get("/produtos/{produto_id}/avaliacoes")
def listar_avaliacoes(produto_id: int):
    with conectar() as conn:
        linhas = conn.execute(
            """
            SELECT id, nome_cliente, nota, comentario, data_hora
            FROM avaliacoes_produtos
            WHERE produto_id = ? AND COALESCE(aprovado, 1) = 1
            ORDER BY data_hora DESC
            LIMIT 100
            """,
            (produto_id,),
        ).fetchall()
        resumo = conn.execute(
            """
            SELECT COUNT(*) AS total, AVG(nota) AS media
            FROM avaliacoes_produtos
            WHERE produto_id = ? AND COALESCE(aprovado, 1) = 1
            """,
            (produto_id,),
        ).fetchone()
    return {
        "avaliacoes": [dict(linha) for linha in linhas],
        "total": resumo["total"] or 0,
        "media": round(resumo["media"], 1) if resumo["media"] else 0,
    }


@router.post("/produtos/{produto_id}/avaliacoes", dependencies=[Depends(limitar_criacao_avaliacao)])
def criar_avaliacao(produto_id: int, avaliacao: AvaliacaoIn, request: Request):
    with conectar() as conn:
        produto = conn.execute(
            "SELECT id FROM produtos WHERE id = ? AND COALESCE(ativo,1)=1",
            (produto_id,),
        ).fetchone()
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado.")
        conn.execute(
            """
            INSERT INTO avaliacoes_produtos (produto_id, nome_cliente, nota, comentario, data_hora, aprovado, ip_hash)
            VALUES (?,?,?,?,?,1,?)
            """,
            (
                produto_id,
                avaliacao.nome_cliente.strip(),
                avaliacao.nota,
                avaliacao.comentario.strip(),
                datetime.now().isoformat(timespec="seconds"),
                _ip_hash(request),
            ),
        )
    return {"ok": True}
