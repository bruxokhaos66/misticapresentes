from __future__ import annotations

import json
from datetime import datetime


def resposta_idempotente_existente(conn, escopo: str, chave: str | None):
    """Se a mesma Idempotency-Key já foi usada neste escopo, devolve a resposta
    salva da primeira vez (para a requisição repetida não duplicar o efeito).
    Sem chave, a checagem é ignorada (mantém compatibilidade com clientes que
    ainda não enviam o header)."""
    if not chave:
        return None
    row = conn.execute(
        "SELECT resposta FROM idempotency_keys WHERE escopo=? AND chave=?",
        (escopo, chave),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["resposta"])
    except Exception:
        return None


def salvar_resposta_idempotente(conn, escopo: str, chave: str | None, resposta: dict):
    if not chave:
        return
    conn.execute(
        "INSERT OR IGNORE INTO idempotency_keys (escopo, chave, resposta, criado_em) VALUES (?,?,?,?)",
        (escopo, chave, json.dumps(resposta, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
    )
