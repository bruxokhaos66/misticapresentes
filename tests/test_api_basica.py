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
    assert data == {"status": "online", "app": "Mística Presentes"}


def test_health_head_sem_autenticacao_e_sem_corpo():
    response = client.head("/api/health")
    assert response.status_code == 200
    assert response.content == b""


def test_health_nao_expoe_informacoes_internas():
    response = client.get("/api/health")
    assert response.status_code == 200
    corpo = response.text
    assert "mistica_gestao_v20.db" not in corpo
    assert "/opt/render" not in corpo
    for chave_proibida in ("database", "db_path", "server_url", "api_url", "domain", "secret", "token", "key"):
        assert chave_proibida not in corpo.lower()


def test_version_online():
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data == {"app": "Mística Presentes", "version": main.app.version}


def test_version_head_sem_autenticacao_e_sem_corpo():
    response = client.head("/api/version")
    assert response.status_code == 200
    assert response.content == b""


def test_status_online():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["api"] == "mistica"
    assert data["app"] == "Mística Presentes"
    assert "data_hora" in data
    for chave_negocio in ("clientes", "vendas", "produtos"):
        assert chave_negocio not in data


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


def test_backup_download_retorna_arquivo():
    response = client.get("/api/backup/download", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert "mistica_backup_" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_backup_download_exige_chave_valida():
    response = client.get("/api/backup/download")
    assert response.status_code in (401, 403)


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
    assert data["armazenamento"] == "arquivo"
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


def test_painel_dashboard_traz_indicadores_comerciais():
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Indicador", "codigo_p": codigo_unico("IND"), "preco": 40.0, "quantidade": 10},
        headers=PROTECTED_HEADERS,
    ).json()
    client.post(
        f"/api/produtos/{produto['id']}/avaliacoes",
        json={"nome_cliente": "Cliente Indicador", "nota": 4, "comentario": "Bom"},
    )

    response = client.get("/api/painel/dashboard", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    for chave in ("ticket_medio_mes", "produto_mais_vendido_mes", "produto_mais_vendido_qtd", "avaliacoes_total", "avaliacoes_media"):
        assert chave in data
    assert data["avaliacoes_total"] >= 1
    assert data["avaliacoes_media"] > 0


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


def test_expiracao_de_pedido_nao_repoe_estoque_em_dobro_com_workers_concorrentes():
    from backend.database import conectar
    from backend.order_status_routes import expirar_pedidos_pendentes

    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Expira", "codigo_p": codigo_unico("EXP"), "preco": 30.0, "quantidade": 5},
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

    produto_reservado = client.get(f"/api/produtos/{produto['id']}").json()
    assert produto_reservado["quantidade"] == 3

    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (venda["id"],))
        conn.commit()

    # Simula dois workers rodando a varredura de expiração ao mesmo tempo: o
    # segundo não deve encontrar mais o pedido "Aguardando pagamento" e,
    # portanto, não deve repor o estoque de novo.
    with conectar() as conn:
        primeira_passada = expirar_pedidos_pendentes(conn)
    with conectar() as conn:
        segunda_passada = expirar_pedidos_pendentes(conn)

    assert primeira_passada == 1
    assert segunda_passada == 0

    produto_apos = client.get(f"/api/produtos/{produto['id']}").json()
    assert produto_apos["quantidade"] == 5

    pedido = client.get(f"/api/pedidos/{venda['id']}", headers=PROTECTED_HEADERS).json()
    assert pedido["status"] == "Cancelado"


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


def test_avaliacoes_publico_le_e_cria_para_produto_existente():
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Avaliado", "codigo_p": codigo_unico("AVL"), "preco": 20.0, "quantidade": 5},
        headers=PROTECTED_HEADERS,
    ).json()

    vazio = client.get(f"/api/produtos/{produto['id']}/avaliacoes")
    assert vazio.status_code == 200
    assert vazio.json() == {"avaliacoes": [], "total": 0, "media": 0}

    resposta = client.post(
        f"/api/produtos/{produto['id']}/avaliacoes",
        json={"nome_cliente": "Maria", "nota": 5, "comentario": "Produto lindo, chegou rápido!"},
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}

    listagem = client.get(f"/api/produtos/{produto['id']}/avaliacoes")
    assert listagem.status_code == 200
    data = listagem.json()
    assert data["total"] == 1
    assert data["media"] == 5
    assert data["avaliacoes"][0]["nome_cliente"] == "Maria"
    assert data["avaliacoes"][0]["comentario"] == "Produto lindo, chegou rápido!"


def test_listagem_de_produtos_traz_prova_social():
    # Insere as avaliações direto no banco (em vez de via POST /avaliacoes) para
    # não consumir a cota do rate limit de criação de avaliação compartilhada
    # com os outros testes deste arquivo (mesmo IP de teste).
    from backend.database import conectar

    codigo = codigo_unico("PROVA")
    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Prova Social", "codigo_p": codigo, "preco": 15.0, "quantidade": 5},
        headers=PROTECTED_HEADERS,
    ).json()

    listagem_sem_avaliacao = client.get("/api/produtos", params={"busca": codigo}).json()
    assert listagem_sem_avaliacao[0]["avaliacoes_total"] == 0
    assert listagem_sem_avaliacao[0]["avaliacoes_media"] == 0

    with conectar() as conn:
        conn.execute(
            "INSERT INTO avaliacoes_produtos (produto_id, nome_cliente, nota, comentario, data_hora, aprovado) VALUES (?,?,?,?,?,1)",
            (produto["id"], "Joana", 4, "Gostei bastante", "2026-01-01T10:00:00"),
        )
        conn.execute(
            "INSERT INTO avaliacoes_produtos (produto_id, nome_cliente, nota, comentario, data_hora, aprovado) VALUES (?,?,?,?,?,1)",
            (produto["id"], "Pedro", 5, "", "2026-01-01T10:05:00"),
        )
        conn.commit()

    listagem = client.get("/api/produtos", params={"busca": codigo}).json()
    assert listagem[0]["avaliacoes_total"] == 2
    assert listagem[0]["avaliacoes_media"] == 4.5


def test_avaliacoes_rejeita_produto_inexistente_e_nota_invalida():
    resposta = client.post(
        "/api/produtos/999999999/avaliacoes",
        json={"nome_cliente": "Ana", "nota": 4, "comentario": "Ótimo"},
    )
    assert resposta.status_code == 404

    produto = client.post(
        "/api/produtos",
        json={"nome": "Produto Nota Invalida", "codigo_p": codigo_unico("AVL2"), "preco": 15.0, "quantidade": 3},
        headers=PROTECTED_HEADERS,
    ).json()
    resposta_nota = client.post(
        f"/api/produtos/{produto['id']}/avaliacoes",
        json={"nome_cliente": "Ana", "nota": 9, "comentario": "Nota fora do intervalo"},
    )
    assert resposta_nota.status_code == 422
