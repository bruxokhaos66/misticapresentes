"""Armazenamento de imagens do Estúdio de Conteúdo (backend/isis_content_storage.py):
validação de MIME real, tamanho, extensão, integridade e proteção contra
path traversal (o nome do arquivo final nunca vem de fora)."""
import io

import pytest
from PIL import Image

from backend import isis_content_storage as storage


def _png_bytes(largura=100, altura=100):
    buffer = io.BytesIO()
    Image.new("RGB", (largura, altura), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_variante_invalida_e_rejeitada():
    with pytest.raises(storage.IsisContentStorageError, match="Variante"):
        storage.salvar_asset(_png_bytes(), draft_id=1, variante="quadrado", content_type="image/png")


def test_content_type_nao_permitido_e_rejeitado():
    with pytest.raises(storage.IsisContentStorageError, match="Formato inválido"):
        storage.salvar_asset(_png_bytes(), draft_id=1, variante="feed", content_type="image/gif")


def test_arquivo_vazio_e_rejeitado():
    with pytest.raises(storage.IsisContentStorageError, match="vazio"):
        storage.salvar_asset(b"", draft_id=1, variante="feed", content_type="image/png")


def test_arquivo_maior_que_o_limite_e_rejeitado(monkeypatch):
    monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(storage.IsisContentStorageError, match="grande"):
        storage.salvar_asset(_png_bytes(), draft_id=1, variante="feed", content_type="image/png")


def test_conteudo_que_nao_e_imagem_real_e_rejeitado_mesmo_com_content_type_correto():
    dados_falsos = b"isto nao e uma imagem, so texto disfarcado de png"
    with pytest.raises(storage.IsisContentStorageError, match="não é uma imagem válida"):
        storage.validar_imagem_real(dados_falsos, "image/png")


def test_content_type_declarado_nao_bate_com_formato_real_e_rejeitado():
    dados_png_reais = _png_bytes()
    with pytest.raises(storage.IsisContentStorageError, match="não corresponde"):
        storage.validar_imagem_real(dados_png_reais, "image/jpeg")


def test_salvar_asset_com_sucesso_usa_dimensoes_da_variante(tmp_path, monkeypatch):
    monkeypatch.setenv("ISIS_CONTENT_IMAGES_LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "_storage", None)
    resultado = storage.salvar_asset(_png_bytes(), draft_id=42, variante="feed", content_type="image/png")
    assert resultado["mime_type"] == "image/png"
    assert resultado["hash_sha256"]
    assert resultado["arquivo"].startswith("/uploads/produtos/")


def test_nome_do_arquivo_final_nunca_e_influenciado_por_entrada_externa(tmp_path, monkeypatch):
    """O storage nunca usa um nome vindo de fora (draft_id, variante) como
    nome de arquivo em disco -- só como parte do namespace da chave, que é
    sempre finalizada com um uuid gerado internamente
    (`ProductImageStorage.build_key`). Um draft_id malicioso tentando path
    traversal não consegue escapar do diretório de destino."""
    monkeypatch.setenv("ISIS_CONTENT_IMAGES_LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "_storage", None)
    resultado = storage.salvar_asset(_png_bytes(), draft_id="../../etc/passwd", variante="feed", content_type="image/png")
    caminho_gerado = tmp_path / resultado["arquivo"].rsplit("/", 1)[-1]
    assert caminho_gerado.exists()
    assert ".." not in resultado["arquivo"]
    arquivos_fora = list(tmp_path.parent.glob("passwd*"))
    assert arquivos_fora == []
