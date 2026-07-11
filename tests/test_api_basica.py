import importlib
import os
import uuid

from fastapi.testclient import TestClient


def codigo_unico(prefixo: str) -> str:
    # O banco usado nos testes é o mesmo arquivo persistente entre execuções (não há
    # isolamento por tmp_path aqui), então usamos um sufixo aleatório para não colidir
    # com codigo_p de execuções anteriores.
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()  # garante que o evento de startup (migrações) rode antes dos testes
PROTECTED_HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def test_health_online():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app"] == "Mística Presentes"


def test_status_online():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["api"] == "mistica"
    assert data["app"] == "Mística Presentes"
    assert "timestamp" in data
    assert "data_hora" in data


def test_diagnostico_sistema_responde():
    response = client.get("/api/diagnostico/sistema", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Mística Presentes"
    assert data["status"] in ["ok", "verificar"]
    assert "banco" in data
    assert "tabelas" in data


def test_backup_status_responde():
    response = client.get("/api/backup/status", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "banco_existe" in data
    assert "backup_dir" in data
    assert "ultimos_backups" in data


def test_playlist_ambiente_responde():
    response = client.get("/api/site/playlist-ambiente")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "links" in data
    assert isinstance(data["links"], list)


def test_playlist_ambiente_salva_links_youtube():
    payload = {"links": ["https://www.youtube.com/watch?v=abc123", "https://example.com/ignorar"]}
    response = client.post("/api/site/playlist-ambiente", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["links"] == ["https://www.youtube.com/watch?v=abc123"]

    response_get = client.get("/api/site/playlist-ambiente")
    assert response_get.status_code == 200
    assert response_get.json()["links"] == ["https://www.youtube.com/watch?v=abc123"]


def test_listagem_musicas_ambiente_responde():
    response = client.get("/api/uploads/musicas")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "musicas" in data
    assert isinstance(data["musicas"], list)


def test_upload_musica_ambiente_responde_rapido_e_salva_arquivo():
    response = client.post(
        "/api/uploads/musicas",
        files={"arquivo": ("teste.mp3", b"ID3teste", "audio/mpeg")},
        data={"nome_base": "teste-ambiente"},
        headers=PROTECTED_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["armazenamento"] == "arquivo+backup_banco"
    assert data["url"].startswith("/api/uploads/musicas/arquivo-local/")

    arquivo = client.get(data["url"])
    assert arquivo.status_code == 200
    assert arquivo.content == b"ID3teste"


def test_listar_clientes_exige_chave_api():
    response = client.get("/api/clientes")
    assert response.status_code == 403

    response = client.get("/api/clientes", headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403

    response = client.get("/api/clientes", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_criar_cliente_exige_chave_api_e_persiste():
    payload = {"nome": f"Cliente {codigo_unico('teste')}", "telefone": "(49) 99999-0000", "cpf": "12345678901", "endereco": "Rua Teste, 1"}

    response = client.post("/api/clientes", json=payload)
    assert response.status_code == 403

    response = client.post("/api/clientes", json=payload, headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403

    response = client.post("/api/clientes", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "criado"
    assert data["id"]

    response = client.get("/api/clientes", headers=PROTECTED_HEADERS, params={"busca": payload["nome"]})
    assert response.status_code == 200
    encontrados = response.json()
    assert any(c["nome"] == payload["nome"] and c["cpf"] == payload["cpf"] for c in encontrados)


def test_criar_cliente_exige_nome_e_telefone():
    response = client.post("/api/clientes", json={"nome": "", "telefone": ""}, headers=PROTECTED_HEADERS)
    assert response.status_code == 422


def test_listar_vendas_exige_chave_api():
    response = client.get("/api/vendas")
    assert response.status_code == 403

    response = client.get("/api/vendas", headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403

    response = client.get("/api/vendas", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_criar_venda_exige_chave_api():
    payload = {"cliente": "Cliente", "itens": [{"nome_p": "Item", "quantidade": 1}]}
    response = client.post("/api/vendas", json=payload)
    assert response.status_code == 403

    response = client.post("/api/vendas", json=payload, headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403


def test_painel_dashboard_e_resumo_exigem_sessao_ou_chave_api():
    for caminho in ("/api/painel/resumo", "/api/painel/dashboard"):
        response = client.get(caminho)
        assert response.status_code == 401, caminho

        response = client.get(caminho, headers={"X-Mistica-Api-Key": "chave-errada"})
        assert response.status_code == 401, caminho

        response = client.get(caminho, headers=PROTECTED_HEADERS)
        assert response.status_code == 200, caminho


def test_listar_pedidos_e_pagamentos_exigem_sessao_ou_chave_api():
    for caminho in ("/api/pedidos", "/api/pedidos/status-log", "/api/pagamentos"):
        response = client.get(caminho)
        assert response.status_code == 401, caminho

        response = client.get(caminho, headers=PROTECTED_HEADERS)
        assert response.status_code == 200, caminho


def test_sync_venda_exige_chave_sync():
    payload = {"cliente": "Cliente", "itens": []}
    response = client.post("/api/sync/venda", json=payload)
    assert response.status_code == 403

    response = client.post("/api/sync/venda", json=payload, headers={"X-Mistica-Sync-Key": "chave-errada"})
    assert response.status_code == 403


def test_venda_rejeita_quantidade_negativa():
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Quantidade", "codigo_p": codigo_unico("QTD"), "preco": 10.0, "quantidade": 5},
        headers=PROTECTED_HEADERS,
    ).json()
    payload = {
        "cliente": "Cliente",
        "itens": [{"produto_id": produto["id"], "quantidade": -3}],
    }
    response = client.post("/api/vendas", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 422


def test_venda_recalcula_precos_e_ignora_valores_do_cliente():
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Preco", "codigo_p": codigo_unico("PRC"), "preco": 100.0, "quantidade": 10},
        headers=PROTECTED_HEADERS,
    ).json()
    payload = {
        "cliente": "Cliente",
        "subtotal": 1,
        "total_final": 1,
        "status": "Aguardando pagamento",
        "baixa_estoque": True,
        "itens": [{"produto_id": produto["id"], "quantidade": 2, "valor_unitario": 1, "valor_total": 1}],
    }
    response = client.post("/api/vendas", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["subtotal"] == 200.0
    assert data["total_final"] == 200.0
    # Reserva de estoque: o pedido pendente já baixa o estoque na criação, para
    # não vender o mesmo item para dois clientes enquanto o Pix não é pago.
    assert data["estoque_baixado"] is True

    produto_apos = client.get(f"/api/produtos/{produto['id']}").json()
    assert produto_apos["quantidade"] == 8


def test_estoque_reservado_na_criacao_e_nao_baixa_de_novo_na_confirmacao():
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Pagamento", "codigo_p": codigo_unico("PAG"), "preco": 50.0, "quantidade": 4},
        headers=PROTECTED_HEADERS,
    ).json()
    venda = client.post(
        "/api/vendas",
        json={
            "cliente": "Cliente",
            "status": "Aguardando pagamento",
            "baixa_estoque": True,
            "itens": [{"produto_id": produto["id"], "quantidade": 2}],
        },
        headers=PROTECTED_HEADERS,
    ).json()

    # A reserva de estoque já baixa a quantidade na criação do pedido pendente.
    produto_antes = client.get(f"/api/produtos/{produto['id']}").json()
    assert produto_antes["quantidade"] == 2

    pagamento = client.post(
        "/api/pagamentos",
        json={"venda_id": venda["id"], "valor": 100.0, "status": "Confirmado"},
        headers=PROTECTED_HEADERS,
    )
    assert pagamento.status_code == 200

    produto_depois = client.get(f"/api/produtos/{produto['id']}").json()
    assert produto_depois["quantidade"] == 2

    pedido = client.get(f"/api/pedidos/{venda['id']}", headers=PROTECTED_HEADERS).json()
    assert pedido["status"] == "Pagamento confirmado"
    assert bool(pedido["estoque_baixado"]) is True


def test_links_audio_ambiente_salva_apenas_audio_direto():
    payload = {
        "links": [
            "https://cdn.exemplo.com/ambiente.mp3",
            "https://cdn.exemplo.com/ambiente.wav?versao=1",
            "https://example.com/pagina",
        ]
    }
    response = client.post("/api/uploads/musicas/links", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["links"] == [
        "https://cdn.exemplo.com/ambiente.mp3",
        "https://cdn.exemplo.com/ambiente.wav?versao=1",
    ]

    response_get = client.get("/api/uploads/musicas/links")
    assert response_get.status_code == 200
    assert response_get.json()["links"] == data["links"]
