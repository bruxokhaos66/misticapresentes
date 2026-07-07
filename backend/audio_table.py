from __future__ import annotations

from backend.database import conectar


def garantir_tabela_audio_ambiente():
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS site_musicas_ambiente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                dados BLOB NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_site_musicas_ambiente_criado ON site_musicas_ambiente(criado_em)"
        )
        conn.commit()
