"""Checklist de homologação comercial (Fase 10) -- backend/admin_dashboard_routes.py
+ services/admin_homologacao_service.py.

Garante que a rota exige perfil administrador, que nenhum item devolve
segredo/caminho de disco, e que os indicadores usam só os três níveis
verde/amarelo/vermelho (ou "info" para itens de verificação manual).
"""

from tests.test_pedido_unificado import HEADERS, client

NIVEIS_VALIDOS = {"verde", "amarelo", "vermelho", "info"}


def test_homologacao_exige_autenticacao():
    resposta = client.get("/api/painel/operacoes/homologacao")
    assert resposta.status_code in (401, 403)


def test_homologacao_retorna_checklist_completo():
    resposta = client.get("/api/painel/operacoes/homologacao", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    assert "itens" in dados
    chaves = {item["chave"] for item in dados["itens"]}
    esperadas = {
        "banco", "api", "mercadopago", "pix", "ssl", "backup", "uploads",
        "cursos", "produtos", "pedidos", "emails", "whatsapp", "seo",
        "lighthouse", "webhooks", "sistema",
    }
    assert esperadas.issubset(chaves)

    for item in dados["itens"]:
        assert item["status"] in NIVEIS_VALIDOS
        detalhe = item["detalhe"].lower()
        assert "token" not in detalhe
        assert "chave=" not in detalhe
        assert "/home/" not in detalhe and "c:\\" not in detalhe
