"""Armazenamento persistente dos ativos de imagem do Estúdio de Conteúdo.

Reaproveita o armazenamento persistente já existente no projeto (o mesmo
padrão de `backend.product_image_storage.ProductImageStorage`: S3-compatível
em produção com fallback para disco local persistente), mas em diretório e
prefixo próprios (`isis-conteudo/`) e com credenciais próprias
(`ISIS_CONTENT_IMAGES_*`) -- nunca reaproveita `PRODUCT_IMAGES_*` nem
`BACKUP_*`, para não misturar o escopo de permissão de escrita de um
armazenamento com o de outro.

Toda validação de upload (MIME real via Pillow, tamanho, extensão,
integridade, proteção contra path traversal) segue o mesmo padrão usado em
`backend/upload_routes.py` para imagens de produto.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from backend.logging_config import get_logger
from backend.product_image_storage import ProductImageStorage, ProductImageStorageConfig

logger = get_logger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 60_000_000
FORMATOS_PIL_POR_TIPO = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

VARIANTES_PERMITIDAS = {
    "feed": (1080, 1350),
    "story": (1080, 1920),
}


class IsisContentStorageError(Exception):
    pass


def _isis_content_storage_config() -> ProductImageStorageConfig:
    return ProductImageStorageConfig(
        enabled=os.environ.get("ISIS_CONTENT_IMAGES_STORAGE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on", "sim"},
        bucket=os.environ.get("ISIS_CONTENT_IMAGES_BUCKET", "").strip(),
        endpoint=os.environ.get("ISIS_CONTENT_IMAGES_ENDPOINT", "").strip(),
        region=os.environ.get("ISIS_CONTENT_IMAGES_REGION", "auto").strip() or "auto",
        access_key=os.environ.get("ISIS_CONTENT_IMAGES_ACCESS_KEY_ID", "").strip(),
        secret_key=os.environ.get("ISIS_CONTENT_IMAGES_SECRET_ACCESS_KEY", "").strip(),
        public_base_url=os.environ.get("ISIS_CONTENT_IMAGES_PUBLIC_BASE_URL", "").strip().rstrip("/"),
        prefix=os.environ.get("ISIS_CONTENT_IMAGES_PREFIX", "isis-conteudo").strip().strip("/") or "isis-conteudo",
        timeout=15.0,
    )


def _diretorio_local() -> Path:
    override = os.environ.get("ISIS_CONTENT_IMAGES_LOCAL_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "uploads" / "isis-conteudo"


_storage: ProductImageStorage | None = None


def obter_storage() -> ProductImageStorage:
    global _storage
    if _storage is None:
        _storage = ProductImageStorage(local_dir=_diretorio_local(), config=_isis_content_storage_config())
    return _storage


def validar_imagem_real(data: bytes, content_type: str) -> tuple[int, int]:
    """Confirma (abrindo de fato os bytes com Pillow) que o conteúdo é uma
    imagem válida do formato declarado -- o content-type informado por uma
    chamada pode estar forjado."""
    try:
        imagem = Image.open(io.BytesIO(data))
        formato_real = imagem.format
        largura, altura = imagem.size
        if largura * altura > MAX_PIXELS:
            raise IsisContentStorageError("Imagem excede a resolução máxima permitida.")
        imagem.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise IsisContentStorageError("Arquivo não é uma imagem válida.") from exc
    esperado = FORMATOS_PIL_POR_TIPO.get(content_type)
    if esperado and formato_real != esperado:
        raise IsisContentStorageError("Conteúdo do arquivo não corresponde ao formato declarado.")
    return largura, altura


def salvar_asset(data: bytes, *, draft_id: int, variante: str, content_type: str) -> dict:
    """Valida e persiste um asset de imagem do estúdio. Nunca aceita um
    nome de arquivo vindo de fora -- o nome final é sempre gerado pela
    própria camada de storage (`ProductImageStorage.build_key`), o que já
    elimina qualquer possibilidade de path traversal."""
    if variante not in VARIANTES_PERMITIDAS:
        raise IsisContentStorageError(f"Variante inválida: {variante!r}. Use 'feed' ou 'story'.")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise IsisContentStorageError("Formato inválido. Use JPG, PNG ou WEBP.")
    if not data:
        raise IsisContentStorageError("Arquivo vazio.")
    if len(data) > MAX_IMAGE_BYTES:
        raise IsisContentStorageError("Imagem muito grande. Limite: 8 MB.")

    largura, altura = validar_imagem_real(data, content_type)
    ext = ALLOWED_CONTENT_TYPES[content_type]
    hash_sha256 = hashlib.sha256(data).hexdigest()

    storage = obter_storage()
    resultado = storage.upload(data, produto_id=f"draft-{draft_id}-{variante}", ext=ext, content_type=content_type)
    return {
        "arquivo": resultado["url"],
        "mime_type": content_type,
        "tamanho_bytes": len(data),
        "hash_sha256": hash_sha256,
        "largura": largura,
        "altura": altura,
        "armazenamento": resultado["backend"],
    }


def remover_asset(arquivo_ou_url: str | None) -> None:
    obter_storage().delete(arquivo_ou_url)
