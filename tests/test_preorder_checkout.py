import importlib
import os
import uuid

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def criar_produto(*, sob_encomenda: bool, quantidade: int, limite: int = 5) -> dict:
    codigo = f"PRE-{uuid.uuid4().hex[:10]}"
    with TestClient(main.app) as client:
        resposta = client.post(
            "/api/produtos",
            headers=HEADERS,
            json={
                "codigo_p": codigo,
                "nome": "Produto de teste sob encomenda" if sob_encomenda else "Produto normal de teste",
                "preco": 39.9,
                "custo": 12.0,
                "quantidade": quantidade,
                "sob_encomenda": sob_encomenda,
                "limite_encomenda": limite,
            },
        )
        assert resposta.status_code == 200, resposta.text
        return {"id": resposta.json()["id"], "codigo_p": codigo.upper()}


def payload(produtos: list[tuple[dict, int]], *, ciente: bool = False) -> dict:
    return {
        "cliente": "Cliente teste encomenda",
        "telefone": "11999999999",
        "ciente_sob_encomenda": ciente,
        "forma_recebimento": "retirada",
        "itens": [
            {
                "produto_id": produto["id"],
                "codigo_p": produto["codigo_p"],
                "quantidade": quantidade,
            }
            for produto, quantidade in produtos
        ],
    }


def postar_checkout(dados: dict, ip_final: int):
    with TestClient(main.app) as client:
        return client.post(
            "/api/checkout/pedidos",
            json=dados,
            headers={"X-Forwarded-For": f"198.51.100.{ip_final}"},
        )


def test_encomenda_sem_ciencia_e_rejeitada_sem_criar_pedido():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=4)
    resposta = postar_checkout(payload([(produto, 1)], ciente=False), 61)

    assert resposta.status_code == 400
    assert "ciente" in resposta.json()["detail"].lower()
    with main.conectar() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM pedidos_itens WHERE codigo_p=?",
            (produto["codigo_p"],),
        ).fetchone()[0]
    assert total == 0


def test_encomenda_com_estoque_zero_cria_pix_sem_baixar_estoque():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=4)
    resposta = postar_checkout(payload([(produto, 2)], ciente=True), 62)

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["sob_encomenda"] is True
    assert dados["estoque_baixado"] is False
    assert dados["estoque_reservado"] is False
    assert dados["pix_copia_cola"]

    with main.conectar() as conn:
        estoque = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto["id"],)).fetchone()[0]
        pedido = conn.execute("SELECT estoque_baixado, estoque_reservado FROM pedidos WHERE id=?", (dados["id"],)).fetchone()
    assert estoque == 0
    assert pedido["estoque_baixado"] == 0
    assert pedido["estoque_reservado"] == 0


def test_encomenda_acima_do_limite_comercial_e_bloqueada():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=3)
    resposta = postar_checkout(payload([(produto, 4)], ciente=True), 63)

    assert resposta.status_code == 409
    assert "máxima" in resposta.json()["detail"].lower()


def test_carrinho_misto_e_bloqueado_para_evitar_reposicao_incorreta():
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=3)
    normal = criar_produto(sob_encomenda=False, quantidade=2, limite=3)
    resposta = postar_checkout(payload([(encomenda, 1), (normal, 1)], ciente=True), 64)

    assert resposta.status_code == 400
    assert "pedidos separados" in resposta.json()["detail"].lower()
    with main.conectar() as conn:
        estoque_normal = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (normal["id"],)).fetchone()[0]
    assert estoque_normal == 2
