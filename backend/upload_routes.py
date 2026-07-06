from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

router = APIRouter(prefix="/api", tags=["uploads"])

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads" / "produtos"
AUDIO_DIR = BASE_DIR / "uploads" / "musicas"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_AUDIO_BYTES = 18 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip()
    if not chave:
        print("[API] Aviso: MISTICA_SITE_API_KEY não configurada. Upload em modo desenvolvimento.")
        return
    if chave_recebida != chave:
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def limpar_nome(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return base.strip("-")[:60] or "arquivo"


@router.post("/uploads/produtos")
async def upload_imagem_produto(
    arquivo: UploadFile = File(...),
    produto_id: str = "produto",
    x_mistica_api_key: str | None = Header(default=None),
):
    validar_site_api_key(x_mistica_api_key)

    content_type = arquivo.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Formato inválido. Use JPG, PNG ou WEBP.")

    data = await arquivo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Imagem muito grande. Limite: 4 MB.")

    ext = ALLOWED_CONTENT_TYPES[content_type]
    nome = f"{limpar_nome(produto_id)}-{uuid4().hex[:10]}{ext}"
    destino = UPLOAD_DIR / nome
    destino.write_bytes(data)

    return {
        "ok": True,
        "filename": nome,
        "content_type": content_type,
        "size_bytes": len(data),
        "url": f"/uploads/produtos/{nome}",
    }


@router.post("/uploads/musicas")
async def upload_musica_ambiente(
    arquivo: UploadFile = File(...),
    nome_base: str = "ambiente-xamanico",
    x_mistica_api_key: str | None = Header(default=None),
):
    validar_site_api_key(x_mistica_api_key)

    content_type = arquivo.content_type or ""
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail="Formato inválido. Use MP3, WAV, OGG ou WEBM.")

    data = await arquivo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Áudio muito grande. Limite: 18 MB.")

    ext = ALLOWED_AUDIO_TYPES[content_type]
    nome = f"{limpar_nome(nome_base)}-{uuid4().hex[:10]}{ext}"
    destino = AUDIO_DIR / nome
    destino.write_bytes(data)

    return {
        "ok": True,
        "filename": nome,
        "content_type": content_type,
        "size_bytes": len(data),
        "url": f"/uploads/musicas/{nome}",
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/uploads/musicas")
def listar_musicas_ambiente():
    musicas = []
    if AUDIO_DIR.exists():
        for arquivo in sorted(AUDIO_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not arquivo.is_file() or arquivo.suffix.lower() not in {".mp3", ".wav", ".ogg", ".webm"}:
                continue
            stat = arquivo.stat()
            musicas.append(
                {
                    "filename": arquivo.name,
                    "url": f"/uploads/musicas/{arquivo.name}",
                    "size_bytes": stat.st_size,
                    "modificado_em": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
    return {
        "ok": True,
        "musicas": musicas[:30],
        "total": len(musicas),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
