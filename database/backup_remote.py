"""Replicacao criptografada de backups locais para armazenamento externo.

Este modulo nao cria backups SQLite e nao participa da validacao/publicacao
local. Ele recebe apenas arquivos que o servico de backup local ja publicou.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import struct
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


_MAGIC = b"MISTBKP1"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_CHUNK_BYTES = 1024 * 1024
_PERMANENT_ERROR_CODES = {
    "AccessDenied",
    "AuthFailure",
    "EntityTooLarge",
    "ExpiredToken",
    "InvalidArgument",
    "InvalidAccessKeyId",
    "InvalidBucketName",
    "InvalidRequest",
    "InvalidToken",
    "MethodNotAllowed",
    "NoSuchBucket",
    "NotImplemented",
    "PermanentRedirect",
    "SignatureDoesNotMatch",
    "Unauthorized",
}
_active_threads: dict[threading.Thread, Callable[..., dict]] = {}
_threads_lock = threading.RLock()
_accepting_uploads = True
logger = logging.getLogger(__name__)


class RemoteBackupError(Exception):
    """Falha operacional na replicacao remota."""

    def __init__(self, message: str, *, record: dict | None = None):
        super().__init__(message)
        self.record = record


class RemoteConfigurationError(RemoteBackupError):
    """Configuracao remota ausente ou invalida."""


class RemoteVerificationError(RemoteBackupError):
    """O objeto remoto nao corresponde ao arquivo enviado."""


class RemoteStorage(ABC):
    """Contrato minimo para providers atuais e futuros."""

    name: str

    @abstractmethod
    def upload(self, local_path: Path, object_key: str, metadata: dict[str, str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def stat(self, object_key: str) -> dict:
        """Retorna ao menos ``size`` e ``sha256`` do objeto remoto."""
        raise NotImplementedError


class R2Storage(RemoteStorage):
    """Cloudflare R2 via sua API compativel com Amazon S3."""

    name = "r2"

    def __init__(self, config: "RemoteBackupConfig"):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - coberto pela validacao de deploy
            raise RemoteConfigurationError("dependencia boto3 indisponivel") from exc

        self.bucket = config.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name="auto",
            config=Config(
                connect_timeout=config.timeout,
                read_timeout=config.timeout,
                retries={"max_attempts": 0, "mode": "standard"},
            ),
        )

    def upload(self, local_path: Path, object_key: str, metadata: dict[str, str]) -> None:
        self.client.upload_file(
            str(local_path),
            self.bucket,
            object_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": metadata,
            },
        )

    def stat(self, object_key: str) -> dict:
        resposta = self.client.head_object(Bucket=self.bucket, Key=object_key)
        objeto = self.client.get_object(Bucket=self.bucket, Key=object_key)
        digest = hashlib.sha256()
        body = objeto["Body"]
        try:
            for chunk in iter(lambda: body.read(_CHUNK_BYTES), b""):
                digest.update(chunk)
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()
        return {
            "size": int(resposta.get("ContentLength", -1)),
            "sha256": digest.hexdigest(),
        }


@dataclass(frozen=True)
class RemoteBackupConfig:
    enabled: bool
    provider: str
    bucket: str
    endpoint: str
    access_key: str
    secret_key: str
    prefix: str
    encryption_key: bytes | None
    timeout: float
    verify_after_upload: bool

    @classmethod
    def from_env(cls) -> "RemoteBackupConfig":
        enabled = _env_bool("BACKUP_REMOTE_ENABLED", False)
        provider = os.environ.get("BACKUP_PROVIDER", "r2").strip().lower() or "r2"
        timeout = _env_float("BACKUP_UPLOAD_TIMEOUT", 30.0, minimo=1.0, maximo=3600.0)
        key_text = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
        # Configuracao incompleta/invalida jamais interfere no backup local
        # enquanto a segunda camada estiver explicitamente desabilitada.
        key = _decode_encryption_key(key_text) if key_text and enabled else None
        return cls(
            enabled=enabled,
            provider=provider,
            bucket=os.environ.get("BACKUP_BUCKET", "").strip(),
            endpoint=os.environ.get("BACKUP_ENDPOINT", "").strip(),
            access_key=os.environ.get("BACKUP_ACCESS_KEY", "").strip(),
            secret_key=os.environ.get("BACKUP_SECRET_KEY", "").strip(),
            prefix=os.environ.get("BACKUP_PREFIX", "").strip().strip("/"),
            encryption_key=key,
            timeout=timeout,
            verify_after_upload=_env_bool("BACKUP_VERIFY_AFTER_UPLOAD", True),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.provider != "r2":
            raise RemoteConfigurationError(f"provider nao suportado: {self.provider}")
        ausentes = [
            nome
            for nome, valor in (
                ("BACKUP_BUCKET", self.bucket),
                ("BACKUP_ENDPOINT", self.endpoint),
                ("BACKUP_ACCESS_KEY", self.access_key),
                ("BACKUP_SECRET_KEY", self.secret_key),
                ("BACKUP_ENCRYPTION_KEY", self.encryption_key),
            )
            if not valor
        ]
        if ausentes:
            raise RemoteConfigurationError("configuracao remota incompleta: " + ", ".join(ausentes))
        if not self.endpoint.lower().startswith("https://"):
            raise RemoteConfigurationError("BACKUP_ENDPOINT do R2 deve usar HTTPS")
        if len(self.encryption_key or b"") != 32:
            raise RemoteConfigurationError("BACKUP_ENCRYPTION_KEY deve representar exatamente 32 bytes")


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


def _decode_encryption_key(value: str) -> bytes:
    """Aceita chave de 32 bytes em base64 ou 64 caracteres hexadecimais."""
    import base64
    import binascii

    try:
        if len(value) == 64:
            return bytes.fromhex(value)
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RemoteConfigurationError("BACKUP_ENCRYPTION_KEY deve estar em base64 ou hexadecimal") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as arquivo:
        for chunk in iter(lambda: arquivo.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_local_backup(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RemoteBackupError("arquivo local de backup invalido")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise RemoteBackupError("arquivo local de backup invalido") from exc
    if not result or str(result[0]).strip().lower() != "ok":
        raise RemoteBackupError("arquivo local de backup invalido")


_UNSAFE_ERROR_DETAIL_RE = re.compile(
    r"(?i)(?:https?://|[a-z]:[\\/]|(?:^|\s)[\\/]\S+|(?:^|\s)\.{1,2}[\\/]\S+|"
    r"(?:^|\s)[\w.-]+[\\/]\S+|"
    r"\?[^\s]*=|(?:authorization|cookie|headers?|access[_\s-]*key|secret[_\s-]*key|"
    r"encryption[_\s-]*key|api[_\s-]*key|password|credential|token|signature)[\"']?\s*[:=])"
)


def sanitize_remote_error(
    error: Exception,
    config: RemoteBackupConfig | None = None,
    source: Path | None = None,
    *,
    fallback: str = "Falha na replicacao remota.",
    expose_safe_detail: bool = True,
) -> str:
    """Produz mensagem segura para persistencia e exposicao administrativa.

    O caminho de despacho usa ``expose_safe_detail=False`` porque a excecao
    pode vir do runtime, do filesystem ou de um SDK ainda nao normalizado. Nos
    fluxos controlados do provider, detalhes operacionais simples continuam
    uteis, mas URLs, caminhos, headers e parametros sensiveis forcam fallback.
    """
    if not expose_safe_detail:
        return fallback

    message = str(error) or error.__class__.__name__
    if any(marker in message for marker in ("\r", "\n", "Traceback", 'File "')):
        return fallback
    message = message[:4000]
    encryption_key_text = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
    configured_values = (
        config.access_key if config else os.environ.get("BACKUP_ACCESS_KEY", "").strip(),
        config.secret_key if config else os.environ.get("BACKUP_SECRET_KEY", "").strip(),
        config.bucket if config else os.environ.get("BACKUP_BUCKET", "").strip(),
        config.endpoint if config else os.environ.get("BACKUP_ENDPOINT", "").strip(),
    )
    for sensitive in (
        *configured_values,
        encryption_key_text,
        str(source) if source else "",
        str(source.resolve()) if source else "",
        tempfile.gettempdir(),
        str(Path.home()),
    ):
        if sensitive:
            message = message.replace(sensitive, "[dado removido]")
    message = " ".join(message.splitlines()).strip()
    if not message or _UNSAFE_ERROR_DETAIL_RE.search(message):
        return fallback
    return message[:500]


def _is_retryable(error: Exception) -> bool:
    """Distingue falhas transitórias de configuração/autorização permanentes."""
    if isinstance(error, (PermissionError, RemoteConfigurationError)):
        return False
    current: BaseException | None = error
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        response = getattr(current, "response", None)
        if isinstance(response, dict):
            code = str((response.get("Error") or {}).get("Code") or "")
            status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            if code in _PERMANENT_ERROR_CODES or status in {401, 403}:
                return False
        current = current.__cause__ or current.__context__
    return True


def _encrypt_aes256_gcm(source: Path, destination: Path, key: bytes) -> None:
    """Criptografa em streaming usando AES-256-GCM autenticado.

    Formato preparado para restauracao futura: magic(8), nonce(12), tamanho
    original unsigned int64, ciphertext e tag GCM(16).
    """
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:  # pragma: no cover - coberto pela validacao de deploy
        raise RemoteConfigurationError("dependencia cryptography indisponivel") from exc

    if len(key) != 32:
        raise RemoteConfigurationError("chave AES-256 deve ter exatamente 32 bytes")
    nonce = os.urandom(_NONCE_BYTES)
    header = _MAGIC + nonce + struct.pack(">Q", source.stat().st_size)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    with source.open("rb") as entrada, destination.open("wb") as saida:
        saida.write(header)
        for chunk in iter(lambda: entrada.read(_CHUNK_BYTES), b""):
            saida.write(encryptor.update(chunk))
        saida.write(encryptor.finalize())
        saida.write(encryptor.tag)


def create_provider(config: RemoteBackupConfig) -> RemoteStorage:
    config.validate()
    if config.provider == "r2":
        return R2Storage(config)
    raise RemoteConfigurationError(f"provider nao suportado: {config.provider}")


class RemoteBackupService:
    def __init__(
        self,
        config: RemoteBackupConfig,
        *,
        provider: RemoteStorage | None = None,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 3,
    ):
        config.validate()
        self.config = config
        self.provider = provider or create_provider(config)
        self.sleep = sleep
        self.attempts = max(1, int(attempts))

    def sync(self, backup_path: Path | str) -> dict:
        source = Path(backup_path)
        _validate_local_backup(source)

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        source_size = source.stat().st_size
        source_checksum = _sha256(source)
        object_name = f"{source.name}.aes256"
        object_key = f"{self.config.prefix}/{object_name}" if self.config.prefix else object_name
        fd, encrypted_name = tempfile.mkstemp(prefix="mistica-remote-", suffix=".aes256")
        os.close(fd)
        encrypted = Path(encrypted_name)
        try:
            _encrypt_aes256_gcm(source, encrypted, self.config.encryption_key or b"")
            size = encrypted.stat().st_size
            checksum = _sha256(encrypted)
            metadata = {
                "sha256": checksum,
                "source-name": source.name,
                "source-sha256": source_checksum,
                "encrypted": "aes-256-gcm",
                "created-at": created_at,
            }
            last_error: Exception | None = None
            attempts_used = 0
            for attempt in range(1, self.attempts + 1):
                attempts_used = attempt
                try:
                    self.provider.upload(encrypted, object_key, metadata)
                    if self.config.verify_after_upload:
                        remote = self.provider.stat(object_key)
                        if int(remote.get("size", -1)) != size:
                            raise RemoteVerificationError("tamanho remoto diferente do arquivo enviado")
                        if str(remote.get("sha256") or "").lower() != checksum:
                            raise RemoteVerificationError("hash SHA-256 remoto diferente do arquivo enviado")
                    return {
                        "nome": object_name,
                        "tamanho_bytes": size,
                        "data": created_at,
                        "hash_sha256": checksum,
                        "source_hash_sha256": source_checksum,
                        "source_tamanho_bytes": source_size,
                        "provider": self.provider.name,
                        "status": "sucesso",
                        "erro": None,
                        "tentativas": attempt,
                    }
                except Exception as exc:  # provider converte erros de rede/auth/timeout aqui
                    last_error = exc
                    if not _is_retryable(exc):
                        break
                    if attempt < self.attempts:
                        self.sleep(2 ** (attempt - 1))
            assert last_error is not None
            error_message = sanitize_remote_error(last_error, self.config, source)
            raise RemoteBackupError(
                error_message,
                record={
                    "nome": object_name,
                    "tamanho_bytes": size,
                    "data": created_at,
                    "hash_sha256": checksum,
                    "source_hash_sha256": source_checksum,
                    "source_tamanho_bytes": source_size,
                    "provider": self.provider.name,
                    "status": "falha",
                    "erro": error_message,
                    "tentativas": attempts_used,
                },
            ) from last_error
        finally:
            encrypted.unlink(missing_ok=True)


def _failure_record(source: Path, provider: str, error: Exception, config: RemoteBackupConfig) -> dict:
    existing = getattr(error, "record", None)
    if isinstance(existing, dict):
        return existing
    try:
        source_size = source.stat().st_size if source.is_file() else None
    except OSError:
        source_size = None
    return {
        "nome": f"{source.name}.aes256",
        "tamanho_bytes": None,
        "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hash_sha256": None,
        "source_hash_sha256": None,
        "source_tamanho_bytes": source_size,
        "provider": provider,
        "status": "falha",
        "erro": sanitize_remote_error(error, config, source),
        "tentativas": 0,
    }


def _state_changes(record: dict) -> dict:
    success = record["status"] == "sucesso"
    changes = {
        "remote_enabled": True,
        "remote_provider": record["provider"],
        "remote_status": "ok" if success else "erro",
        "last_remote_error": None if success else record["erro"],
    }
    if success:
        changes.update(
            last_remote_backup=record["nome"],
            last_remote_size=record["tamanho_bytes"],
            last_remote_hash=record["hash_sha256"],
        )
    return changes


def sync_and_record(
    backup_path: Path | str,
    *,
    save_state: Callable[..., dict],
    config: RemoteBackupConfig | None = None,
    provider: RemoteStorage | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict | None:
    """Sincroniza e persiste resultado sem propagar falhas ao backup local."""
    config = config or RemoteBackupConfig.from_env()
    if not config.enabled:
        return None
    source = Path(backup_path)
    try:
        record = RemoteBackupService(config, provider=provider, sleep=sleep).sync(source)
    except Exception as exc:
        record = _failure_record(source, config.provider, exc, config)
    # O prepend e o merge acontecem sob o mesmo lock/replace atomico do
    # backup.status.json, evitando perda de entradas em uploads concorrentes.
    save_state(_prepend_remote_upload=record, **_state_changes(record))
    return record


def _run_tracked_sync(**kwargs) -> None:
    """Supervisiona a thread e captura inclusive falhas fora do provider."""
    try:
        sync_and_record(**kwargs)
    except BaseException:
        # Nao inclui traceback/mensagem arbitraria: uma excecao de SDK pode
        # conter endpoint, bucket ou credenciais em seus atributos.
        logger.error("falha inesperada na tarefa de backup remoto")
        save_state = kwargs.get("save_state")
        if callable(save_state):
            try:
                save_state(remote_status="erro", last_remote_error="falha inesperada na tarefa remota")
            except Exception:
                logger.error("falha ao registrar erro inesperado do backup remoto")
    finally:
        with _threads_lock:
            _active_threads.pop(threading.current_thread(), None)


def trigger_remote_sync(
    backup_path: Path | str,
    *,
    save_state: Callable[..., dict],
    config: RemoteBackupConfig | None = None,
) -> threading.Thread | None:
    """Dispara replicacao em daemon; nunca espera rede no chamador."""
    config = config or RemoteBackupConfig.from_env()
    if not config.enabled:
        return None
    with _threads_lock:
        if not _accepting_uploads:
            accepting = False
        else:
            accepting = True
    if not accepting:
        save_state(
            remote_enabled=True,
            remote_provider=config.provider,
            remote_status="erro",
            last_remote_error="aplicacao em encerramento; upload nao iniciado",
        )
        return None
    save_state(
        remote_enabled=True,
        remote_provider=config.provider,
        remote_status="enfileirado",
        last_remote_error=None,
    )
    thread = threading.Thread(
        target=_run_tracked_sync,
        kwargs={
            "backup_path": backup_path,
            "save_state": save_state,
            "config": config,
        },
        name="backup-remote-upload",
        daemon=True,
    )
    with _threads_lock:
        if not _accepting_uploads:
            save_state(
                remote_enabled=True,
                remote_provider=config.provider,
                remote_status="erro",
                last_remote_error="aplicacao em encerramento; upload nao iniciado",
            )
            return None
        _active_threads[thread] = save_state
        try:
            thread.start()
        except BaseException:
            _active_threads.pop(thread, None)
            raise
    return thread


def start_remote_uploads() -> None:
    """Reabre o supervisor no startup do lifespan da API."""
    global _accepting_uploads
    with _threads_lock:
        _accepting_uploads = True


def shutdown_remote_uploads(timeout: float = 30.0) -> bool:
    """Para novos envios e aguarda uploads ativos por um prazo limitado."""
    global _accepting_uploads
    deadline = time.monotonic() + max(0.0, float(timeout))
    with _threads_lock:
        _accepting_uploads = False
        threads = list(_active_threads)
    for thread in threads:
        remaining = max(0.0, deadline - time.monotonic())
        thread.join(remaining)
    with _threads_lock:
        active = [(thread, save_state) for thread, save_state in _active_threads.items() if thread.is_alive()]
    for _, save_state in active:
        try:
            save_state(
                remote_status="erro",
                last_remote_error="upload remoto interrompido pelo encerramento da aplicacao",
            )
        except Exception:
            logger.error("falha ao registrar interrupcao do backup remoto")
    return not active
