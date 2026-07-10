from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_tem_entrada_direta():
    admin = (ROOT / "admin.html").read_text(encoding="utf-8")
    assert "?admin=mistica" in admin
    assert "#admin" in admin
    assert 'name="robots" content="noindex,nofollow"' in admin
    assert "admin-separated-final" in admin


def test_painel_auth_inicializa_mesmo_apos_load():
    script = (ROOT / "painel-auth.js").read_text(encoding="utf-8")
    assert 'document.readyState === "loading"' in script
    assert "inicializarAdmin();" in script
    assert 'params.get("admin") === "mistica"' in script


def test_site_config_bloqueia_listener_local_antes_do_app():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert "HTMLFormElement.prototype.addEventListener" in config
    assert 'type === "submit"' in config
    assert 'this.id === "adminLoginForm"' in config
    assert "legacySubmitBlocked" in config
    assert "admin-api-login-bootstrap.js" in config
    assert "admin-separated-final" in config


def test_bootstrap_carrega_painel_auth_sem_login_local():
    bootstrap = (ROOT / "admin-api-login-bootstrap.js").read_text(encoding="utf-8")
    assert "cloneNode(true)" in bootstrap
    assert "form.replaceWith(clone)" in bootstrap
    assert "painel-auth.js" in bootstrap
    assert "localStorage" not in bootstrap
