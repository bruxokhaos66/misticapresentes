from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FRONTEND_FILES = [
    ROOT / "site-config.js",
    ROOT / "mobile-sync.js",
    ROOT / "index.html",
    ROOT / "painel-auth.js",
    ROOT / "painel-operacional.html",
    ROOT / "site-production-guard.js",
]

FORBIDDEN_BROWSER_SECRET_MARKERS = (
    "siteApiKey",
    "X-Mistica-Api-Key",
    "MISTICA_SITE_API_KEY",
    "MISTICA_SYNC_KEY",
    "Salvar chave neste navegador",
    "configurar a chave da API do site",
)


def test_frontend_publico_nao_contem_fluxo_de_chave_global():
    for path in PUBLIC_FRONTEND_FILES:
        content = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_BROWSER_SECRET_MARKERS:
            assert marker not in content, f"Segredo/fluxo legado encontrado em {path.name}: {marker}"


def test_checkout_publico_existe_sem_header_de_segredo():
    source = (ROOT / "backend" / "product_routes.py").read_text(encoding="utf-8")
    assert '@router.post("/checkout/pedidos"' in source
    route_block = source.split('@router.post("/checkout/pedidos"', 1)[1].split('@router.post("/produtos")', 1)[0]
    assert "Header(" not in route_block
    assert "x_mistica_api_key" not in route_block
    assert "_chave_interna_checkout()" in route_block


def test_guard_legado_de_chave_foi_removido():
    assert not (ROOT / "site-write-key-guard.js").exists()


def test_botao_gerar_pix_usa_checkout_publico_sem_chave():
    """Regressão: o botão real de checkout (site-production-guard.js) precisa
    chamar a rota pública /api/checkout/pedidos, nunca /api/vendas (que exige
    uma chave que o navegador nunca deve ter) -- ver sendSaleToApi()."""
    source = (ROOT / "site-production-guard.js").read_text(encoding="utf-8")
    assert '"/api/checkout/pedidos"' in source
    assert '"/api/vendas"' not in source
