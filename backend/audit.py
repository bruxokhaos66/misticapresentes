from __future__ import annotations

import json
from datetime import datetime


def registrar_auditoria(conn, entidade: str, entidade_id, acao: str, usuario: str | None = None, antes=None, depois=None):
    """Grava uma linha no log de auditoria unificado (quem mudou o quê, quando).

    Complementa (não substitui) os históricos específicos já existentes
    (movimentacao_estoque, historico_precos, pedido_status_log)."""
    conn.execute(
        """
        INSERT INTO audit_log (entidade, entidade_id, acao, usuario, dados_antes, dados_depois, data_hora)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            entidade,
            str(entidade_id) if entidade_id is not None else None,
            acao,
            usuario or "Sistema",
            json.dumps(antes, ensure_ascii=False, default=str) if antes is not None else None,
            json.dumps(depois, ensure_ascii=False, default=str) if depois is not None else None,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
