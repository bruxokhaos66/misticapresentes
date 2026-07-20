"""Fase 1/3/10: páginas novas do Centro de Operações e da Homologação.

Cobre apenas os arquivos estáticos (a suíte de backend já cobre as rotas em
tests/test_admin_dashboard_operacional.py e tests/test_admin_homologacao.py):
existência dos arquivos, ausência de localStorage/innerHTML (mesma regra já
aplicada a admin-pedidos.js em tests/test_admin_pedidos_fase2.py) e presença
dos filtros rápidos de pedidos pedidos na Fase 2.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def ler(nome: str) -> str:
    return (RAIZ / nome).read_text(encoding="utf-8")


def test_paginas_novas_existem():
    for nome in (
        "admin-operacoes.html", "admin-operacoes.css", "admin-operacoes.js",
        "admin-homologacao.html", "admin-homologacao.css", "admin-homologacao.js",
    ):
        assert (RAIZ / nome).exists(), nome


def test_paginas_novas_nao_guardam_pii_localmente():
    for nome in ("admin-operacoes.js", "admin-homologacao.js"):
        js = ler(nome).lower()
        assert "localstorage" not in js
        assert "sessionstorage" not in js
        assert ".innerhtml" not in js


def test_admin_html_linka_as_paginas_novas():
    html = ler("admin.html")
    assert 'href="admin-operacoes.html"' in html
    assert 'href="admin-homologacao.html"' in html


def test_pedidos_ganhou_filtros_rapidos_fase2():
    html = ler("admin-pedidos.html")
    js = ler("admin-pedidos.js")
    for atributo in ("data-periodo=\"hoje\"", "data-periodo=\"ontem\"", "data-periodo=\"7dias\"", "data-periodo=\"30dias\""):
        assert atributo in html
    for atributo in ("data-estado=\"pago\"", "data-estado=\"pendente\"", "data-estado=\"cancelado\"", "data-estado=\"enviado\"", "data-estado=\"pix\"", "data-estado=\"cartao\""):
        assert atributo in html
    assert "pedidoAtendeFiltroRapido" in js
    assert ".innerhtml" not in js.lower()
