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
from backend.drive_storage import drive_configured, upload_bytes_to_drive
from config import DB_PATH

router = APIRouter(prefix="/api", tags=["uploads"])

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads" / "produtos"
AUDIO_DIR = BASE_DIR / "uploads" / "musicas"
AUDIO_LINKS_FILE = AUDIO_DIR / "links-diretos.txt"
CURSOS_DIR = BASE_DIR / "uploads" / "cursos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
CURSOS_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_AUDIO_BYTES = 30 * 1024 * 1024
MAX_CURSO_DOC_BYTES = 20 * 1024 * 1024
MAX_CURSO_VIDEO_BYTES = 150 * 1024 * 1024
ALLOWED_CURSO_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
ALLOWED_CURSO_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
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
_MUSICAS_CACHE = {"at": 0.0, "data": None}


class AudioLinksIn(BaseModel):
    links: list[str] = Field(default_factory=list)


def log_tempo(etapa: str, inicio: float, detalhe: str = ""):
    duracao_ms = int((time.perf_counter() - inicio) * 1000)
    sufixo = f" | {detalhe}" if detalhe else ""
    print(f"[API][musicas] {etapa}: {duracao_ms}ms{sufixo}")


def conectar_rapido(timeout: float = 0.08):
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def validar_site_api_key(chave_recebida: str | None):
    chaves_validas = [os.environ.get("MISTICA_SITE_API_KEY", "").strip(), os.environ.get("MISTICA_SYNC_KEY", "").strip()]
    chaves_validas = [chave for chave in chaves_validas if chave]
    if not chaves_validas:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir upload pela API.")
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
    if "drive.google.com/uc" in texto or "drive.google.com/file" in texto:
        return texto
    if not sem_query.endswith(ALLOWED_AUDIO_EXTENSIONS):
        return ""
    return texto


def limpar_links_audio(links: list[str]) -> list[str]:
    limpos = []
    for item in links:
        link = normalizar_link_audio(item)
        if link and link not in limpos:
            limpos.append(link)
        if len(limpos) >= 30:
            break
    return limpos


def adicionar_link_audio_persistente(link: str):
    if not normalizar_link_audio(link):
        return
    links = []
    if AUDIO_LINKS_FILE.exists():
        links = AUDIO_LINKS_FILE.read_text(encoding="utf-8").splitlines()
    limpos = limpar_links_audio([link] + links)
    AUDIO_LINKS_FILE.write_text("\n".join(limpos), encoding="utf-8")


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


def listar_musicas_links() -> list[dict]:
    if not AUDIO_LINKS_FILE.exists():
        return []
    links = limpar_links_audio(AUDIO_LINKS_FILE.read_text(encoding="utf-8").splitlines())
    return [
        {"filename": f"Música Drive {idx}", "url": link, "size_bytes": 0, "modificado_em": "", "armazenamento": "google_drive"}
        for idx, link in enumerate(links, start=1)
    ]


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
        musicas.append({"filename": arquivo.name, "url": f"/api/uploads/musicas/arquivo-local/{arquivo.name}", "size_bytes": stat.st_size, "modificado_em": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"), "armazenamento": "arquivo"})
        if len(musicas) >= 30:
            break
    return musicas


def listar_musicas_banco_rapido() -> tuple[list[dict], set[str], str | None]:
    musicas = []
    nomes = set()
    try:
        conn = conectar_rapido(timeout=0.08)
        try:
            rows = conn.execute("SELECT id, filename, content_type, size_bytes, criado_em FROM site_musicas_ambiente ORDER BY id DESC LIMIT 30").fetchall()
            for row in rows:
                nomes.add(row["filename"])
                musicas.append({"id": row["id"], "filename": row["filename"], "content_type": row["content_type"], "size_bytes": row["size_bytes"], "modificado_em": row["criado_em"], "url": f"/api/uploads/musicas/arquivo/{row['id']}", "armazenamento": "banco"})
        finally:
            conn.close()
    except Exception as exc:
        return musicas, nomes, str(exc)
    return musicas, nomes, None


@router.post("/uploads/produtos")
async def upload_imagem_produto(arquivo: UploadFile = File(...), produto_id: str = "produto", x_mistica_api_key: str | None = Header(default=None)):
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
    return {"ok": True, "filename": nome, "content_type": content_type, "size_bytes": len(data), "url": f"/uploads/produtos/{nome}"}


@router.post("/uploads/cursos")
async def upload_material_curso(background_tasks: BackgroundTasks, arquivo: UploadFile = File(...), titulo: str = "material", x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    content_type = arquivo.content_type or ""
    ext = ALLOWED_CURSO_TYPES.get(content_type)
    if not ext:
        filename_lower = (arquivo.filename or "").lower()
        for tipo, extensao in ALLOWED_CURSO_TYPES.items():
            if filename_lower.endswith(extensao):
                ext = extensao
                content_type = tipo
                break
    if not ext:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PDF, PPT, PPTX, MP4, WEBM ou MOV.")
    data = await arquivo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    limite = MAX_CURSO_VIDEO_BYTES if content_type in ALLOWED_CURSO_VIDEO_TYPES else MAX_CURSO_DOC_BYTES
    if len(data) > limite:
        raise HTTPException(status_code=413, detail=f"Arquivo muito grande. Limite: {limite // (1024 * 1024)} MB.")
    nome = f"{limpar_nome(titulo)}-{uuid4().hex[:10]}{ext}"

    if drive_configured():
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_CURSOS", "").strip() or None
        try:
            drive_file = upload_bytes_to_drive(data=data, filename=nome, mime_type=content_type, folder_id=folder_id)
            link = drive_file.get("download_url") or drive_file.get("web_content_link") or drive_file.get("web_view_link")
            if link:
                return {"ok": True, "filename": nome, "content_type": content_type, "size_bytes": len(data), "url": link, "drive_id": drive_file.get("id"), "armazenamento": "google_drive"}
        except Exception as exc:
            log_tempo("drive_upload_curso_falhou", time.perf_counter(), str(exc))

    destino = CURSOS_DIR / nome
    destino.write_bytes(data)
    return {"ok": True, "filename": nome, "content_type": content_type, "size_bytes": len(data), "url": f"/uploads/cursos/{nome}", "armazenamento": "arquivo"}


@router.post("/uploads/musicas")
async def upload_musica_ambiente(background_tasks: BackgroundTasks, arquivo: UploadFile = File(...), nome_base: str = "ambiente-xamanico", x_mistica_api_key: str | None = Header(default=None)):
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

    if drive_configured():
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_MUSICAS", "").strip() or None
        try:
            drive_file = upload_bytes_to_drive(data=data, filename=nome, mime_type=content_type, folder_id=folder_id)
            link = drive_file.get("download_url") or drive_file.get("web_content_link") or drive_file.get("web_view_link")
            if link:
                adicionar_link_audio_persistente(link)
            _MUSICAS_CACHE["at"] = 0.0
            _MUSICAS_CACHE["data"] = None
            return {"ok": True, "filename": nome, "content_type": content_type, "size_bytes": len(data), "url": link, "drive_id": drive_file.get("id"), "data_hora": criado_em, "armazenamento": "google_drive"}
        except Exception as exc:
            log_tempo("drive_upload_falhou", time.perf_counter(), str(exc))

    destino = AUDIO_DIR / nome
    destino.write_bytes(data)
    background_tasks.add_task(salvar_musica_no_banco, nome, content_type, data, criado_em)
    _MUSICAS_CACHE["at"] = 0.0
    _MUSICAS_CACHE["data"] = None
    return {"ok": True, "filename": nome, "content_type": content_type, "size_bytes": len(data), "url": f"/api/uploads/musicas/arquivo-local/{nome}", "data_hora": criado_em, "armazenamento": "arquivo+backup_banco"}


@router.get("/uploads/musicas")
def listar_musicas_ambiente():
    inicio = time.perf_counter()
    agora = time.monotonic()
    cache_data = _MUSICAS_CACHE.get("data")
    if cache_data and agora - float(_MUSICAS_CACHE.get("at") or 0) < 20:
        return cache_data
    musicas_banco, nomes_banco, erro_banco = listar_musicas_banco_rapido()
    musicas_arquivos = listar_musicas_arquivo_local(nomes_banco)
    musicas_links = listar_musicas_links()
    musicas = (musicas_links + musicas_arquivos + musicas_banco)[:30]
    resposta = {"ok": True, "musicas": musicas, "total": len(musicas), "fonte": "drive+arquivo+banco_rapido", "banco_erro": erro_banco, "data_hora": datetime.now().isoformat(timespec="seconds")}
    _MUSICAS_CACHE["at"] = agora
    _MUSICAS_CACHE["data"] = resposta
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
    return Response(content=arquivo.read_bytes(), media_type=media_type_por_nome(nome), headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600", "Content-Disposition": f"inline; filename={nome}"})


@router.get("/uploads/musicas/arquivo/{musica_id}")
def obter_musica_ambiente(musica_id: int):
    with conectar() as conn:
        garantir_tabela_musicas_ambiente(conn)
        row = conn.execute("SELECT filename, content_type, dados FROM site_musicas_ambiente WHERE id=?", (musica_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Música não encontrada.")
    return Response(content=row["dados"], media_type=row["content_type"], headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600", "Content-Disposition": f"inline; filename={row['filename']}"})


@router.get("/uploads/musicas/links")
def listar_links_audio_ambiente():
    links = []
    if AUDIO_LINKS_FILE.exists():
        links = limpar_links_audio(AUDIO_LINKS_FILE.read_text(encoding="utf-8").splitlines())
    return {"ok": True, "links": links, "total": len(links), "data_hora": datetime.now().isoformat(timespec="seconds")}


@router.post("/uploads/musicas/links")
def salvar_links_audio_ambiente(payload: AudioLinksIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    links = limpar_links_audio(payload.links)
    AUDIO_LINKS_FILE.write_text("\n".join(links), encoding="utf-8")
    _MUSICAS_CACHE["at"] = 0.0
    _MUSICAS_CACHE["data"] = None
    return {"ok": True, "links": links, "total": len(links), "data_hora": datetime.now().isoformat(timespec="seconds")}
