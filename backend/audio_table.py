"""Migração única: tira as músicas de ambiente que ainda estejam guardadas
como BLOB em `site_musicas_ambiente` e grava cada uma como arquivo em
`backend/uploads/musicas/`, removendo a tabela do SQLite em seguida.

Guardar áudio (até 30MB por faixa) como BLOB inflava o arquivo do banco e
tornava backups/cópias do SQLite muito mais lentos que o necessário — o
disco de uploads já é o destino padrão desde upload_routes.py e cobre o
mesmo propósito sem esse custo.
"""

from __future__ import annotations

from pathlib import Path

from backend.database import conectar
from backend.logging_config import get_logger

logger = get_logger(__name__)

AUDIO_DIR = Path(__file__).resolve().parent / "uploads" / "musicas"


def migrar_musicas_blob_para_arquivo() -> None:
    with conectar() as conn:
        existe = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='site_musicas_ambiente'"
        ).fetchone()
        if not existe:
            return

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        linhas = conn.execute("SELECT id, filename, dados FROM site_musicas_ambiente").fetchall()
        migradas = 0
        for linha in linhas:
            nome = linha["filename"]
            dados = linha["dados"]
            if not nome or dados is None:
                continue
            destino = AUDIO_DIR / Path(nome).name
            if not destino.exists():
                destino.write_bytes(dados)
                migradas += 1

        conn.execute("DROP TABLE site_musicas_ambiente")
        conn.commit()
        logger.info(
            "migração de músicas BLOB→arquivo concluída",
            extra={"evento": "migracao_musicas_blob", "linhas": len(linhas), "arquivos_gravados": migradas},
        )
