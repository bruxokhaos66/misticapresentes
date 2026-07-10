"""Teste automatico basico do sistema Mistica Presentes.

Roda dentro da suite pytest (tests/smoke_test.py). Usa banco temporario
via fixtures do pytest e nao mexe no banco real da loja.
"""
import database.connection as db_conn
import config


def test_venda_e_cancelamento_ajustam_estoque_corretamente(tmp_path, monkeypatch):
    db_path = str(tmp_path / "smoke_mistica.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)

    from database import init_db, query_db
    from services.caixa_service import abrir_caixa, obter_caixa_id_ativo
    from services.produto_service import cadastrar_produto_service
    from services.venda_service import calcular_total_venda, cancelar_venda_service, registrar_venda_service

    init_db()

    query_db("INSERT INTO categorias (nome) VALUES (?)", ("Teste",), commit=True)
    codigo = cadastrar_produto_service(
        nome="Produto Teste",
        custo=5.0,
        lucro=100.0,
        preco=10.0,
        quantidade=10,
        estoque_minimo=2,
        categoria="Teste",
        usuario="Teste",
    )

    caixa_id = abrir_caixa(100.0, "Teste")
    assert obter_caixa_id_ativo() == caixa_id

    carrinho = [{"id": codigo, "n": "Produto Teste", "q": 2, "p": 10.0, "t": 20.0}]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    venda_id = registrar_venda_service(
        carrinho,
        "Consumidor Final",
        "01/01/2026 10:00",
        "2026-01-01 10:00:00",
        calculo,
        "Dinheiro",
        "Teste",
        caixa_id,
    )

    estoque = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    assert estoque == 8, f"Estoque esperado 8, recebido {estoque}"

    cancelar_venda_service(venda_id, "Teste", caixa_id)
    estoque = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    assert estoque == 10, f"Estoque esperado 10 apos cancelamento, recebido {estoque}"

    status = query_db("SELECT status FROM vendas WHERE id=?", (venda_id,))[0][0]
    assert status == "Cancelado", f"Status esperado Cancelado, recebido {status}"
