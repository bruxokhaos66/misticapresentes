"""Testes da persistência real das imagens de produtos (backend/product_image_storage.py).

Cobrem a causa raiz do bug relatado: o disco dos serviços web do Render é
efêmero fora do disco persistente montado em /data, então gravar em
backend/uploads/produtos (dentro do código da aplicação) fazia as imagens
desaparecerem no deploy seguinte, mesmo com a URL preservada no banco.
"""
from __future__ import annotations

import importlib
import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")

main = importlib.import_module("backend.main")
upload_routes = importlib.import_module("backend.upload_routes")
product_routes = importlib.import_module("backend.product_routes")
storage_module = importlib.import_module("backend.product_image_storage")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": "test-api-key"}


def _png_bytes(width=40, height=30, color=(200, 30, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def codigo(prefixo="IMG"):
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# A camada de storage local usa o MESMO diretório servido estaticamente
# ---------------------------------------------------------------------------

def test_mount_estatico_serve_do_mesmo_diretorio_do_storage_local():
    assert main.PRODUTOS_UPLOAD_DIR == upload_routes.UPLOAD_DIR
    assert upload_routes.imagem_storage.local_dir == upload_routes.UPLOAD_DIR


def test_storage_remoto_desligado_por_padrao_sem_env():
    config = storage_module.ProductImageStorageConfig.from_env()
    assert config.enabled is False


# ---------------------------------------------------------------------------
# Upload real: valida, normaliza (remove EXIF/orientação) e persiste
# ---------------------------------------------------------------------------

def test_upload_imagem_produto_grava_no_diretorio_persistente_e_retorna_url_publica():
    resposta = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto.png", _png_bytes(), "image/png")},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert corpo["armazenamento"] == "local"
    assert corpo["url"].startswith("/uploads/produtos/")
    nome_arquivo = corpo["filename"]
    caminho_fisico = upload_routes.UPLOAD_DIR / nome_arquivo
    try:
        assert caminho_fisico.is_file()
        # o arquivo servido pelo mount estático é o mesmo gravado pelo upload
        resposta_estatica = client.get(corpo["url"])
        assert resposta_estatica.status_code == 200
        assert resposta_estatica.content == caminho_fisico.read_bytes()
    finally:
        caminho_fisico.unlink(missing_ok=True)


def test_upload_normaliza_imagem_removendo_orientacao_exif():
    buffer = io.BytesIO()
    imagem = Image.new("RGB", (60, 20), (10, 200, 10))
    exif = imagem.getexif()
    exif[274] = 6  # Orientation: rotate 270
    imagem.save(buffer, format="JPEG", exif=exif)
    resposta = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto.jpg", buffer.getvalue(), "image/jpeg")},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    caminho_fisico = upload_routes.UPLOAD_DIR / resposta.json()["filename"]
    try:
        with Image.open(caminho_fisico) as reaberta:
            assert reaberta.getexif().get(274) is None
            # orientação 6 gira 90°: dimensões finais ficam invertidas
            assert reaberta.size == (20, 60)
    finally:
        caminho_fisico.unlink(missing_ok=True)


def test_upload_falha_de_storage_nao_perde_a_imagem_anterior(monkeypatch):
    def _falhar(*args, **kwargs):
        raise storage_module.ProductImageStorageError("storage indisponível")

    monkeypatch.setattr(upload_routes.imagem_storage, "upload", _falhar)
    antes = set(p.name for p in upload_routes.UPLOAD_DIR.iterdir() if p.is_file())
    resposta = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto.png", _png_bytes(), "image/png")},
        headers=HEADERS,
    )
    assert resposta.status_code == 502
    assert "anterior" in resposta.json()["detail"].lower()
    depois = set(p.name for p in upload_routes.UPLOAD_DIR.iterdir() if p.is_file())
    assert antes == depois  # nenhum arquivo órfão foi criado


def test_arquivo_grande_e_rejeitado_antes_de_gravar_no_disco():
    antes = set(p.name for p in upload_routes.UPLOAD_DIR.iterdir() if p.is_file())
    payload_grande = b"\x89PNG\r\n\x1a\n" + os.urandom(upload_routes.MAX_IMAGE_BYTES + 1)
    resposta = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto.png", payload_grande, "image/png")},
        headers=HEADERS,
    )
    assert resposta.status_code == 413
    depois = set(p.name for p in upload_routes.UPLOAD_DIR.iterdir() if p.is_file())
    assert antes == depois


def test_produto_id_com_path_traversal_nao_escapa_do_diretorio_de_upload():
    resposta = client.post(
        "/api/uploads/produtos",
        params={"produto_id": "../../../../etc/cron.d/malicioso"},
        files={"arquivo": ("produto.png", _png_bytes(), "image/png")},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    nome_arquivo = resposta.json()["filename"]
    caminho_fisico = upload_routes.UPLOAD_DIR / nome_arquivo
    try:
        assert ".." not in nome_arquivo
        assert caminho_fisico.parent == upload_routes.UPLOAD_DIR
    finally:
        caminho_fisico.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# is_managed_by_storage: nunca mexe em URLs externas/legadas
# ---------------------------------------------------------------------------

def test_is_managed_by_storage_reconhece_apenas_urls_proprias():
    local_storage = storage_module.ProductImageStorage(local_dir=upload_routes.UPLOAD_DIR)
    assert storage_module.is_managed_by_storage(local_storage, "/uploads/produtos/x.png") is True
    assert storage_module.is_managed_by_storage(local_storage, "https://drive.google.com/uc?id=abc") is False
    assert storage_module.is_managed_by_storage(local_storage, "https://exemplo.com/legado.jpg") is False
    assert storage_module.is_managed_by_storage(local_storage, None) is False


def test_delete_ignora_url_nao_gerenciada_sem_lancar_erro():
    local_storage = storage_module.ProductImageStorage(local_dir=upload_routes.UPLOAD_DIR)
    local_storage.delete("https://drive.google.com/uc?id=abc")  # não deve lançar


# ---------------------------------------------------------------------------
# Storage remoto (S3/R2): validado com um cliente boto3 falso, sem rede real
# ---------------------------------------------------------------------------

class _S3ClienteFalso:
    def __init__(self):
        self.objetos = {}

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl=None):
        self.objetos[Key] = {"body": Body, "content_type": ContentType}

    def delete_object(self, Bucket, Key):
        self.objetos.pop(Key, None)

    def head_object(self, Bucket, Key):
        if Key not in self.objetos:
            raise RuntimeError("NoSuchKey")
        return {}


def _storage_remoto_falso(monkeypatch, tmp_path):
    config = storage_module.ProductImageStorageConfig(
        enabled=True,
        bucket="mistica-produtos-teste",
        endpoint="https://exemplo.r2.cloudflarestorage.com",
        region="auto",
        access_key="chave-teste",  # pragma: allowlist secret
        secret_key="segredo-teste",  # pragma: allowlist secret
        public_base_url="https://cdn.exemplo.com/produtos",
        prefix="produtos",
        timeout=5.0,
    )
    storage = storage_module.ProductImageStorage(local_dir=tmp_path, config=config)
    cliente_falso = _S3ClienteFalso()
    monkeypatch.setattr(storage, "_s3_client", lambda: cliente_falso)
    return storage, cliente_falso


def test_upload_remoto_retorna_url_publica_estavel(monkeypatch, tmp_path):
    storage, cliente = _storage_remoto_falso(monkeypatch, tmp_path)
    resultado = storage.upload(b"conteudo", produto_id="produto x", ext=".jpg", content_type="image/jpeg")
    assert resultado["backend"] == "s3"
    assert resultado["url"].startswith("https://cdn.exemplo.com/produtos/produtos/")
    assert resultado["key"] in cliente.objetos
    assert not (tmp_path / resultado["key"]).exists()  # nada gravado localmente


def test_exists_e_delete_no_storage_remoto(monkeypatch, tmp_path):
    storage, cliente = _storage_remoto_falso(monkeypatch, tmp_path)
    resultado = storage.upload(b"conteudo", produto_id="produto y", ext=".png", content_type="image/png")
    assert storage.exists(resultado["url"]) is True
    storage.delete(resultado["url"])
    assert storage.exists(resultado["url"]) is False


def test_delete_remoto_nao_afeta_url_de_outro_dominio(monkeypatch, tmp_path):
    storage, cliente = _storage_remoto_falso(monkeypatch, tmp_path)
    storage.delete("https://drive.google.com/uc?id=abc")
    assert cliente.objetos == {}


# ---------------------------------------------------------------------------
# Substituição de imagem: a antiga só é removida depois que a nova é
# confirmada no banco, e nunca se for uma URL externa/legada
# ---------------------------------------------------------------------------

def _payload_produto(**overrides):
    payload = {
        "codigo_p": codigo(),
        "nome": "Produto imagem teste",
        "preco": 9.9,
        "custo": 3.0,
        "quantidade": 1,
        "estoque_minimo": 1,
        "imagem_url": None,
        "imagens": [],
    }
    payload.update(overrides)
    return payload


def test_atualizar_produto_remove_imagem_antiga_gerenciada_apos_confirmar_nova(monkeypatch):
    upload = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto.png", _png_bytes(), "image/png")},
        headers=HEADERS,
    )
    assert upload.status_code == 200, upload.text
    url_antiga = f"https://api.misticaesotericos.com.br{upload.json()['url']}"
    caminho_antigo = upload_routes.UPLOAD_DIR / upload.json()["filename"]

    criado = client.post(
        "/api/produtos",
        json=_payload_produto(imagem_url=None),
        headers=HEADERS,
    )
    assert criado.status_code == 200, criado.text
    produto_id = criado.json()["id"]

    chamadas = []
    original_delete = product_routes.imagem_storage.delete

    def _delete_espiao(valor):
        chamadas.append(valor)
        return original_delete(valor)

    monkeypatch.setattr(product_routes.imagem_storage, "delete", _delete_espiao)

    atualizado = client.put(
        f"/api/produtos/{produto_id}",
        json=_payload_produto(codigo_p=None, imagem_url=url_antiga),
        headers=HEADERS,
    )
    assert atualizado.status_code == 200, atualizado.text
    assert chamadas == []  # não havia imagem antiga ainda

    nova_imagem = _png_bytes(color=(1, 2, 3))
    novo_upload = client.post(
        "/api/uploads/produtos",
        params={"produto_id": codigo()},
        files={"arquivo": ("produto2.png", nova_imagem, "image/png")},
        headers=HEADERS,
    )
    assert novo_upload.status_code == 200, novo_upload.text
    caminho_novo = upload_routes.UPLOAD_DIR / novo_upload.json()["filename"]
    url_nova = f"https://api.misticaesotericos.com.br{novo_upload.json()['url']}"

    try:
        segunda_atualizacao = client.put(
            f"/api/produtos/{produto_id}",
            json=_payload_produto(codigo_p=None, imagem_url=url_nova),
            headers=HEADERS,
        )
        assert segunda_atualizacao.status_code == 200, segunda_atualizacao.text
        assert chamadas == [url_antiga]
        assert not caminho_antigo.is_file()  # imagem antiga removida
        assert caminho_novo.is_file()  # imagem nova preservada
    finally:
        caminho_antigo.unlink(missing_ok=True)
        caminho_novo.unlink(missing_ok=True)


def test_atualizar_produto_nao_remove_imagem_externa_legada(monkeypatch):
    criado = client.post(
        "/api/produtos",
        json=_payload_produto(imagem_url="https://exemplo-legado.com/foto-antiga.jpg"),
        headers=HEADERS,
    )
    assert criado.status_code == 200, criado.text
    produto_id = criado.json()["id"]

    chamadas = []
    monkeypatch.setattr(product_routes.imagem_storage, "delete", lambda valor: chamadas.append(valor))

    atualizado = client.put(
        f"/api/produtos/{produto_id}",
        json=_payload_produto(codigo_p=None, imagem_url="https://exemplo-legado.com/foto-nova.jpg"),
        headers=HEADERS,
    )
    assert atualizado.status_code == 200, atualizado.text
    assert chamadas == []  # URL externa nunca é removida por este storage
