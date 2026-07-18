"""Testes da Content Security Policy (CSP) do site público (GitHub Pages).

O site público é publicado via GitHub Pages (ver .github/workflows/deploy-pages.yml,
actions/deploy-pages@v4), que não permite configurar cabeçalhos HTTP
customizados -- por isso a CSP é entregue via
<meta http-equiv="Content-Security-Policy"> em cada página HTML pública,
não por header (a API em backend/main.py já entrega CSP por header, testada
separadamente em tests/test_seguranca_reforcada.py).

Estes testes leem os arquivos HTML diretamente (sem servidor) -- são só
verificações estáticas do conteúdo publicado.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PAGINAS_PUBLICAS = [
    "404.html", "achados-misticos/index.html", "admin-pedidos-pix.html", "admin.html",
    "aromaterapia/index.html", "banhos-de-ervas/index.html", "cristais/index.html",
    "escola-admin.html", "escola-curso.html", "escola-incensos.html",
    "escola-medicinas-floresta.html", "escola.html", "incensos/index.html", "index.html",
    "isis-conteudo-admin.html", "kit.html", "painel/index.html", "painel-operacional.html",
    "politica-de-privacidade.html", "politica-de-trocas.html", "produto.html",
    "termos-de-uso.html", "teste-commerce.html", "velas/index.html",
]


def _ler(pagina: str) -> str:
    return (ROOT / pagina).read_text(encoding="utf-8")


def _csp_de(pagina: str) -> str:
    conteudo = _ler(pagina)
    m = re.search(r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"', conteudo)
    assert m, f"{pagina}: meta CSP não encontrada"
    return m.group(1)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_pagina_tem_meta_csp(pagina):
    """Toda página pública publica uma CSP -- nenhuma fica sem proteção."""
    csp = _csp_de(pagina)
    assert csp.strip()


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_nao_usa_unsafe_eval(pagina):
    assert "unsafe-eval" not in _csp_de(pagina)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_nao_usa_curingas_globais(pagina):
    csp = _csp_de(pagina)
    # Nenhuma diretiva pode valer "*" (qualquer origem) nem usar https: como
    # curinga de src amplo em script/connect/frame -- só em img-src, onde o
    # próprio enunciado do exercício já aceita "https:" (baixo risco: uma
    # imagem não executa JS).
    for diretiva in ("default-src", "script-src", "connect-src", "frame-src", "object-src"):
        m = re.search(rf"{diretiva} ([^;]+);", csp)
        if not m:
            continue
        valores = m.group(1).split()
        assert "*" not in valores, f"{pagina}: {diretiva} usa curinga global"
        if diretiva != "img-src":
            assert "https:" not in valores, f"{pagina}: {diretiva} usa https: como curinga amplo"


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_object_src_none(pagina):
    assert "object-src 'none'" in _csp_de(pagina)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_base_uri_self(pagina):
    assert "base-uri 'self'" in _csp_de(pagina)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_script_src_sem_unsafe_inline(pagina):
    """script-src nunca pode conter 'unsafe-inline'."""
    csp = _csp_de(pagina)
    m = re.search(r"script-src ([^;]+);", csp)
    assert m, f"{pagina}: script-src ausente"
    assert "'unsafe-inline'" not in m.group(1)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_style_src_sem_unsafe_inline(pagina):
    """style-src também não depende de 'unsafe-inline': todo style="" inline
    (fixo ou dinâmico) foi removido em favor de classes CSS dedicadas ou de
    element.style.* via CSSOM (não restrito por CSP) -- ver docs/admin/CSP.md."""
    csp = _csp_de(pagina)
    m = re.search(r"style-src ([^;]+);", csp)
    assert m, f"{pagina}: style-src ausente"
    assert "'unsafe-inline'" not in m.group(1)


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_csp_autoriza_apenas_origens_conhecidas_do_mercado_pago(pagina):
    """script-src/connect-src/frame-src só podem referenciar domínios do
    próprio Mercado Pago -- nunca um host de terceiros.

    script-src fica com o host exato do loader oficial (sdk.mercadopago.com):
    é o único ponto que executa JavaScript, então o mais estrito possível.
    connect-src/frame-src usam curinga de subdomínio (`*.mercadopago.com` e
    `*.mercadopago.com.br`, TLD do Mercado Pago Brasil) -- necessário porque
    o Secure Fields (iframes de número/validade/CVV do CardForm) e as
    chamadas de tokenização/parcelas do SDK não têm um único subdomínio
    documentado nem estável entre países/ambientes (ver docs/admin/CSP.md,
    seção sobre o bug do CardForm sem foco/parcelas). Ainda é um domínio
    restrito ao próprio provedor de pagamento, não um curinga global."""
    csp = _csp_de(pagina)
    script_src = re.search(r"script-src ([^;]+);", csp).group(1)
    for host in re.findall(r"https://([a-zA-Z0-9.-]*mercadopago[a-zA-Z0-9.-]*)", script_src):
        assert host == "sdk.mercadopago.com", f"{pagina}: script-src com host inesperado do Mercado Pago: {host}"
    for diretiva in ("connect-src", "frame-src"):
        m = re.search(rf"{diretiva} ([^;]+);", csp)
        if not m:
            continue
        for host in re.findall(r"https://([a-zA-Z0-9.*-]*mercadopago[a-zA-Z0-9.*-]*)", m.group(1)):
            assert host in {"*.mercadopago.com", "*.mercadopago.com.br"}, (
                f"{pagina}: {diretiva} com host inesperado do Mercado Pago: {host}"
            )


def test_index_permite_sdk_mercadopago_para_tokenizacao():
    csp = _csp_de("index.html")
    assert "https://sdk.mercadopago.com" in csp  # script-src: carrega o SDK
    connect_src = re.search(r"connect-src ([^;]+);", csp).group(1)
    assert "https://*.mercadopago.com" in connect_src  # tokenização/parcelas/emissor


def test_frontend_nunca_referencia_endpoint_privado_de_criacao_de_pagamento_mercadopago():
    """O frontend nunca deve chamar diretamente a API REST privada do
    Mercado Pago para CRIAR pagamentos (isso é exclusivo do backend, com o
    Access Token) -- só os endpoints públicos de tokenização/consulta usados
    pelo próprio SDK no navegador."""
    conteudo = (ROOT / "v2-mercadopago-checkout.js").read_text(encoding="utf-8")
    assert "api.mercadopago.com" not in conteudo
    assert "ACCESS_TOKEN" not in conteudo.upper() or "access_token" not in conteudo.lower()


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_pagina_nao_tem_handlers_inline_onclick_onerror(pagina):
    """Nenhuma página pública deve depender de onclick=/onerror= inline --
    são bloqueados por um script-src sem 'unsafe-inline'."""
    conteudo = _ler(pagina)
    assert not re.search(r'\son(click|error|load|change|submit)="', conteudo), (
        f"{pagina}: ainda tem handler inline, incompatível com a CSP sem unsafe-inline"
    )


@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_pagina_nao_tem_script_inline_executavel(pagina):
    """<script> sem src= só é aceitável quando type= não é JavaScript (ex.:
    application/ld+json, dado inerte, nunca sujeito a script-src)."""
    conteudo = _ler(pagina)
    for m in re.finditer(r"<script(?![^>]*\bsrc=)([^>]*)>", conteudo, re.IGNORECASE):
        atributos = m.group(1)
        tipo_m = re.search(r'type="([^"]*)"', atributos)
        tipo = tipo_m.group(1) if tipo_m else "text/javascript"
        assert tipo in ("application/ld+json", "application/json"), (
            f"{pagina}: <script> inline executável encontrado (type={tipo!r}), incompatível com a CSP"
        )


def test_admin_pages_login_sem_regressao_de_atributos_essenciais():
    """Checagem rápida de que a inserção da meta CSP não corrompeu o head
    de admin.html (login do painel é crítico)."""
    conteudo = _ler("admin.html")
    assert conteudo.count("<head>") == 1
    assert conteudo.count("</head>") == 1
    assert "<title>" in conteudo


def test_frontend_getcart_nunca_expoe_valor_para_pagamento():
    """O schema enviado pelo cartão nunca inclui um campo de valor -- só
    pedido_id/txid/token/parcelas/payer (ver backend/mercadopago_routes.py::
    CartaoPagamentoIn, já teste por test_mercadopago_cartao.py). Aqui só
    confirmamos que o frontend não construiu um campo 'valor'/'total' no
    corpo enviado a /card."""
    conteudo = (ROOT / "v2-mercadopago-checkout.js").read_text(encoding="utf-8")
    corpo_match = re.search(r"const corpo = \{(.*?)\};", conteudo, re.S)
    assert corpo_match, "corpo da requisição de cartão não encontrado"
    corpo_texto = corpo_match.group(1)
    assert "valor" not in corpo_texto.lower()
    assert "total" not in corpo_texto.lower()
