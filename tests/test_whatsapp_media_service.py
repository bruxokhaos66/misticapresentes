"""Testes da validação de mídia por magic bytes (backend/whatsapp_media_service.py).
Nunca chama a Graph API real -- só exercita a função pura de identificação de
tipo, que é o que decide se um arquivo é aceito ou rejeitado."""
from __future__ import annotations

from backend.whatsapp_media_service import _identificar_por_magic_bytes


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
