from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_tem_entrada_direta():
    admin = (ROOT / "admin.html").read_text(encoding="utf-8")
    assert "?admin=mistica" in admin
    assert "#admin" in admin
    assert 'name="robots" content="noindex,nofollow"' in admin


def test_painel_auth_inicializa_mesmo_apos_load():
    script = (ROOT / "painel-auth.js").read_text(encoding="utf-8")
    assert 'document.readyState === "loading"' in script
    assert "inicializarAdmin();" in script
    assert 'params.get("admin") === "mistica"' in script


def test_site_config_carrega_auth_explicitamente():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert 'loadScript("painelAuthScript"' in config
    assert "painel-auth.js?v=20260710-admin-entry-fix" in config
