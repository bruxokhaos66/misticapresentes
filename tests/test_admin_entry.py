from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_tem_entrada_direta():
    admin = (ROOT / "admin.html").read_text(encoding="utf-8")
    assert "?admin=mistica" in admin
    assert "#admin" in admin
    assert 'name="robots" content="noindex,nofollow"' in admin
    assert "admin-separated-final" in admin


def test_site_config_captura_login_admin_antes_do_listener_local():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert 'document.addEventListener("submit"' in config
    assert "event.stopImmediatePropagation()" in config
    assert 'form.id !== "adminLoginForm"' in config
    assert "/api/auth/login" in config
    assert 'credentials: "include"' in config
    assert "X-Mistica-Api-Key" not in config
    assert "localStorage" not in config


def test_site_config_restaura_sessao_no_servidor():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert "/api/auth/me" in config
    assert "liberarPainel" in config
    assert "misticaAdminUnlocked" in config


def test_painel_auth_continua_sem_segredo_no_navegador():
    script = (ROOT / "painel-auth.js").read_text(encoding="utf-8")
    assert "/api/auth/login" in script
    assert 'credentials: "include"' in script
    assert "X-Mistica-Api-Key" not in script
