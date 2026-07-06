from __future__ import annotations

import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from config import BACKUP_DIR, DB_PATH

router = APIRouter(prefix="/api", tags=["backup"])


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir acesso ao backup.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


@router.post("/backup/manual")
def criar_backup_manual(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    origem = Path(DB_PATH)
    destino_dir = Path(BACKUP_DIR)

    if not origem.exists():
        raise HTTPException(status_code=404, detail="Arquivo do banco de dados não encontrado")

    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = destino_dir / f"mistica_backup_{timestamp}.db"
        shutil.copy2(origem, destino)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao criar backup: {exc}") from exc

    return {
        "status": "ok",
        "mensagem": "Backup manual criado com sucesso.",
        "arquivo": str(destino),
        "tamanho_bytes": destino.stat().st_size,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/backup/status")
def status_backup_manual(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    origem = Path(DB_PATH)
    destino_dir = Path(BACKUP_DIR)
    backups = []

    if destino_dir.exists():
        arquivos = sorted(destino_dir.glob("mistica_backup_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for arquivo in arquivos[:10]:
            backups.append(
                {
                    "arquivo": str(arquivo),
                    "nome": arquivo.name,
                    "tamanho_bytes": arquivo.stat().st_size,
                    "modificado_em": datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(timespec="seconds"),
                }
            )

    return {
        "status": "ok",
        "banco_existe": origem.exists(),
        "backup_dir": str(destino_dir),
        "backup_dir_existe": destino_dir.exists(),
        "ultimos_backups": backups,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
