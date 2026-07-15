import base64
import io
import sqlite3
import sys
import threading
import time
import types
from pathlib import Path

import pytest

import database.backup as backup
import database.backup_remote as remote


class FakeProvider(remote.RemoteStorage):
    name = "r2"

    def __init__(self, failures=None, remote_hash=None, remote_size=None):
        self.failures = list(failures or [])
        self.remote_hash = remote_hash
        self.remote_size = remote_size
        self.uploads = []

    def upload(self, local_path, object_key, metadata):
        self.uploads.append((Path(local_path).read_bytes(), object_key, metadata))
        if self.failures:
            raise self.failures.pop(0)

    def stat(self, object_key):
        content, _, metadata = self.uploads[-1]
        return {
            "size": len(content) if self.remote_size is None else self.remote_size,
            "sha256": metadata["sha256"] if self.remote_hash is None else self.remote_hash,
        }


def _config(**changes):
    values = {
        "enabled": True,
        "provider": "r2",
        "bucket": "backups",
        "endpoint": "https://example.r2.cloudflarestorage.com",
        "access_key": "access",
        "secret_key": "secret",  # pragma: allowlist secret
        "prefix": "mistica",
        "encryption_key": b"k" * 32,
        "timeout": 5.0,
        "verify_after_upload": True,
    }
    values.update(changes)
    return remote.RemoteBackupConfig(**values)


def _source(tmp_path, content=None):
    path = tmp_path / "backup_2026-07-15_03-00-00.db"
    if content is None:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE dados (valor TEXT)")
        conn.execute("INSERT INTO dados VALUES ('backup validado')")
        conn.commit()
        conn.close()
    else:
        path.write_bytes(content)
    return path


def _save_into(state):
    def save(**changes):
        record = changes.pop("_prepend_remote_upload", None)
        if record is not None:
            state["remote_uploads"] = ([record] + state.get("remote_uploads", []))[:50]
        state.update(changes)
        return state

    return save


def test_upload_criptografado_com_sucesso_valida_tamanho_hash_e_metadados(tmp_path):
    source = _source(tmp_path)
    provider = FakeProvider()

    result = remote.RemoteBackupService(_config(), provider=provider).sync(source)

    encrypted, key, metadata = provider.uploads[0]
    assert result["status"] == "sucesso"
    assert result["tentativas"] == 1
    assert key == f"mistica/{source.name}.aes256"
    assert encrypted.startswith(b"MISTBKP1")
    assert source.read_bytes() not in encrypted
    assert metadata["sha256"] == result["hash_sha256"]
    assert metadata["source-sha256"] == result["source_hash_sha256"]
    assert result["source_tamanho_bytes"] == source.stat().st_size
    assert result["tamanho_bytes"] == len(encrypted)
    assert result["provider"] == "r2"


def test_falha_de_rede_tenta_tres_vezes_com_backoff_exponencial(tmp_path):
    provider = FakeProvider(failures=[ConnectionError("rede"), ConnectionError("rede"), ConnectionError("rede")])
    sleeps = []

    with pytest.raises(remote.RemoteBackupError, match="rede"):
        remote.RemoteBackupService(_config(), provider=provider, sleep=sleeps.append).sync(_source(tmp_path))

    assert len(provider.uploads) == 3
    assert sleeps == [1, 2]


def test_retry_recupera_na_terceira_tentativa(tmp_path):
    provider = FakeProvider(failures=[ConnectionError("rede"), TimeoutError("timeout")])
    sleeps = []

    result = remote.RemoteBackupService(_config(), provider=provider, sleep=sleeps.append).sync(_source(tmp_path))

    assert result["status"] == "sucesso"
    assert result["tentativas"] == 3
    assert sleeps == [1, 2]


def test_erro_de_autenticacao_permanente_nao_e_retentado(tmp_path):
    provider = FakeProvider(failures=[PermissionError("autenticacao negada")] * 3)
    sleeps = []

    with pytest.raises(remote.RemoteBackupError, match="autenticacao") as error:
        remote.RemoteBackupService(_config(), provider=provider, sleep=sleeps.append).sync(_source(tmp_path))

    assert len(provider.uploads) == 1
    assert sleeps == []
    assert error.value.record["tentativas"] == 1


def test_erro_s3_permanente_nao_e_retentado(tmp_path):
    class NoSuchBucketError(RuntimeError):
        response = {
            "Error": {"Code": "NoSuchBucket"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }

    provider = FakeProvider(failures=[NoSuchBucketError("bucket ausente")] * 3)
    sleeps = []

    with pytest.raises(remote.RemoteBackupError, match="ausente"):
        remote.RemoteBackupService(_config(), provider=provider, sleep=sleeps.append).sync(_source(tmp_path))

    assert len(provider.uploads) == 1
    assert sleeps == []


@pytest.mark.parametrize("content,exists", [(b"", True), (b"nao e sqlite", True), (None, False)])
def test_arquivo_invalido_nao_inicia_upload(tmp_path, content, exists):
    source = tmp_path / "invalido.db"
    if exists:
        source.write_bytes(content)
    provider = FakeProvider()

    with pytest.raises(remote.RemoteBackupError, match="invalido"):
        remote.RemoteBackupService(_config(), provider=provider).sync(source)

    assert provider.uploads == []


def test_adapter_r2_configura_s3_envia_metadados_e_calcula_hash_remoto(monkeypatch, tmp_path):
    calls = {}
    remote_content = b"objeto remoto criptografado"

    class Client:
        def upload_file(self, *args, **kwargs):
            calls["upload"] = (args, kwargs)

        def head_object(self, **kwargs):
            calls["head"] = kwargs
            return {"ContentLength": len(remote_content)}

        def get_object(self, **kwargs):
            calls["get"] = kwargs
            return {"Body": io.BytesIO(remote_content)}

    def client(service, **kwargs):
        calls["client"] = (service, kwargs)
        return Client()

    class Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=client))
    monkeypatch.setitem(sys.modules, "botocore.config", types.SimpleNamespace(Config=Config))
    provider = remote.R2Storage(_config())
    local = tmp_path / "payload.aes256"
    local.write_bytes(b"payload")

    provider.upload(local, "mistica/payload.aes256", {"sha256": "a" * 64})
    result = provider.stat("mistica/payload.aes256")

    assert calls["client"][0] == "s3"
    assert calls["client"][1]["endpoint_url"] == _config().endpoint
    assert calls["upload"][0][1:] == ("backups", "mistica/payload.aes256")
    assert calls["upload"][1]["ExtraArgs"]["Metadata"]["sha256"] == "a" * 64
    assert calls["head"] == {"Bucket": "backups", "Key": "mistica/payload.aes256"}
    assert calls["get"] == calls["head"]
    assert result == {"size": len(remote_content), "sha256": remote.hashlib.sha256(remote_content).hexdigest()}


@pytest.mark.parametrize(
    "provider,erro",
    [
        (FakeProvider(remote_hash="0" * 64), "hash SHA-256"),
        (FakeProvider(failures=[PermissionError("autenticacao negada")] * 3), "autenticacao"),
        (FakeProvider(failures=[TimeoutError("timeout")] * 3), "timeout"),
        (FakeProvider(failures=[OSError("provider indisponivel")] * 3), "indisponivel"),
    ],
)
def test_erros_de_verificacao_autenticacao_timeout_e_provider(tmp_path, provider, erro):
    with pytest.raises(remote.RemoteBackupError, match=erro):
        remote.RemoteBackupService(_config(), provider=provider, sleep=lambda _: None).sync(_source(tmp_path))


def test_hash_diferente_e_retentado_tres_vezes(tmp_path):
    provider = FakeProvider(remote_hash="f" * 64)
    sleeps = []

    with pytest.raises(remote.RemoteBackupError, match="hash SHA-256"):
        remote.RemoteBackupService(_config(), provider=provider, sleep=sleeps.append).sync(_source(tmp_path))

    assert len(provider.uploads) == 3
    assert sleeps == [1, 2]


def test_tamanho_remoto_diferente_nunca_e_marcado_como_sucesso(tmp_path):
    provider = FakeProvider(remote_size=1)

    with pytest.raises(remote.RemoteBackupError, match="tamanho remoto") as error:
        remote.RemoteBackupService(_config(), provider=provider, sleep=lambda _: None).sync(_source(tmp_path))

    assert len(provider.uploads) == 3
    assert error.value.record["status"] == "falha"


def test_sync_and_record_persiste_falha_sem_apagar_ultimo_sucesso(tmp_path):
    state = {
        "last_remote_backup": "anterior.aes256",
        "last_remote_size": 123,
        "last_remote_hash": "a" * 64,
        "remote_uploads": [],
    }
    provider = FakeProvider(failures=[ConnectionError("sem rede")] * 3)

    result = remote.sync_and_record(
        _source(tmp_path),
        save_state=_save_into(state),
        config=_config(),
        provider=provider,
        sleep=lambda _: None,
    )

    assert result["status"] == "falha"
    assert state["remote_status"] == "erro"
    assert state["last_remote_error"] == "sem rede"
    assert state["last_remote_backup"] == "anterior.aes256"
    assert state["last_remote_hash"] == "a" * 64
    assert state["remote_uploads"][0]["status"] == "falha"
    assert state["remote_uploads"][0]["tamanho_bytes"] > 0
    assert len(state["remote_uploads"][0]["hash_sha256"]) == 64


def test_erro_persistido_remove_credenciais_bucket_endpoint_chave_e_caminho(tmp_path, monkeypatch):
    state = {}
    source = _source(tmp_path)
    encryption_text = "ab" * 32
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", encryption_text)
    config = _config(
        access_key="access-super-secreto",
        secret_key="secret-super-secreto",  # pragma: allowlist secret
        bucket="bucket-privado",
        endpoint="https://endpoint-privado.example",
    )
    unsafe = (
        f"access-super-secreto secret-super-secreto bucket-privado "
        f"https://endpoint-privado.example {encryption_text} {source}"
    )
    provider = FakeProvider(failures=[RuntimeError(unsafe)] * 3)

    remote.sync_and_record(
        source,
        save_state=_save_into(state),
        config=config,
        provider=provider,
        sleep=lambda _: None,
    )

    assert "access-super-secreto" not in state["last_remote_error"]
    assert "secret-super-secreto" not in state["last_remote_error"]
    assert "bucket-privado" not in state["last_remote_error"]
    assert "endpoint-privado" not in state["last_remote_error"]
    assert encryption_text not in state["last_remote_error"]
    assert str(source) not in state["last_remote_error"]


def test_sanitizador_rejeita_caminhos_urls_headers_tokens_e_credenciais(tmp_path, monkeypatch):
    source = _source(tmp_path)
    encryption_text = "cd" * 32
    access_key = "AKIA_TEST_FAKE"
    secret_key = "secret-test-fake"  # pragma: allowlist secret
    bucket = "bucket-secreto-fake"
    endpoint = "https://conta-fake.r2.cloudflarestorage.com"
    credential_url = "https://user-fake:password-fake@example.test/path?token=abc123-fake"  # pragma: allowlist secret
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", encryption_text)
    config = _config(
        access_key=access_key,
        secret_key=secret_key,  # pragma: allowlist secret
        bucket=bucket,
        endpoint=endpoint,
    )
    sensitive_values = (
        r"C:\data\backups\arquivo.db",
        "/data/backups/arquivo.db",
        r"interno\backups\arquivo.db",
        "interno/backups/arquivo.db",
        r"\\servidor-fake\backups\arquivo.db",
        endpoint,
        bucket,
        access_key,
        secret_key,
        encryption_text,
        credential_url,
        "Authorization: Bearer token-fake",
    )
    unsafe = " ".join(sensitive_values)

    safe = remote.sanitize_remote_error(
        RuntimeError(unsafe),
        config,
        source,
        fallback="Falha ao iniciar a replicacao remota.",
    )

    assert safe == "Falha ao iniciar a replicacao remota."
    assert all(value not in safe for value in sensitive_values)


def test_configuracao_aceita_chave_base64_e_nunca_expoe_credenciais(monkeypatch):
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "true")
    monkeypatch.setenv("BACKUP_BUCKET", "bucket")
    monkeypatch.setenv("BACKUP_ENDPOINT", "https://r2.example")
    monkeypatch.setenv("BACKUP_ACCESS_KEY", "nao-expor-access")
    monkeypatch.setenv("BACKUP_SECRET_KEY", "nao-expor-secret")
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", base64.b64encode(b"x" * 32).decode())

    config = remote.RemoteBackupConfig.from_env()
    config.validate()

    assert config.encryption_key == b"x" * 32
    assert "nao-expor" not in str(
        remote._failure_record(Path("backup.db"), "r2", RuntimeError("falha"), config)
    )


def test_configuracao_incompleta_registra_falha_sem_tentar_provider(tmp_path, monkeypatch):
    config = _config(bucket="")
    state = {}
    monkeypatch.setattr(remote, "create_provider", lambda config: pytest.fail("provider nao deve iniciar"))

    result = remote.sync_and_record(_source(tmp_path), save_state=_save_into(state), config=config)

    assert result["status"] == "falha"
    assert result["tentativas"] == 0
    assert "BACKUP_BUCKET" in result["erro"]


def test_remoto_desabilitado_nao_carrega_provider_criptografia_ou_rede(tmp_path, monkeypatch):
    state = {}
    monkeypatch.setattr(remote, "create_provider", lambda config: pytest.fail("provider nao deve iniciar"))
    monkeypatch.setattr(remote, "_encrypt_aes256_gcm", lambda *args: pytest.fail("nao deve criptografar"))

    thread = remote.trigger_remote_sync(
        _source(tmp_path),
        save_state=_save_into(state),
        config=_config(enabled=False, encryption_key=None),
    )

    assert thread is None
    assert state == {}


def test_configuracao_invalida_e_ignorada_quando_remoto_desabilitado(monkeypatch):
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "false")
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "chave-invalida")

    config = remote.RemoteBackupConfig.from_env()

    assert config.enabled is False
    assert config.encryption_key is None
    config.validate()


def test_r2_recusa_endpoint_sem_https():
    with pytest.raises(remote.RemoteConfigurationError, match="HTTPS"):
        _config(endpoint="http://r2.inseguro").validate()


def test_nonce_aes_gcm_e_unico_para_cada_arquivo(tmp_path):
    source = _source(tmp_path)
    first = FakeProvider()
    second = FakeProvider()

    remote.RemoteBackupService(_config(), provider=first).sync(source)
    remote.RemoteBackupService(_config(), provider=second).sync(source)

    first_payload = first.uploads[0][0]
    second_payload = second.uploads[0][0]
    assert first_payload[8:20] != second_payload[8:20]
    assert int.from_bytes(first_payload[20:28], "big") == source.stat().st_size
    assert len(first_payload) == 28 + source.stat().st_size + 16


def test_falha_na_criptografia_remove_arquivo_parcial(tmp_path, monkeypatch):
    state = {}
    monkeypatch.setattr(remote.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(remote, "_encrypt_aes256_gcm", lambda *args: (_ for _ in ()).throw(RuntimeError("cripto falhou")))

    result = remote.sync_and_record(_source(tmp_path), save_state=_save_into(state), config=_config(), provider=FakeProvider())

    assert result["status"] == "falha"
    assert "cripto falhou" in result["erro"]
    assert list(tmp_path.glob("mistica-remote-*.aes256")) == []


def test_integracao_dispara_somente_apos_backup_local_publicado_e_status_ok(tmp_path, monkeypatch):
    source = tmp_path / "mistica_gestao_v20.db"
    directory = tmp_path / "backups"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE dados (valor TEXT)")
    conn.execute("INSERT INTO dados VALUES ('ok')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("MISTICA_DB_PATH", str(source))
    monkeypatch.setenv("BACKUP_DIRECTORY", str(directory))
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "true")
    monkeypatch.setattr(backup, "_obter_espaco_livre_bytes", lambda diretorio=None: 1024**3)
    observed = {}

    def trigger(path, *, save_state, config=None):
        observed["path"] = Path(path)
        observed["state"] = backup._ler_estado(Path(path).parent)
        return None

    monkeypatch.setattr(remote, "trigger_remote_sync", trigger)

    result = backup.executar_backup()

    assert result["status"] == "ok"
    assert observed["path"].is_file()
    assert observed["state"]["status"] == "ok"
    assert observed["state"]["integridade"] == "ok"
    assert observed["state"]["ultimo_backup"] == observed["path"].name


def test_falha_total_do_disparo_remoto_nao_altera_sucesso_local(tmp_path, monkeypatch):
    source = tmp_path / "mistica_gestao_v20.db"
    directory = tmp_path / "backups"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE dados (valor TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("MISTICA_DB_PATH", str(source))
    monkeypatch.setenv("BACKUP_DIRECTORY", str(directory))
    monkeypatch.setenv("BACKUP_REMOTE_ENABLED", "true")
    monkeypatch.setattr(backup, "_obter_espaco_livre_bytes", lambda diretorio=None: 1024**3)
    original_save = backup._salvar_estado
    calls = {"save": 0}

    def trigger(*args, **kwargs):
        raise RuntimeError("uploader indisponivel")

    def save_with_remote_failure(target, **changes):
        calls["save"] += 1
        if "remote_status" in changes:
            raise OSError("status remoto indisponivel")
        return original_save(target, **changes)

    monkeypatch.setattr(remote, "trigger_remote_sync", trigger)
    monkeypatch.setattr(backup, "_salvar_estado", save_with_remote_failure)

    result = backup.executar_backup()

    assert result["status"] == "ok"
    assert (directory / result["nome"]).is_file()
    assert calls["save"] >= 2


def test_tarefa_remota_captura_excecao_inesperada_sem_logar_detalhes(tmp_path, monkeypatch, caplog):
    state = {}
    remote.start_remote_uploads()
    monkeypatch.setattr(remote, "sync_and_record", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    thread = remote.trigger_remote_sync(_source(tmp_path), save_state=_save_into(state), config=_config())
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert state["remote_status"] == "erro"
    assert state["last_remote_error"] == "falha inesperada na tarefa remota"
    assert "boom" not in caplog.text


def test_shutdown_aguarda_uploads_e_recusa_novos(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    state = {}

    def slow_sync(**kwargs):
        started.set()
        assert release.wait(timeout=5)

    remote.start_remote_uploads()
    monkeypatch.setattr(remote, "sync_and_record", slow_sync)
    source = _source(tmp_path)
    thread = remote.trigger_remote_sync(source, save_state=_save_into(state), config=_config())
    assert started.wait(timeout=5)
    assert remote.shutdown_remote_uploads(timeout=0.01) is False
    assert "interrompido" in state["last_remote_error"]

    refused = remote.trigger_remote_sync(source, save_state=_save_into(state), config=_config())
    assert refused is None
    assert "encerramento" in state["last_remote_error"]

    release.set()
    thread.join(timeout=5)
    assert remote.shutdown_remote_uploads(timeout=1) is True
    remote.start_remote_uploads()


def test_historico_remoto_tem_limite_e_atualizacao_concorrente_atomica(tmp_path):
    directory = tmp_path / "backups"

    def write(index):
        backup._salvar_estado(
            directory,
            _prepend_remote_upload={
                "nome": f"backup-{index}.aes256",
                "status": "sucesso",
                "hash_sha256": f"{index:064x}",
            },
        )

    threads = [threading.Thread(target=write, args=(index,)) for index in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    state = backup._ler_estado(directory)
    assert len(state["remote_uploads"]) == 50
    assert len({item["nome"] for item in state["remote_uploads"]}) == 50
    assert all(len(item["hash_sha256"]) == 64 for item in state["remote_uploads"])
