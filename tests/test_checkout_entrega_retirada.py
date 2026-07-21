"""Fase 3 — entrega ou retirada no checkout.

Cobre a regra de frete centralizada (backend/frete.py), a obrigatoriedade da
escolha no checkout público, a normalização de cidade/UF, a idempotência
diferenciando modalidade/endereço, e a compatibilidade entre status
comercial e modalidade no painel administrativo.
"""

import importlib
import os
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key-fase3")
os.environ.setdefault("MISTICA_SYNC_KEY", os.environ["MISTICA_SITE_API_KEY"])
os.environ["MISTICA_PIX_KEY"] = os.environ.get("MISTICA_PIX_KEY") or "fase3-entrega@example.com"

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    n = uuid.uuid4().int
    return f"203.0.{(n >> 8) % 256}.{n % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float = 50.0, quantidade: int = 20) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Fase 3", "codigo_p": codigo_unico("F3"), "preco": preco, "quantidade": quantidade, "categoria": "Testes"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def checkout(produto: dict, payload_extra: dict, *, quantidade: int = 1):
    payload = {
        "cliente": "Cliente Fase 3",
        "telefone": "11999998888",
        "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        **payload_extra,
    }
    return client.post(
        "/api/checkout/pedidos",
        json=payload,
        headers={"X-Forwarded-For": ip_unico()},
    )


def endereco_entrega(cidade: str, uf: str, **overrides) -> dict:
    base = {
        "forma_recebimento": "entrega",
        "endereco_cep": "89890000",
        "endereco_rua": "Rua das Flores",
        "endereco_numero": "123",
        "endereco_bairro": "Centro",
        "endereco_cidade": cidade,
        "endereco_uf": uf,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1-4: retirada
# ---------------------------------------------------------------------------


def test_retirada_grava_forma_recebimento_retirada():
    produto = criar_produto()
    resposta = checkout(produto, {"forma_recebimento": "retirada"})
    assert resposta.status_code == 200, resposta.text
    pedido_id = resposta.json()["id"]
    detalhe = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    assert detalhe["forma_recebimento"] == "retirada"


def test_retirada_tem_frete_zero():
    produto = criar_produto(preco=99.0)
    resposta = checkout(produto, {"forma_recebimento": "retirada"})
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 0.0
    assert dados["total_final"] == dados["subtotal"]


def test_retirada_nao_exige_endereco():
    produto = criar_produto()
    resposta = checkout(produto, {"forma_recebimento": "retirada"})
    assert resposta.status_code == 200, resposta.text


def test_retirada_limpa_endereco_enviado_indevidamente():
    produto = criar_produto()
    resposta = checkout(
        produto,
        {
            "forma_recebimento": "retirada",
            "endereco_cep": "89890000",
            "endereco_rua": "Rua Indevida",
            "endereco_numero": "1",
            "endereco_bairro": "Bairro",
            "endereco_cidade": "Pinhalzinho",
            "endereco_uf": "SC",
        },
    )
    assert resposta.status_code == 200, resposta.text
    pedido_id = resposta.json()["id"]
    detalhe = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    assert detalhe["endereco_rua"] is None
    assert detalhe["endereco_cidade"] is None
    assert detalhe["frete"] == 0.0


# ---------------------------------------------------------------------------
# 5-7: validação de entrega
# ---------------------------------------------------------------------------


def test_entrega_exige_endereco_completo():
    produto = criar_produto()
    resposta = checkout(produto, {"forma_recebimento": "entrega"})
    assert resposta.status_code == 422, resposta.text


def test_entrega_rejeita_cep_invalido():
    produto = criar_produto()
    resposta = checkout(produto, endereco_entrega("Pinhalzinho", "SC", endereco_cep="123"))
    assert resposta.status_code == 422, resposta.text


def test_entrega_rejeita_uf_invalida():
    produto = criar_produto()
    resposta = checkout(produto, endereco_entrega("Pinhalzinho", "ZZ"))
    assert resposta.status_code == 422, resposta.text


# ---------------------------------------------------------------------------
# 8-11: regra de frete e normalização
# ---------------------------------------------------------------------------


def test_entrega_em_pinhalzinho_sc_tem_frete_gratis():
    produto = criar_produto(preco=40.0)
    resposta = checkout(produto, endereco_entrega("Pinhalzinho", "SC"))
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 0.0
    assert dados["total_final"] == dados["subtotal"]
    assert dados["prazo_entrega_dias_uteis"]


def test_entrega_outra_cidade_de_sc_cobra_30():
    produto = criar_produto(preco=40.0)
    resposta = checkout(produto, endereco_entrega("Chapecó", "SC"))
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 30.0
    assert dados["total_final"] == round(dados["subtotal"] + 30.0, 2)


def test_entrega_fora_de_sc_cobra_50():
    produto = criar_produto(preco=40.0)
    resposta = checkout(produto, endereco_entrega("Curitiba", "PR"))
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 50.0
    assert dados["total_final"] == round(dados["subtotal"] + 50.0, 2)


def test_diferencas_de_acentos_caixa_e_espacos_nao_burlam_regra():
    produto = criar_produto(preco=10.0)
    variações = [" PINHALZINHO ", "pinhalzinho", "Pínhalzinho", "PinhalZinho"]
    for cidade in variações:
        resposta = checkout(produto, endereco_entrega(cidade, " sc "))
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["frete"] == 0.0, cidade


# ---------------------------------------------------------------------------
# 12-13: servidor é a fonte autoritativa
# ---------------------------------------------------------------------------


def test_frete_enviado_pelo_navegador_e_ignorado():
    produto = criar_produto(preco=40.0)
    payload = endereco_entrega("Curitiba", "PR")
    payload["frete"] = 0.0
    payload["total_final"] = 1.0
    resposta = checkout(produto, payload)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 50.0
    assert dados["total_final"] == round(dados["subtotal"] + 50.0, 2)


def test_total_final_inclui_o_frete():
    produto = criar_produto(preco=123.45)
    resposta = checkout(produto, endereco_entrega("Curitiba", "PR"))
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["total_final"] == round(dados["subtotal"] - dados["desconto"] + dados["frete"], 2)


# ---------------------------------------------------------------------------
# 14: cupom de frete grátis
# ---------------------------------------------------------------------------


def _criar_campanha_frete_gratis() -> str:
    from datetime import datetime, timedelta

    from backend.database import conectar

    codigo = f"FRETEGRATIS{uuid.uuid4().hex[:6].upper()}"
    agora = datetime.now()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO campanhas (titulo, tipo, valor, codigo_cupom, ativo, data_inicio, data_fim, criado_em)
            VALUES (?,?,?,?,1,?,?,?)
            """,
            (
                "Frete grátis Fase 3",
                "frete_gratis",
                0,
                codigo,
                (agora - timedelta(days=1)).isoformat(timespec="seconds"),
                (agora + timedelta(days=30)).isoformat(timespec="seconds"),
                agora.isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return codigo


def test_cupom_frete_gratis_zera_o_frete_da_entrega():
    produto = criar_produto(preco=60.0)
    cupom = _criar_campanha_frete_gratis()
    payload = endereco_entrega("Curitiba", "PR")
    payload["cupom"] = cupom
    resposta = checkout(produto, payload)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["frete"] == 0.0
    assert dados["frete_gratis"] is True
    assert dados["total_final"] == dados["subtotal"]


# ---------------------------------------------------------------------------
# 17-18: painel administrativo / pedidos antigos
# ---------------------------------------------------------------------------


def test_pedido_aparece_corretamente_no_painel():
    produto = criar_produto(preco=70.0)
    resposta = checkout(produto, endereco_entrega("Chapecó", "SC"))
    pedido_id = resposta.json()["id"]
    detalhe = client.get(f"/api/pedidos/{pedido_id}/detalhes-admin", headers=HEADERS)
    assert detalhe.status_code == 200, detalhe.text
    dados = detalhe.json()
    assert dados["forma_recebimento"] == "entrega"
    assert dados["endereco_cidade"] == "Chapecó"
    assert dados["endereco_uf"] == "SC"
    assert dados["frete"] == 30.0


def test_pedido_antigo_continua_sem_modalidade_inventada():
    from backend.database import conectar

    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO pedidos (cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                                  forma_pagamento, vendedor, status, data_iso, dia_operacional, origem)
            VALUES ('Cliente legado', '11999990000', '01/01/2020 10:00:00', 10.0, 0, 0, 10.0,
                    'Pix site/celular', 'Site/Celular', 'Pagamento confirmado', '2020-01-01T10:00:00', '2020-01-01', 'site')
            """
        )
        pedido_id = int(cur.lastrowid)
        conn.commit()

    detalhe = client.get(f"/api/pedidos/{pedido_id}/detalhes-admin", headers=HEADERS)
    assert detalhe.status_code == 200, detalhe.text
    assert detalhe.json()["forma_recebimento"] is None


# ---------------------------------------------------------------------------
# 19-20: idempotência
# ---------------------------------------------------------------------------


def test_idempotencia_diferencia_modalidades_com_mesmo_carrinho():
    produto = criar_produto(preco=25.0, quantidade=10)
    chave = str(uuid.uuid4())
    payload_base = {
        "cliente": "Cliente Fase 3",
        "telefone": "11999998888",
        "itens": [{"produto_id": produto["id"], "quantidade": 1}],
    }
    headers = {"X-Forwarded-For": ip_unico(), "Idempotency-Key": chave}

    r1 = client.post("/api/checkout/pedidos", json={**payload_base, "forma_recebimento": "retirada"}, headers=headers)
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/checkout/pedidos",
        json={**payload_base, **endereco_entrega("Curitiba", "PR")},
        headers=headers,
    )
    # Mesma chave, payload de idempotência diferente (modalidade/endereço
    # mudou) -> conflito, nunca reaproveita a resposta do primeiro pedido.
    assert r2.status_code == 409, r2.text
    assert r1.json()["id"] != None


def test_duplo_clique_com_mesma_modalidade_nao_duplica_pedido():
    produto = criar_produto(preco=25.0, quantidade=10)
    chave = str(uuid.uuid4())
    payload = {
        "cliente": "Cliente Fase 3",
        "telefone": "11999998888",
        "forma_recebimento": "retirada",
        "itens": [{"produto_id": produto["id"], "quantidade": 1}],
    }
    headers = {"X-Forwarded-For": ip_unico(), "Idempotency-Key": chave}

    r1 = client.post("/api/checkout/pedidos", json=payload, headers=headers)
    r2 = client.post("/api/checkout/pedidos", json=payload, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# 22: prazo só aparece na entrega
# ---------------------------------------------------------------------------


def test_prazo_de_entrega_aparece_somente_na_entrega():
    produto = criar_produto()
    retirada = checkout(produto, {"forma_recebimento": "retirada"})
    assert retirada.json()["prazo_entrega_dias_uteis"] is None

    entrega = checkout(produto, endereco_entrega("Pinhalzinho", "SC"))
    assert entrega.json()["prazo_entrega_dias_uteis"] == "5 a 10 dias úteis"


# ---------------------------------------------------------------------------
# 25: status incompatível com a modalidade é rejeitado
# ---------------------------------------------------------------------------


def _avancar(pedido_id: int, destino: str):
    return client.patch(
        f"/api/pedidos/{pedido_id}/status-comercial",
        json={"status_pedido": destino},
        headers=HEADERS,
    )


def test_pedido_retirada_nao_pode_ser_marcado_como_enviado():
    produto = criar_produto()
    pedido_id = checkout(produto, {"forma_recebimento": "retirada"}).json()["id"]
    assert _avancar(pedido_id, "confirmado").status_code == 200
    assert _avancar(pedido_id, "em_preparacao").status_code == 200
    resposta = _avancar(pedido_id, "enviado")
    assert resposta.status_code == 409
    assert "entrega" in resposta.json()["detail"].lower()


def test_pedido_entrega_nao_pode_ser_marcado_como_pronto_retirada():
    produto = criar_produto()
    pedido_id = checkout(produto, endereco_entrega("Pinhalzinho", "SC")).json()["id"]
    assert _avancar(pedido_id, "confirmado").status_code == 200
    assert _avancar(pedido_id, "em_preparacao").status_code == 200
    resposta = _avancar(pedido_id, "pronto_retirada")
    assert resposta.status_code == 409
    assert "retirada" in resposta.json()["detail"].lower()


def test_checkout_publico_exige_escolha_de_modalidade():
    produto = criar_produto()
    resposta = checkout(produto, {})
    assert resposta.status_code == 400, resposta.text
