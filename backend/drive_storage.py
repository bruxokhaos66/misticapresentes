from __future__ import annotations

import io
import json
import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _load_service_account_info() -> dict[str, Any] | None:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def drive_configured() -> bool:
    return bool(_load_service_account_info())


def _drive_service():
    info = _load_service_account_info()
    if not info:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON não configurado.")
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_bytes_to_drive(*, data: bytes, filename: str, mime_type: str, folder_id: str | None = None) -> dict[str, Any]:
    if not data:
        raise ValueError("Arquivo vazio.")
    service = _drive_service()
    metadata: dict[str, Any] = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type or "application/octet-stream", resumable=False)
    created = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,mimeType,size,webViewLink,webContentLink",
    ).execute()
    file_id = created.get("id")
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
    except Exception:
        pass
    return {
        "id": file_id,
        "name": created.get("name") or filename,
        "mime_type": created.get("mimeType") or mime_type,
        "size": created.get("size"),
        "web_view_link": created.get("webViewLink"),
        "web_content_link": created.get("webContentLink"),
        "download_url": f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else None,
    }
