from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_site_config_carrega_bootstrap_do_admin_api():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert "admin-api-login-bootstrap.js" in config
    assert 'loadScript("painelAuthScript"' not in config


def test_bootstrap_remove_listeners_legados_antes_do_login_api():
    bootstrap = (ROOT / "admin-api-login-bootstrap.js").read_text(encoding="utf-8")
    assert "cloneNode(true)" in bootstrap
    assert "form.replaceWith(clone)" in bootstrap
    assert "painel-auth.js" in bootstrap


def test_frontend_nao_orienta_login_admin_local():
    bootstrap = (ROOT / "admin-api-login-bootstrap.js").read_text(encoding="utf-8")
    assert "localStorage" not in bootstrap
    assert "X-Mistica-Api-Key" not in bootstrap
