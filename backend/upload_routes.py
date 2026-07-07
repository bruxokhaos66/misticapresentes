from __future__ import annotations

import os
import re
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from backend.database import conectar
from config import DB_PATH

router = APIRouter(prefix="/api", tags=["uploads"])

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads" / "produtos"
AUDIO_DIR = BASE_DIR / "uploads" / "musicas"
AUDIO_LINKS_FILE = AUDIO_DIR / "links-diretos.txt"
PUBLIC_SITE_KEY = "c4e9012d72c6bb42f52457c6d6ba916a"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_AUDIO_BYTES = 30 * 1024 * 1024
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
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
}
ALLOWED_AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".webm", ".m4a")


class AudioLinksIn(BaseModel):
    links: list[str] = Field(default_factory=list)


def log_tempo(etapa: str, inicio: float, detalhe: str = ""):
    duracao_ms = int((time.perf_counter() - inicio) * 1000)
    sufixo = f" | {detalhe}" if detalhe else ""
    print(f"[API][musicas] {etapa}: {duracao_ms}ms{sufixo}")


def conectar_rapido(timeout: float = 0.35):
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def validar_site_api_key(chave_recebida: str | None):
    chaves_validas = [
        os.environ.get("MISTICA_SITE_API_KEY", "").strip(),
        os.environ.get("MISTICA_SYNC_KEY", "").strip(),
        PUBLIC_SITE_KEY,
    ]
    chaves_validas = [chave for chave in chaves_validas if chave]
    if not chave_recebida:
        raise HTTPException(status_code=403, detail="Chave da API não enviada pelo site.")
    if not any(secrets.compare_digest(str(chave_recebida), chave) for chave in chaves_validas):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def limpar_nome(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return base.strip("-")[:60] or "arquivo"


def normalizar_link_audio(value: str | None) -> str:
    texto = str(value or "").strip()[:720]
    if not texto.startswith(("https://", "http://")):
        return ""
    sem_query = texto.split("?", 1)[0].lower()
    if not sem_query.endswith(ALLOWED_AUDIO_EXTENSIONS):
        return ""
    return texto


def limpar_links_audio(links: list[str]) -> list[str]:
    limpos = []
    for item in links:
        link = normalizar_link_audio(item)
        if link and link not in limpos:
            limpos.append(link)
        if len(limpos) >= 20:
            break
    return limpos


def garantir_tabela_musicas_ambiente(conn):
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_site_musicas_ambiente_criado ON site_musicas_ambiente(criado_em)")


def garantir_tabela_musicas_startup():
    inicio = time.perf_counter()
    try:
        with conectar() as conn:
            garantir_tabela_musicas_ambiente(conn)
            conn.commit()
        log_tempo("garantir_tabela", inicio, "ok")
        return None
    except Exception as exc:
        log_tempo("garantir_tabela_falhou", inicio, str(exc))
        return str(exc)


def salvar_musica_no_banco(nome: str, content_type: str, data: bytes, criado_em: str):
    inicio = time.perf_counter()
    try:
        with conectar() as conn:
            garantir_tabela_musicas_ambiente(conn)
            conn.execute(
                """
                INSERT INTO site_musicas_ambiente (filename, content_type, size_bytes, dados, criado_em)
                VALUES (?,?,?,?,?)
                """,
                (nome, content_type, len(data), data, criado_em),
            )
            conn.commit()
        log_tempo("backup_banco_ok", inicio, nome)
    except Exception as exc:
        log_tempo("backup_banco_falhou", inicio, str(exc))


def detectar_extensao_audio(arquivo: UploadFile) -> str:
    content_type = arquivo.content_type or ""
    if content_type in ALLOWED_AUDIO_TYPES:
        return ALLOWED_AUDIO_TYPES[content_type]
    filename = (arquivo.filename or "").lower()
    for ext in ALLOWED_AUDIO_EXTENSIONS:
        if filename.endswith(ext):
            return ext
    raise HTTPException(status_code=400, detail="Formato inválido. Use MP3, WAV, OGG, WEBM ou M4A.")


def media_type_por_nome(nome: str, fallback: str = "audio/mpeg") -> str:
    nome_lower = nome.lower()
    if nome_lower.endswith(".wav"):
        return "audio/wav"
    if nome_lower.endswith(".ogg"):
        return "audio/ogg"
    if nome_lower.endswith(".webm"):
        return "audio/webm"
    if nome_lower.endswith(".m4a"):
        return "audio/mp4"
    return fallback or "audio/mpeg"


def listar_musicas_arquivo_local(nomes_existentes: set[str]) -> list[dict]:
    musicas = []
    if not AUDIO_DIR.exists():
        return musicas
    for arquivo in sorted(AUDIO_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not arquivo.is_file() or arquivo.name == AUDIO_LINKS_FILE.name or arquivo.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
            continue
        if arquivo.name in nomes_existentes:
            continue
        stat = arquivo.stat()
        musicas.append(
            {
                "filename": arquivo.name,
                "url": f"/api/uploads/musicas/arquivo-local/{arquivo.name}",
                "size_bytes": stat.st_size,
                "modificado_em": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "armazenamento": "arquivo",
            }
        )
        if len(musicas) >= 30:
            break
    return musicas


def listar_musicas_banco_rapido() -> tuple[list[dict], set[str], str | None]:
    musicas = []
    nomes = set()
    erro = garantir_tabela_musicas_startup()
    if erro:
        return musicas, nomes, erro
    try:
        conn = conectar_rapido(timeout=0.35)
        try:
            rows = conn.execute(
                """
                SELECT id, filename, content_type, size_bytes, criado_em
                FROM site_musicas_ambiente
                ORDER BY id DESC
                LIMIT 30
                """
            ).fetchall()
            for row in rows:
                nomes.add(row["filename"])
                musicas.append(
                    {
                        "id": row["id"],
                        "filename": row["filename"],
                        "content_type": row["content_type"],
                        "size_bytes": row["size_bytes"],
                        "modificado_em": row["criado_em"],
                        "url": f"/api/uploads/musicas/arquivo/{row['id']}",
                        "armazenamento": "banco",
                    }
                )
        finally:
            conn.close()
    except Exception as exc:
        erro = str(exc)
    return musicas, nomes, erro


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
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(...),
    nome_base: str = "ambiente-xamanico",
    x_mistica_api_key: str | None = Header(default=None),
):
    validar_site_api_key(x_mistica_api_key)

    ext = detectar_extensao_audio(arquivo)
    data = await arquivo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Áudio muito grande. Limite: 30 MB.")

    content_type = arquivo.content_type or media_type_por_nome(arquivo.filename or "")
    nome_original = arquivo.filename or nome_base or "ambiente-xamanico"
    nome_limpo = limpar_nome(nome_original.rsplit(".", 1)[0] or nome_base)
    nome = f"{nome_limpo}-{uuid4().hex[:10]}{ext}"
    criado_em = datetime.now().isoformat(timespec="seconds")

    destino = AUDIO_DIR / nome
    destino.write_bytes(data)
    background_tasks.add_task(salvar_musica_no_banco, nome, content_type, data, criado_em)

    return {
        "ok": True,
        "filename": nome,
        "content_type": content_type,
        "size_bytes": len(data),
        "url": f"/api/uploads/musicas/arquivo-local/{nome}",
        "data_hora": criado_em,
        "armazenamento": "arquivo+backup_banco",
    }


@router.get("/uploads/musicas")
def listar_musicas_ambiente():
    inicio = time.perf_counter()
    log_tempo("inicio_listagem", inicio)

    musicas_banco, nomes_banco, erro_banco = listar_musicas_banco_rapido()
    log_tempo("consulta_banco", inicio, erro_banco or f"{len(musicas_banco)} registro(s)")

    musicas_arquivos = listar_musicas_arquivo_local(nomes_banco)
    log_tempo("consulta_arquivos", inicio, f"{len(musicas_arquivos)} arquivo(s)")

    musicas = (musicas_arquivos + musicas_banco)[:30]
    resposta = {
        "ok": True,
        "musicas": musicas,
        "total": len(musicas),
        "fonte": "arquivo+banco_rapido",
        "banco_erro": erro_banco,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
    log_tempo("fim_resposta", inicio, f"total={len(musicas)}")
    return resposta


@router.get("/uploads/musicas/arquivo-local/{filename}")
def obter_musica_local_ambiente(filename: str):
    nome = Path(filename).name
    if not nome.lower().endswith(ALLOWED_AUDIO_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Formato de música inválido.")
    arquivo = AUDIO_DIR / nome
    if not arquivo.exists() or not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Música não encontrada.")

    return Response(
        content=arquivo.read_bytes(),
        media_type=media_type_por_nome(nome),
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f"inline; filename={nome}",
        },
    )


@router.get("/uploads/musicas/arquivo/{musica_id}")
def obter_musica_ambiente(musica_id: int):
    with conectar() as conn:
        garantir_tabela_musicas_ambiente(conn)
        row = conn.execute(
            """
            SELECT filename, content_type, dados
            FROM site_musicas_ambiente
            WHERE id=?
            """,
            (musica_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Música não encontrada.")

    return Response(
        content=row["dados"],
        media_type=row["content_type"],
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f"inline; filename={row['filename']}",
        },
    )


@router.get("/uploads/musicas/links")
def listar_links_audio_ambiente():
    links = []
    if AUDIO_LINKS_FILE.exists():
        links = limpar_links_audio(AUDIO_LINKS_FILE.read_text(encoding="utf-8").splitlines())
    return {
        "ok": True,
        "links": links,
        "total": len(links),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/uploads/musicas/links")
def salvar_links_audio_ambiente(payload: AudioLinksIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    links = limpar_links_audio(payload.links)
    AUDIO_LINKS_FILE.write_text("\n".join(links), encoding="utf-8")
    return {
        "ok": True,
        "links": links,
        "total": len(links),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
