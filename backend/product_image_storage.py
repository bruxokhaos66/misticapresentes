"""Armazenamento persistente das imagens de produtos.

O disco local dos serviços web do Render é efêmero: qualquer arquivo gravado
fora do disco persistente configurado em ``render.yaml`` (montado em
``/data``) some no próximo deploy, reinício ou recriação da instância. Antes
desta camada, o endpoint de upload gravava direto em ``backend/uploads/produtos``,
que fica dentro do código da aplicação e é substituído a cada deploy -- por
isso a URL continuava salva no banco, mas o arquivo físico desaparecia.

Esta camada resolve isso de duas formas, escolhidas por configuração:

- produção: armazenamento de objetos compatível com S3 (Cloudflare R2, Amazon
  S3, Backblaze B2, etc.), com URL pública estável e independente da
  instância que recebeu o upload;
- desenvolvimento/local (ou fallback quando o storage remoto não está
  configurado): disco local, mas gravado no mesmo diretório usado pelo banco
  (``PRODUCT_IMAGES_LOCAL_DIR`` ou o diretório de ``MISTICA_DB_PATH``), para
  que ao menos sobreviva a reinícios quando um disco persistente existir.

Nunca reutiliza as credenciais do backup remoto (``BACKUP_*``): são segredos
com escopo e prefixo próprios, e nomes/veriáveis distintos evitam que um
bucket de imagens públicas acabe com a permissão de escrita do backup do
banco (ou vice-versa).
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_TIMEOUT_PADRAO = 15.0
_TIMEOUT_MIN = 1.0
_TIMEOUT_MAX = 120.0


class ProductImageStorageError(Exception):
    """Falha operacional ao enviar, remover ou consultar uma imagem de produto."""


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}


def _env_float(nome: str, padrao: float, *, minimo: float, maximo: float) -> float:
    try:
        valor = float(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao
    return valor if minimo <= valor <= maximo else padrao


@dataclass(frozen=True)
class ProductImageStorageConfig:
    enabled: bool
    bucket: str
    endpoint: str
    region: str
    access_key: str
    secret_key: str
    public_base_url: str
    prefix: str
    timeout: float

    @classmethod
    def from_env(cls) -> "ProductImageStorageConfig":
        return cls(
            enabled=_env_bool("PRODUCT_IMAGES_STORAGE_ENABLED", False),
            bucket=os.environ.get("PRODUCT_IMAGES_BUCKET", "").strip(),
            endpoint=os.environ.get("PRODUCT_IMAGES_ENDPOINT", "").strip(),
            region=os.environ.get("PRODUCT_IMAGES_REGION", "auto").strip() or "auto",
            access_key=os.environ.get("PRODUCT_IMAGES_ACCESS_KEY_ID", "").strip(),
            secret_key=os.environ.get("PRODUCT_IMAGES_SECRET_ACCESS_KEY", "").strip(),
            public_base_url=os.environ.get("PRODUCT_IMAGES_PUBLIC_BASE_URL", "").strip().rstrip("/"),
            prefix=os.environ.get("PRODUCT_IMAGES_PREFIX", "produtos").strip().strip("/") or "produtos",
            timeout=_env_float("PRODUCT_IMAGES_UPLOAD_TIMEOUT", _TIMEOUT_PADRAO, minimo=_TIMEOUT_MIN, maximo=_TIMEOUT_MAX),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        ausentes = [
            nome
            for nome, valor in (
                ("PRODUCT_IMAGES_BUCKET", self.bucket),
                ("PRODUCT_IMAGES_ENDPOINT", self.endpoint),
                ("PRODUCT_IMAGES_ACCESS_KEY_ID", self.access_key),
                ("PRODUCT_IMAGES_SECRET_ACCESS_KEY", self.secret_key),
                ("PRODUCT_IMAGES_PUBLIC_BASE_URL", self.public_base_url),
            )
            if not valor
        ]
        if ausentes:
            raise ProductImageStorageError(
                "configuracao de armazenamento de imagens incompleta: " + ", ".join(ausentes)
            )
        if not self.endpoint.lower().startswith("https://"):
            raise ProductImageStorageError("PRODUCT_IMAGES_ENDPOINT deve usar HTTPS")
        if not self.public_base_url.lower().startswith("https://"):
            raise ProductImageStorageError("PRODUCT_IMAGES_PUBLIC_BASE_URL deve usar HTTPS")


def _nome_seguro(valor: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(valor or "").strip().lower())
    return base.strip("-")[:60] or "produto"


def _caminho_local_gerenciado(valor: str) -> str | None:
    """Se ``valor`` (absoluto ou relativo) aponta para a rota estática local
    de imagens de produto, devolve o path (``/uploads/produtos/<arquivo>``);
    senão, None. Usa só o path da URL -- não o domínio -- para reconhecer
    tanto ``/uploads/produtos/x.png`` quanto ``https://qualquer-dominio/uploads/produtos/x.png``,
    que é como o front-end (v2-admin-products.js normalizeUrl) sempre monta a
    URL antes de salvar no produto."""
    caminho = urlparse(valor).path if valor.startswith(("http://", "https://")) else valor
    if caminho.startswith("/uploads/produtos/") and Path(caminho).name:
        return caminho
    return None


class ProductImageStorage:
    """Camada única de armazenamento das imagens de produtos.

    Endpoints não devem chamar boto3/S3 nem escrever no disco diretamente --
    tudo passa por aqui, para manter a política de nomes, prefixos e
    remoção em um único lugar.
    """

    def __init__(self, *, local_dir: Path, config: ProductImageStorageConfig | None = None):
        self.config = config or ProductImageStorageConfig.from_env()
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self._client = None

    @property
    def remote_enabled(self) -> bool:
        return self.config.enabled

    def _s3_client(self):
        if self._client is not None:
            return self._client
        self.config.validate()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - dependencia sempre presente em producao
            raise ProductImageStorageError("dependencia boto3 indisponivel") from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=self.config.endpoint,
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
            region_name=self.config.region,
            config=Config(
                connect_timeout=self.config.timeout,
                read_timeout=self.config.timeout,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        return self._client

    def build_key(self, produto_id: str, ext: str) -> str:
        agora = datetime.now(timezone.utc)
        return f"{self.config.prefix}/{_nome_seguro(produto_id)}/{agora:%Y}/{agora:%m}/{uuid.uuid4().hex}{ext}"

    def _public_url(self, key: str) -> str:
        return f"{self.config.public_base_url}/{key}"

    def key_from_url(self, url: str) -> str | None:
        """Extrai a chave do objeto se a URL pertence a este storage remoto."""
        base = self.config.public_base_url
        if not base or not url:
            return None
        prefixo = base + "/"
        if url.startswith(prefixo):
            return url[len(prefixo):]
        return None

    def upload(self, data: bytes, *, produto_id: str, ext: str, content_type: str) -> dict:
        """Envia os bytes já validados/normalizados e devolve a URL pública definitiva.

        Não grava nada no banco -- quem chama só deve persistir a URL depois
        que esta função retornar com sucesso.
        """
        key = self.build_key(produto_id, ext)
        if self.remote_enabled:
            try:
                client = self._s3_client()
                client.put_object(
                    Bucket=self.config.bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                    CacheControl="public, max-age=31536000, immutable",
                )
            except ProductImageStorageError:
                raise
            except Exception as exc:
                logger.error(
                    "falha ao enviar imagem de produto para o storage remoto",
                    extra={"evento": "product_image_upload_falhou", "erro_tipo": type(exc).__name__},
                )
                raise ProductImageStorageError("Falha ao enviar imagem para o armazenamento remoto.") from exc
            return {"key": key, "url": self._public_url(key), "backend": "s3"}

        nome_local = Path(key).name
        destino = self.local_dir / nome_local
        destino.write_bytes(data)
        return {"key": key, "url": f"/uploads/produtos/{nome_local}", "backend": "local"}

    def delete(self, key_or_url: str | None) -> None:
        """Remove um objeto que este storage gerenciou. Silencioso para URLs
        externas/legadas -- nunca tenta apagar algo que não controla."""
        if not key_or_url:
            return
        key = self.key_from_url(key_or_url) if key_or_url.startswith(("http://", "https://")) else key_or_url
        if self.remote_enabled and key and self.key_from_url(key_or_url) is not None:
            try:
                client = self._s3_client()
                client.delete_object(Bucket=self.config.bucket, Key=key)
            except Exception as exc:
                logger.warning(
                    "falha ao remover imagem de produto do storage remoto",
                    extra={"evento": "product_image_delete_falhou", "erro_tipo": type(exc).__name__},
                )
            return
        caminho_local = _caminho_local_gerenciado(key_or_url)
        if caminho_local:
            nome_local = Path(caminho_local).name
            try:
                (self.local_dir / nome_local).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "falha ao remover imagem de produto local",
                    extra={"evento": "product_image_delete_local_falhou", "erro_tipo": type(exc).__name__},
                )

    def exists(self, key_or_url: str | None) -> bool:
        if not key_or_url:
            return False
        key = self.key_from_url(key_or_url) if key_or_url.startswith(("http://", "https://")) else key_or_url
        if self.remote_enabled and key and self.key_from_url(key_or_url) is not None:
            try:
                client = self._s3_client()
                client.head_object(Bucket=self.config.bucket, Key=key)
                return True
            except Exception:
                return False
        caminho_local = _caminho_local_gerenciado(key_or_url)
        if caminho_local:
            return (self.local_dir / Path(caminho_local).name).is_file()
        return True


def is_managed_by_storage(storage: ProductImageStorage, url: str | None) -> bool:
    """True quando a URL foi gerada por este storage (remoto ou local) --
    ou seja, seguro remover/reemitir. URLs externas ou de outros domínios
    (Google Drive, links antigos, etc.) nunca retornam True."""
    if not url:
        return False
    if storage.remote_enabled:
        return storage.key_from_url(url) is not None
    return _caminho_local_gerenciado(url) is not None
