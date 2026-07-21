import importlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def criar_produto(*, sob_encomenda: bool = False, quantidade: int = 10, limite: int = 5) -> dict:
    codigo = f"TRK-{uuid.uuid4().hex[:10]}"
    with TestClient(main.app) as client:
        resposta = client.post(
            "/api/produtos",
            headers=HEADERS,
            json={
                "codigo_p": codigo,
                "nome": "Produto teste acompanhamento/idempotencia",
                "preco": 49.9,
                "custo": 15.0,
                "quantidade": quantidade,
                "sob_encomenda": sob_encomenda,
                "limite_encomenda": limite,
            },
        )
        assert resposta.status_code == 200, resposta.text
        return {"id": resposta.json()["id"], "codigo_p": codigo.upper()}


def payload_checkout(produto: dict, quantidade: int = 1, *, ciente: bool = False) -> dict:
    return {
        "cliente": "Cliente teste acompanhamento",
        "telefone": "11988887777",
        "ciente_sob_encomenda": ciente,
        "forma_recebimento": "retirada",
        "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": quantidade}],
    }


def postar_checkout(dados: dict, ip_final: int, idempotency_key: str | None = None):
    headers = {"X-Forwarded-For": f"198.51.100.{ip_final}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    with TestClient(main.app) as client:
        return client.post("/api/checkout/pedidos", json=dados, headers=headers)


def consultar_status(venda_id: int, **params):
    with TestClient(main.app) as client:
        return client.get(f"/api/pedidos/{venda_id}/status", params=params)


# ---------------------------------------------------------------------------
# Acompanhamento público de pedidos protegido por pix_txid
# ---------------------------------------------------------------------------


def test_status_sem_txid_retorna_403():
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 101, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    venda_id = criado.json()["id"]

    resposta = consultar_status(venda_id)
    assert resposta.status_code == 403
    assert "pedido não encontrado" not in resposta.json()["detail"].lower()


def test_status_com_txid_invalido_retorna_403():
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 102, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    venda_id = criado.json()["id"]

    resposta = consultar_status(venda_id, txid="txid-invalido-nao-existe")
    assert resposta.status_code == 403


def test_status_com_txid_correto_retorna_200():
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 103, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    dados = criado.json()
    venda_id = dados["id"]
    txid = dados["pix_txid"]
    assert txid

    resposta = consultar_status(venda_id, txid=txid)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["venda_id"] == venda_id
    assert corpo["status_atual"] == "Aguardando pagamento"


def test_status_id_inexistente_sem_txid_tambem_retorna_403_generico():
    """Sem txid, mesmo um ID inexistente deve responder com o mesmo 403
    genérico (nunca 404) para não servir de oráculo de enumeração."""
    resposta = consultar_status(999_999_999)
    assert resposta.status_code == 403


def test_pix_txid_nao_e_previsivel_a_partir_do_id_do_pedido():
    """Regressão: o pix_txid é o único segredo que protege o acompanhamento
    público do pedido (ver test_status_com_txid_invalido_retorna_403). Ele
    não pode ser derivado do id do pedido — que é público, aparece na própria
    URL /api/pedidos/{id}/status — nem seguir um padrão adivinhável."""
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 106, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    dados = criado.json()
    venda_id = dados["id"]
    txid = dados["pix_txid"]
    assert txid

    padrao_adivinhavel = f"MISTICA{venda_id:09d}"
    assert txid != padrao_adivinhavel
    resposta_com_padrao_antigo = consultar_status(venda_id, txid=padrao_adivinhavel)
    assert resposta_com_padrao_antigo.status_code == 403

    outro = criar_produto()
    criado2 = postar_checkout(payload_checkout(outro), 107, uuid.uuid4().hex)
    assert criado2.status_code == 200, criado2.text
    txid2 = criado2.json()["pix_txid"]
    assert txid2 != txid


def test_admin_autenticado_acessa_status_sem_txid():
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 104, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    venda_id = criado.json()["id"]

    with TestClient(main.app) as client:
        resposta = client.get(f"/api/pedidos/{venda_id}/status", headers=HEADERS)
    assert resposta.status_code == 200
    assert resposta.json()["venda_id"] == venda_id


def test_recibo_publico_tambem_exige_txid_valido():
    produto = criar_produto()
    criado = postar_checkout(payload_checkout(produto), 105, uuid.uuid4().hex)
    assert criado.status_code == 200, criado.text
    dados = criado.json()
    venda_id = dados["id"]
    txid = dados["pix_txid"]

    with TestClient(main.app) as client:
        sem_txid = client.get(f"/api/pedidos/{venda_id}/recibo")
        assert sem_txid.status_code == 403

        com_txid = client.get(f"/api/pedidos/{venda_id}/recibo", params={"txid": txid})
        assert com_txid.status_code == 200


# ---------------------------------------------------------------------------
# Idempotência efetiva no checkout público (produtos normais e sob encomenda)
# ---------------------------------------------------------------------------


def test_mesma_idempotency_key_retorna_o_mesmo_pedido():
    produto = criar_produto(quantidade=5)
    chave = uuid.uuid4().hex
    dados = payload_checkout(produto)

    primeira = postar_checkout(dados, 110, chave)
    segunda = postar_checkout(dados, 111, chave)

    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text
    corpo1, corpo2 = primeira.json(), segunda.json()
    assert corpo1["id"] == corpo2["id"]
    assert corpo1["total_final"] == corpo2["total_final"]
    assert corpo1["pix_txid"] == corpo2["pix_txid"]
    assert corpo1["pix_copia_cola"] == corpo2["pix_copia_cola"]

    with main.conectar() as conn:
        total_pedidos = conn.execute(
            "SELECT COUNT(*) FROM pedidos_itens WHERE codigo_p=?", (produto["codigo_p"],)
        ).fetchone()[0]
        estoque = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto["id"],)).fetchone()[0]
    assert total_pedidos == 1
    assert estoque == 4  # baixado (reservado) uma única vez, não duas


def test_idempotency_key_com_payload_diferente_retorna_409():
    produto_a = criar_produto(quantidade=5)
    produto_b = criar_produto(quantidade=5)
    chave = uuid.uuid4().hex

    primeira = postar_checkout(payload_checkout(produto_a), 112, chave)
    assert primeira.status_code == 200, primeira.text

    segunda = postar_checkout(payload_checkout(produto_b), 113, chave)
    assert segunda.status_code == 409
    assert "idempotency" in segunda.json()["detail"].lower() or "diferente" in segunda.json()["detail"].lower()


def test_repetir_pedido_sob_encomenda_nao_cria_duplicata():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    chave = uuid.uuid4().hex
    dados = payload_checkout(produto, ciente=True)

    primeira = postar_checkout(dados, 114, chave)
    segunda = postar_checkout(dados, 115, chave)

    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text
    assert primeira.json()["id"] == segunda.json()["id"]
    assert primeira.json()["pix_txid"] == segunda.json()["pix_txid"]

    with main.conectar() as conn:
        total_pedidos = conn.execute(
            "SELECT COUNT(*) FROM pedidos_itens WHERE codigo_p=?", (produto["codigo_p"],)
        ).fetchone()[0]
    assert total_pedidos == 1


def test_erro_de_validacao_nao_deixa_chave_idempotente_gravada():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=2)
    chave = uuid.uuid4().hex

    # Sem "ciente_sob_encomenda": erro de validação, nenhum pedido deve ser criado.
    falhou = postar_checkout(payload_checkout(produto, ciente=False), 116, chave)
    assert falhou.status_code == 400

    # A mesma chave, agora com o payload correto, deve conseguir criar o pedido
    # normalmente -- prova que a chave anterior não ficou presa/gravada.
    sucesso = postar_checkout(payload_checkout(produto, ciente=True), 117, chave)
    assert sucesso.status_code == 200, sucesso.text


def test_concorrencia_simultanea_com_mesma_chave_nao_cria_dois_pedidos():
    produto = criar_produto(quantidade=5)
    chave = uuid.uuid4().hex
    dados = payload_checkout(produto)
    barreira = threading.Barrier(2)

    def enviar(ip):
        with TestClient(main.app) as client:
            barreira.wait(timeout=10)
            return client.post(
                "/api/checkout/pedidos",
                json=dados,
                headers={"X-Forwarded-For": f"198.51.100.{ip}", "Idempotency-Key": chave},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar, 120), executor.submit(enviar, 121)]
        resultados = [futuro.result(timeout=20) for futuro in futuros]

    for resposta in resultados:
        assert resposta.status_code == 200, resposta.text
    ids = {resposta.json()["id"] for resposta in resultados}
    assert len(ids) == 1

    with main.conectar() as conn:
        total_pedidos = conn.execute(
            "SELECT COUNT(*) FROM pedidos_itens WHERE codigo_p=?", (produto["codigo_p"],)
        ).fetchone()[0]
        estoque = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto["id"],)).fetchone()[0]
    assert total_pedidos == 1
    assert estoque == 4


def test_sem_idempotency_key_continua_funcionando_como_antes():
    produto = criar_produto(quantidade=3)
    resposta = postar_checkout(payload_checkout(produto), 122, None)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["pix_copia_cola"]
