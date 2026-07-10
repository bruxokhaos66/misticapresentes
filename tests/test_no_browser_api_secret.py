from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FRONTEND_FILES = [
    ROOT / "site-config.js",
    ROOT / "mobile-sync.js",
    ROOT / "index.html",
    ROOT / "painel-auth.js",
    ROOT / "painel-operacional.html",
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
