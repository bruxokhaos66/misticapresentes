"""Centro de Operações administrativo (Fases 1, 3 e 10 da homologação).

Cobre apenas leitura: os endpoints novos (backend/admin_dashboard_routes.py)
não gravam em pedidos, estoque ou pagamentos, então os testes verificam
autenticação, formato da resposta e que os números batem com pedidos
criados via o mesmo fluxo público já testado em test_pedido_unificado.py.
"""

from services.admin_dashboard_service import limpar_cache_kpis
from tests.test_pedido_unificado import HEADERS, client, criar_pedido_publico


def test_dashboard_operacional_exige_autenticacao():
    resposta = client.get("/api/painel/operacoes/dashboard")
    assert resposta.status_code in (401, 403)


def test_dashboard_operacional_retorna_kpis_esperados():
    limpar_cache_kpis()
    criar_pedido_publico(41.0)

    resposta = client.get("/api/painel/operacoes/dashboard", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    campos_esperados = {
        "pedidos_aguardando_pagamento",
        "pedidos_pagos_aguardando_envio",
        "pedidos_enviados_hoje",
        "faturamento_hoje",
        "faturamento_mes",
        "ticket_medio_mes",
        "produtos_sem_estoque",
        "produtos_estoque_critico",
        "novos_clientes_hoje",
        "cursos_vendidos_mes",
        "pedidos_pix_mes",
        "pedidos_cartao_mes",
        "campanhas_ativas",
        "alertas",
        "gerado_em",
    }
    assert campos_esperados.issubset(dados.keys())
    assert dados["pedidos_aguardando_pagamento"] >= 1


def test_alertas_operacionais_refletem_pedidos_aguardando_pagamento():
    limpar_cache_kpis()
    criar_pedido_publico(42.0)

    resposta = client.get("/api/painel/operacoes/alertas", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    assert "alertas" in dados
    tipos = {alerta["tipo"] for alerta in dados["alertas"]}
    assert "pedidos_aguardando_pagamento" in tipos


def test_dashboard_operacional_usa_cache_entre_chamadas_proximas():
    limpar_cache_kpis()
    primeira = client.get("/api/painel/operacoes/dashboard", headers=HEADERS).json()
    criar_pedido_publico(43.0)
    segunda = client.get("/api/painel/operacoes/dashboard", headers=HEADERS).json()

    # Enquanto o cache está válido, o novo pedido não deve aparecer ainda --
    # prova que a rota não repete a bateria de consultas a cada chamada.
    assert segunda["gerado_em"] == primeira["gerado_em"]
