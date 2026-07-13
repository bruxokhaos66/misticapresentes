"""Valida a sanitização de `link_externo` no modelo ProdutoCompletoIn.

Regra: aceitar exclusivamente URLs https://; preservar vazio/None; rejeitar
http://, protocolos perigosos (javascript:, data:, file:, vbscript:) e URLs
relativas. Não quebrar produtos antigos sem link.
"""
import importlib
import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")

product_routes = importlib.import_module("backend.product_routes")
ProdutoCompletoIn = product_routes.ProdutoCompletoIn


def _criar(link):
    return ProdutoCompletoIn(nome="Produto", link_externo=link)


def test_aceita_https():
    assert _criar("https://shopee.com.br/produto").link_externo == "https://shopee.com.br/produto"


def test_faz_trim_do_https():
    assert _criar("  https://exemplo.com/x  ").link_externo == "https://exemplo.com/x"


def test_preserva_vazio_e_none():
    assert ProdutoCompletoIn(nome="Produto").link_externo is None
    assert _criar(None).link_externo is None
    assert _criar("   ").link_externo is None


@pytest.mark.parametrize(
    "url",
    [
        "http://exemplo.com/x",      # http:// agora é rejeitado
        "HTTP://exemplo.com/x",
        "javascript:alert(1)",
        "data:text/html,<script>",
        "file:///etc/passwd",
        "vbscript:msgbox(1)",
        "//evil.com/x",              # relativa (protocol-relative)
        "/caminho/relativo",
        "ftp://exemplo.com/x",
        "exemplo.com/x",
    ],
)
def test_rejeita_http_protocolos_perigosos_e_relativos(url):
    with pytest.raises(ValidationError):
        _criar(url)
