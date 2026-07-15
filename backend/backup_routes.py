from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.api_security import validar_site_api_key as validar_chave_api
from backend.panel_sessions import exigir_sessao_ou_chave_api
from config import BACKUP_DIR, DB_PATH
from database.backup import BackupInvalidoError, criar_backup_seguro, obter_status_backup

router = APIRouter(prefix="/api", tags=["backup"])

PREFIXO_BACKUP_MANUAL = "mistica_backup"
PREFIXO_BACKUP_DOWNLOAD = "mistica_backup_download"


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir acesso ao backup.")


def _remover_arquivo_temporario(caminho: str) -> None:
    for candidato in (caminho, f"{caminho}.sha256"):
        try:
            os.remove(candidato)
        except OSError:
            pass


@router.post("/backup/manual")
def criar_backup_manual(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Arquivo do banco de dados não encontrado")

    try:
        info = criar_backup_seguro(DB_PATH, BACKUP_DIR, PREFIXO_BACKUP_MANUAL)
    except BackupInvalidoError as exc:
        raise HTTPException(status_code=500, detail="O backup gerado falhou na validação de integridade.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Falha ao criar backup.") from exc

    return {
        "status": "ok",
        "mensagem": "Backup manual criado com sucesso.",
        "arquivo": info["nome"],
        "tamanho_bytes": info["tamanho_bytes"],
        "checksum_sha256": info["checksum_sha256"],
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/backup/status")
def status_backup_manual(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    destino_dir = Path(BACKUP_DIR)
    backups = []

    if destino_dir.exists():
        arquivos = sorted(
            (p for p in destino_dir.glob(f"{PREFIXO_BACKUP_MANUAL}_*.db") if p.is_file()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for arquivo in arquivos[:10]:
            backups.append(
                {
                    "nome": arquivo.name,
                    "tamanho_bytes": arquivo.stat().st_size,
                    "modificado_em": datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(timespec="seconds"),
                }
            )

    return {
        "status": "ok",
        "banco_existe": os.path.exists(DB_PATH),
        # Não revela o caminho absoluto do disco/servidor: apenas o nome do
        # diretório de backups, suficiente para o painel administrativo.
        "backup_dir": destino_dir.name,
        "backup_dir_existe": destino_dir.exists(),
        "ultimos_backups": backups,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/admin/backup/status")
def status_backup_administrativo(sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    """Resumo operacional sem expor caminhos ou permitir acesso aos arquivos."""
    return obter_status_backup()


@router.get("/backup/download")
def baixar_backup_atual(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Arquivo do banco de dados não encontrado")

    try:
        info = criar_backup_seguro(DB_PATH, BACKUP_DIR, PREFIXO_BACKUP_DOWNLOAD)
    except BackupInvalidoError as exc:
        raise HTTPException(status_code=500, detail="O backup gerado falhou na validação de integridade.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Falha ao criar backup.") from exc

    # A cópia de download é efêmera: é removida do disco assim que a resposta
    # termina de ser enviada, para não acumular arquivos temporários.
    #
    # A remoção usa BackgroundTask, que o Starlette só executa depois que o
    # corpo da resposta já foi totalmente enviado ao cliente (ver
    # `Response.__call__`/`FileResponse.__call__`): o `await self.background()`
    # só é alcançado após o laço de leitura e envio do arquivo terminar. O
    # servidor ASGI usado aqui (uvicorn) não oferece a extensão
    # `http.response.pathsend` (que delegaria o envio ao servidor de forma
    # assíncrona e tornaria esse `background` prematuro); se isso mudar no
    # futuro, o header abaixo continua permitindo detectar corrupção via
    # checksum, mas o ideal é revalidar esta suposição antes de trocar de
    # servidor ASGI.
    return FileResponse(
        path=info["caminho"],
        media_type="application/octet-stream",
        filename=info["nome"],
        headers={"X-Backup-Checksum-Sha256": info["checksum_sha256"]},
        background=BackgroundTask(_remover_arquivo_temporario, info["caminho"]),
    )
