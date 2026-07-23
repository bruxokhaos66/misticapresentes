"""Testes da validação de mídia por magic bytes (backend/whatsapp_media_service.py).
Nunca chama a Graph API real -- exercita as funções puras de identificação de
tipo/domínio, e o fluxo completo de download com um transporte HTTP falso
(httpx.MockTransport), comparando os BYTES finais com uma fixture real -- não
apenas se as chamadas HTTP aconteceram."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "token-de-teste-" + uuid.uuid4().hex[:8])

import httpx
import pytest

from backend.whatsapp_media_service import (
    WhatsAppMediaError,
    _host_permitido,
    _identificar_por_magic_bytes,
    baixar_midia,
    extensao_para_mime,
    salvar_midia_local,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

JPEG_MINIMO = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb0043000302020202020302020"
    "2030303030406040404040408060605070605080808080909090808080a0b0c0a"
    "0a0b0a08080b0d0b0b0c0c0c0c0c07090e0f0d0c0e0b0c0c0cffc9000b0800010001010"
    "1001100ffcc000601000101ffda0008010100003f00d2cf20ffd9"
)


def test_frontend_nunca_usa_innerhtml():
    """Defesa em profundidade contra XSS armazenado: nome de perfil e texto
    de mensagem vêm de um cliente do WhatsApp (nunca confiável) e são
    renderizados no painel só via textContent -- innerHTML nunca deve
    aparecer em central-atendimento.js. Guarda de regressão estática."""
    conteudo = (REPO_ROOT / "central-atendimento.js").read_text(encoding="utf-8")
    assert "innerHTML" not in conteudo


def test_jpeg_reconhecido():
    assert _identificar_por_magic_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20) == ("jpg", "image/jpeg")


def test_png_reconhecido():
    assert _identificar_por_magic_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20) == ("png", "image/png")


def test_pdf_reconhecido():
    assert _identificar_por_magic_bytes(b"%PDF-1.4\n" + b"\x00" * 20) == ("pdf", "application/pdf")


def test_webp_reconhecido():
    corpo = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
    assert _identificar_por_magic_bytes(corpo) == ("webp", "image/webp")


def test_svg_disfarcado_de_imagem_e_rejeitado():
    """Um SVG (que pode conter <script>) enviado com mime_type "image/svg+xml"
    falso nunca é aceito -- magic bytes não batem com nenhuma assinatura da
    allowlist."""
    conteudo = b"<?xml version=\"1.0\"?><svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    assert _identificar_por_magic_bytes(conteudo) is None


def test_html_e_rejeitado():
    conteudo = b"<html><body><script>alert(document.cookie)</script></body></html>"
    assert _identificar_por_magic_bytes(conteudo) is None


def test_executavel_elf_e_rejeitado():
    conteudo = b"\x7fELF" + b"\x00" * 20
    assert _identificar_por_magic_bytes(conteudo) is None


def test_riff_sem_webp_e_rejeitado():
    """RIFF é o cabeçalho de vários formatos (AVI, WAV...); só é aceito
    quando os bytes 8-12 confirmam WEBP -- outro contêiner RIFF não deve
    passar disfarçado de imagem."""
    corpo = b"RIFF" + b"\x00\x00\x00\x00" + b"AVI " + b"\x00" * 20
    assert _identificar_por_magic_bytes(corpo) is None


def test_json_de_erro_e_rejeitado():
    conteudo = b'{"error": {"message": "Unsupported", "code": 100}}'
    assert _identificar_por_magic_bytes(conteudo) is None


def test_arquivo_vazio_e_rejeitado():
    assert _identificar_por_magic_bytes(b"") is None


def test_extensao_para_mime_conhecido():
    assert extensao_para_mime("image/jpeg") == "jpg"
    assert extensao_para_mime("image/png") == "png"
    assert extensao_para_mime("image/webp") == "webp"
    assert extensao_para_mime("application/pdf") == "pdf"


def test_extensao_para_mime_desconhecido_cai_em_bin():
    assert extensao_para_mime("application/x-msdownload") == "bin"
    assert extensao_para_mime(None) == "bin"


def test_host_permitido_dominios_da_meta():
    assert _host_permitido("https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=1")
    assert _host_permitido("https://scontent.xx.fbcdn.net/v/abc")
    assert _host_permitido("https://graph.facebook.com/v21.0/123")


def test_host_permitido_rejeita_dominio_arbitrario():
    assert not _host_permitido("https://evil.example.com/malware.exe")
    assert not _host_permitido("https://fbcdn.net.evil.com/x")
    assert not _host_permitido("https://notfbsbx.com/x")


def _transporte_falso(handler):
    return httpx.MockTransport(handler)


def _com_transporte_falso(monkeypatch, handler):
    transporte = _transporte_falso(handler)
    original = httpx.Client

    def cliente_falso(*args, **kwargs):
        kwargs["transport"] = transporte
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", cliente_falso)


def test_baixar_midia_bytes_finais_identicos_a_fixture(monkeypatch):
    """Fluxo completo (metadados -> download autenticado -> magic bytes) com
    HTTP falso -- valida os BYTES finais, não só se a Graph API foi chamada."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            assert request.headers["authorization"].startswith("Bearer ")
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=abc", "file_size": len(JPEG_MINIMO)})
        if "lookaside.fbsbx.com" in str(request.url):
            assert request.headers["authorization"].startswith("Bearer ")
            return httpx.Response(200, content=JPEG_MINIMO, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    _com_transporte_falso(monkeypatch, handler)
    conteudo, extensao, mime = baixar_midia("media-1")
    assert conteudo == JPEG_MINIMO
    assert extensao == "jpg"
    assert mime == "image/jpeg"


def test_baixar_midia_rejeita_html_disfarcado_de_jpeg(monkeypatch):
    html = b"<html><body><script>alert(document.cookie)</script></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": len(html)})
        return httpx.Response(200, content=html, headers={"content-type": "image/jpeg"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-html")
    assert exc.value.codigo == "unsupported_media_type"


def test_baixar_midia_rejeita_json_no_lugar_da_imagem(monkeypatch):
    corpo_json = b'{"error":"nao autorizado"}'

    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": len(corpo_json)})
        return httpx.Response(200, content=corpo_json, headers={"content-type": "application/json"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-json")
    assert exc.value.codigo == "unsupported_media_type"


def test_baixar_midia_rejeita_arquivo_vazio(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": 0})
        return httpx.Response(200, content=b"", headers={"content-type": "image/jpeg"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-vazio")
    assert exc.value.codigo == "empty_media"


def test_baixar_midia_rejeita_acima_do_limite(monkeypatch):
    grande = JPEG_MINIMO + b"\x00" * (10 * 1024 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": len(grande)})
        return httpx.Response(200, content=grande, headers={"content-type": "image/jpeg"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-grande")
    assert exc.value.codigo == "media_too_large"


def test_baixar_midia_rejeita_dominio_fora_da_allowlist(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://evil.example.com/malware.jpg", "file_size": 10})
        return httpx.Response(200, content=JPEG_MINIMO)

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-dominio-ruim")
    assert exc.value.codigo == "invalid_media_domain"


def test_baixar_midia_rejeita_redirect_para_dominio_nao_permitido(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": 10})
        return httpx.Response(302, headers={"location": "https://evil.example.com/steal.jpg"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-redirect-ruim")
    assert exc.value.codigo == "invalid_redirect_domain"


def test_baixar_midia_meta_401(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-401")
    assert exc.value.codigo == "metadata_unavailable"


def test_baixar_midia_meta_404(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-404")
    assert exc.value.codigo == "metadata_unavailable"


def test_baixar_midia_timeout(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout simulado")

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-timeout")
    assert exc.value.codigo == "metadata_request_failed"


def test_baixar_midia_download_interrompido(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/x", "file_size": len(JPEG_MINIMO)})
        raise httpx.ReadError("conexão interrompida simulada")

    _com_transporte_falso(monkeypatch, handler)
    with pytest.raises(WhatsAppMediaError) as exc:
        baixar_midia("media-interrompida")
    assert exc.value.codigo == "download_network_error"


def test_salvar_midia_local_grava_bytes_identicos_e_atomico(tmp_path, monkeypatch):
    monkeypatch.setenv("WHATSAPP_MEDIA_STORAGE_DIR", str(tmp_path))
    caminho = salvar_midia_local(JPEG_MINIMO, "jpg")
    assert Path(caminho).read_bytes() == JPEG_MINIMO
    # nenhum arquivo temporário deve sobrar após a gravação atômica
    restantes = list(tmp_path.glob(".tmp-*"))
    assert restantes == []


def test_salvar_midia_local_nome_gerado_pelo_servidor(tmp_path, monkeypatch):
    """Nunca usa nome vindo de fora -- sempre uuid4, o que também elimina
    path traversal."""
    monkeypatch.setenv("WHATSAPP_MEDIA_STORAGE_DIR", str(tmp_path))
    caminho = salvar_midia_local(JPEG_MINIMO, "jpg")
    nome = Path(caminho).name
    assert ".." not in nome
    assert "/" not in nome
    assert Path(caminho).parent == tmp_path
