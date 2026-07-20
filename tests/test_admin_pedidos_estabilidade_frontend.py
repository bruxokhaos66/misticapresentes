from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ler(nome: str) -> str:
    return (ROOT / nome).read_text(encoding="utf-8")


def test_script_de_estabilidade_carrega_antes_do_painel():
    html = ler("admin-pedidos.html")
    estabilidade = html.index('src="admin-pedidos-estabilidade.js"')
    painel = html.index('src="admin-pedidos.js"')
    logistica = html.index('src="admin-pedidos-logistica.js"')
    assert estabilidade < painel < logistica


def test_lista_e_filtro_nao_sao_reconstruidos_quando_conteudo_nao_muda():
    js = ler("admin-pedidos-estabilidade.js")
    assert "assinaturaNos(atuais) === assinaturaNos(novosNos)" in js
    assert "assinaturaAtual === assinaturaNova" in js
    assert "queueMicrotask" in js
    assert "preventScroll: true" in js
    assert "innerHTML =" not in js


def test_logistica_cancela_raf_duplicado_e_valida_dialogo_atual():
    js = ler("admin-pedidos-logistica.js")
    assert "cancelAnimationFrame(rafMontagem)" in js
    assert "pedidoIdAtual() === pedidoId" in js
    assert "dialog.open" in js
    assert "carregamentos.has(pedidoId)" in js
    assert "innerHTML" not in js


def test_css_nao_depende_de_has_para_textarea():
    css = ler("admin-pedidos-logistica.css")
    js = ler("admin-pedidos-logistica.js")
    assert ":has(" not in css
    assert ".admin-logistica-campo-largo" in css
    assert "criarCampo(\"Observação logística\", observacao, true)" in js
