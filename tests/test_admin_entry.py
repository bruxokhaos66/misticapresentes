from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_html_e_pagina_separada_com_o_painel():
    admin = (ROOT / "admin.html").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex,nofollow"' in admin
    assert 'id="admin"' in admin
    assert 'id="adminLoginForm"' in admin
    assert 'id="adminContent"' in admin


def test_index_nao_carrega_html_do_admin_no_bundle_publico():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="admin"' not in index
    assert 'id="adminLoginForm"' not in index
    assert 'id="adminContent"' not in index


def test_site_config_redireciona_rotas_antigas_para_admin_html():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert 'window.location.replace("admin.html")' in config
    assert "onAdminPage" in config


def test_site_config_captura_login_admin_antes_do_listener_local():
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    assert 'document.addEventListener("submit"' in config
    assert "event.stopImmediatePropagation()" in config
    assert 'form.id !== "adminLoginForm"' in config
    assert "/api/auth/login" in config
    assert 'credentials: "include"' in config
    assert "X-Mistica-Api-Key" not in config
    # O bloco de captura de login admin (a partir da leitura de
    # window.location.search) nunca deve tocar localStorage: a sessão real é
    # sempre o cookie HttpOnly revalidado em /api/auth/me. Isso não proíbe
    # localStorage no restante do arquivo: o módulo de persistência segura do
    # carrinho (window.misticaSecureStorage, coberto por
    # tests/e2e/localstorage-seguro.spec.js) roda antes deste bloco e é a
    # única gravação de localStorage permitida no site.
    bloco_admin = config.split("const params = new URLSearchParams(window.location.search);", 1)[1]
    assert "localStorage" not in bloco_admin


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


def test_sessao_admin_nao_grava_objeto_completo_no_sessionstorage():
    # A autorização real é sempre via cookie HttpOnly revalidado em
    # /api/auth/me; sessionStorage deve guardar só um flag de UI
    # (misticaAdminUnlocked), nunca o objeto de sessão (nome, perfil,
    # permissões), que seria superfície extra de furto via XSS sem uso
    # funcional (nada nunca lê essa chave de volta).
    config = (ROOT / "site-config.js").read_text(encoding="utf-8")
    painel_auth = (ROOT / "painel-auth.js").read_text(encoding="utf-8")
    for script in (config, painel_auth):
        assert 'setItem("misticaPainelSessao"' not in script
