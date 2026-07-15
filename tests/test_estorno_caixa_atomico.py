"""Testes do estorno atômico de vendas no módulo Caixa/PDV (Fase 2 — PR
fix/caixa-estorno-atomico).

Antes desta correção, services/venda_service.py::cancelar_venda_service lia o
status da venda (repositories/vendas.py::obter_status_total_forma) num SELECT
separado — antes de abrir a transação — e só depois decidia e escrevia
(repositories/vendas.py::marcar_cancelada_cursor fazia um UPDATE incondicional,
sem WHERE de guarda). Duas chamadas concorrentes de estorno para a mesma venda
(duplo clique do operador, dois caixas simultâneos, retry) podiam observar o
mesmo status "Concluído" antigo e as duas prosseguirem: devolução de estoque em
dobro, lançamento de saída duplicado no fluxo de caixa e histórico de
movimentação duplicado.

Da mesma forma, services/caixa_service.py::fechar_caixa_simples/
fechar_caixa_conferido faziam um UPDATE incondicional (sem WHERE status=
'Aberto'), então um estorno concorrente com o fechamento do caixa podia gravar
uma saída num caixa_diario que acabou de fechar, ou dois fechamentos
simultâneos podiam sobrescrever silenciosamente os totais um do outro.

A correção substitui cada leitura-decisão-escrita por um único UPDATE com
guarda no próprio WHERE (compare-and-swap): a checagem do estado atual e a
escrita da transição acontecem atomicamente, dentro da mesma transação SQLite
que já protege a devolução de estoque e o lançamento financeiro. Só uma
chamada reivindica a transição (rowcount==1); a(s) outra(s) reagem ao estado
JÁ ATUAL, nunca ao que leram antes — e, se o caixa fechar no meio da operação,
a transação inteira é revertida (nada de estoque/fluxo parcialmente aplicado).
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

import config
import database.connection as db_conn
from services import venda_service
from services.venda_service import calcular_total_venda, calcular_total_venda_misto, registrar_venda_service, cancelar_venda_service
from services.caixa_service import (
    abrir_caixa,
    fechar_caixa_simples,
    fechar_caixa_conferido,
    resumo_fechamento_caixa,
)
from services.produto_service import cadastrar_produto_service


@pytest.fixture()
def banco_temporario(tmp_path, monkeypatch):
    db_path = str(tmp_path / "estorno_caixa_atomico.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(venda_service, "_confirmar_venda_no_banco_central", lambda venda_id: (True, None))

    from database import init_db, query_db

    init_db()
    query_db("INSERT INTO categorias (nome) VALUES (?)", ("Teste",), commit=True)
    return db_path


def _produto(quantidade=10, preco=50.0, custo=10.0):
    return cadastrar_produto_service(
        nome=f"Produto {uuid.uuid4().hex[:8]}",
        custo=custo,
        lucro=100.0,
        preco=preco,
        quantidade=quantidade,
        estoque_minimo=1,
        categoria="Teste",
        usuario="Teste",
    )


def _vender(codigo, caixa_id, quantidade=1, preco=50.0):
    carrinho = [{"id": codigo, "n": "Produto", "q": quantidade, "p": preco, "t": preco * quantidade}]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    return registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, "Dinheiro", "Teste", caixa_id,
    )


def _estoque(codigo):
    from database import query_db
    res = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))
    return int(res[0][0])


def _status_venda(venda_id):
    from database import query_db
    res = query_db("SELECT status FROM vendas WHERE id=?", (venda_id,))
    return res[0][0] if res else None


def _status_caixa(caixa_id):
    from database import query_db
    res = query_db("SELECT status FROM caixa_diario WHERE id=?", (caixa_id,))
    return res[0][0] if res else None


def _movimentacoes(venda_id):
    from database import query_db
    return query_db(
        "SELECT tipo FROM movimentacao_estoque WHERE venda_id=? ORDER BY id ASC", (venda_id,)
    )


def _fluxo_caixa(caixa_id):
    from database import query_db
    return query_db(
        "SELECT tipo, descricao, valor FROM fluxo_caixa WHERE caixa_id=? ORDER BY id ASC", (caixa_id,)
    )


# 1 — dois estornos simultâneos não duplicam devolução de estoque nem lançamento


def test_dois_estornos_simultaneos_nao_duplicam_devolucao(banco_temporario):
    codigo = _produto(quantidade=10)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id)
    assert _estoque(codigo) == 9

    barreira = threading.Barrier(2)

    def estornar():
        barreira.wait(timeout=10)
        try:
            cancelar_venda_service(venda_id, "Teste", caixa_id)
            return "ok"
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(estornar) for _ in range(2)]
        resultados = [f.result(timeout=20) for f in futuros]

    assert sorted(resultados) == ["Venda ja cancelada.", "ok"]
    assert _estoque(codigo) == 10  # nunca duplicado
    assert _status_venda(venda_id) == "Cancelado"

    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    assert len(saidas) == 1  # um único lançamento de estorno, não dois

    cancelamentos = [m for m in _movimentacoes(venda_id) if m[0] == "Cancelamento"]
    assert len(cancelamentos) == 1  # histórico registrado uma única vez


# 2/6 — estorno repetido é idempotente


def test_estorno_repetido_e_idempotente(banco_temporario):
    codigo = _produto(quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id)
    assert _estoque(codigo) == 4

    cancelar_venda_service(venda_id, "Teste", caixa_id)
    assert _estoque(codigo) == 5

    for _ in range(4):
        with pytest.raises(ValueError, match="ja cancelada"):
            cancelar_venda_service(venda_id, "Teste", caixa_id)

    assert _estoque(codigo) == 5  # estoque nunca volta a mudar
    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    assert len(saidas) == 1


# 3 — estorno concorrente com fechamento de caixa: resultado sempre determinístico


def test_estorno_concorrente_com_fechamento_de_caixa_e_deterministico(banco_temporario):
    resultados_gerais = []
    for _ in range(8):
        codigo = _produto(quantidade=5)
        caixa_id = abrir_caixa(0.0, "Teste")
        venda_id = _vender(codigo, caixa_id)
        assert _estoque(codigo) == 4
        resumo = resumo_fechamento_caixa()

        barreira = threading.Barrier(2)
        resultado = {}

        def estornar():
            barreira.wait(timeout=10)
            try:
                cancelar_venda_service(venda_id, "Teste", caixa_id)
                resultado["estorno"] = "ok"
            except ValueError as exc:
                resultado["estorno"] = str(exc)

        def fechar():
            barreira.wait(timeout=10)
            try:
                fechar_caixa_simples(caixa_id, resumo["saldo"])
                resultado["fechamento"] = "ok"
            except ValueError as exc:
                resultado["fechamento"] = str(exc)

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(estornar)
            f2 = executor.submit(fechar)
            f1.result(timeout=20)
            f2.result(timeout=20)

        # Nunca um estado "meio-termo": só dois desfechos são possíveis, e
        # cada um deve satisfazer TODAS as propriedades abaixo — nenhuma
        # combinação parcial é aceita.
        estoque_final = _estoque(codigo)
        status_final = _status_venda(venda_id)
        status_caixa_final = _status_caixa(caixa_id)
        saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
        cancelamentos = [m for m in _movimentacoes(venda_id) if m[0] == "Cancelamento"]

        if resultado["estorno"] == "ok":
            # O estorno venceu o CAS da venda: estoque reposto uma única vez,
            # saída financeira lançada, venda cancelada, e o fechamento -
            # que só pôde rodar depois - inclui esse lançamento e fecha o
            # caixa normalmente (nunca falha por "já fechado" nem sobra
            # "Aberto").
            assert estoque_final == 5
            assert status_final == "Cancelado"
            assert len(saidas) == 1
            assert len(cancelamentos) == 1
            assert status_caixa_final == "Fechado"
            assert resultado["fechamento"] == "ok"
        else:
            # O fechamento venceu o CAS do caixa: o estorno detecta
            # 'status != Aberto' dentro da própria transação e sofre
            # rollback completo — nem estoque, nem status da venda, nem
            # fluxo_caixa, nem histórico são tocados. O caixa termina
            # fechado por quem venceu.
            assert resultado["estorno"] == "O caixa foi fechado durante a operação; estorno cancelado. Reabra o caixa e tente novamente."
            assert resultado["fechamento"] == "ok"
            assert estoque_final == 4  # rollback completo: nada mudou
            assert status_final == "Concluído"
            assert saidas == []  # nenhuma saída financeira criada pelo perdedor
            assert cancelamentos == []  # nenhum histórico de cancelamento "fantasma"
            assert status_caixa_final == "Fechado"
        resultados_gerais.append(resultado["estorno"] == "ok")
        # Cada iteração usa um caixa novo (abrir_caixa exige o anterior
        # fechado); o loop acima já garante isso em ambos os desfechos.

    # Garante que os dois desfechos possíveis realmente ocorreram ao longo
    # das repetições (a corrida não é sempre resolvida do mesmo jeito) — sem
    # isso, o teste poderia estar validando só metade da lógica por sorte de
    # agendamento de threads.
    assert True in resultados_gerais
    assert False in resultados_gerais


# 4 — rollback completo em falha intermediária


def test_rollback_completo_quando_devolucao_falha_no_meio(banco_temporario):
    codigo_ok = _produto(quantidade=5)
    codigo_removido = _produto(quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")

    carrinho = [
        {"id": codigo_ok, "n": "Produto OK", "q": 1, "p": 50.0, "t": 50.0},
        {"id": codigo_removido, "n": "Produto Removido", "q": 1, "p": 50.0, "t": 50.0},
    ]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    venda_id = registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, "Dinheiro", "Teste", caixa_id,
    )
    assert _estoque(codigo_ok) == 4
    assert _estoque(codigo_removido) == 4

    from database import query_db
    query_db("DELETE FROM produtos WHERE codigo_p=?", (codigo_removido,), commit=True)

    with pytest.raises(ValueError):
        cancelar_venda_service(venda_id, "Teste", caixa_id)

    # Nada foi aplicado: nem a devolução do primeiro item (que teria
    # sucedido isoladamente), nem o status da venda, nem o fluxo de caixa.
    assert _estoque(codigo_ok) == 4
    assert _status_venda(venda_id) == "Concluído"
    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    assert saidas == []
    assert _movimentacoes(venda_id) == [("Venda",), ("Venda",)]  # só a baixa original, nada de cancelamento parcial


# 5 — preservação da auditoria financeira (fluxo_caixa) e do histórico (movimentacao_estoque)


def test_estorno_preserva_auditoria_financeira_e_historico(banco_temporario):
    codigo = _produto(quantidade=5, preco=80.0)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id, preco=80.0)

    entradas_antes = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Entrada" and str(venda_id) in linha[1]]
    assert len(entradas_antes) == 1
    assert entradas_antes[0][2] == pytest.approx(80.0)

    cancelar_venda_service(venda_id, "Operador Teste", caixa_id)

    # A entrada original da venda nunca é apagada/alterada pelo estorno.
    fluxo_depois = _fluxo_caixa(caixa_id)
    entradas_depois = [linha for linha in fluxo_depois if linha[0] == "Entrada" and str(venda_id) in linha[1]]
    assert entradas_depois == entradas_antes

    saidas = [linha for linha in fluxo_depois if linha[0] == "Saida"]
    assert len(saidas) == 1
    assert saidas[0][2] == pytest.approx(80.0)
    assert str(venda_id) in saidas[0][1]

    # Histórico de estoque preserva a baixa original e registra a devolução
    # como um evento novo (nunca sobrescreve o registro anterior).
    mov = _movimentacoes(venda_id)
    assert mov == [("Venda",), ("Cancelamento",)]


# 7 — idempotência sob retries sequenciais da mesma chamada


def test_retries_sequenciais_de_estorno_sao_seguros(banco_temporario):
    codigo = _produto(quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id)

    resultados = []
    for _ in range(3):
        try:
            cancelar_venda_service(venda_id, "Teste", caixa_id)
            resultados.append("ok")
        except ValueError as exc:
            resultados.append(str(exc))

    assert resultados[0] == "ok"
    assert resultados[1:] == ["Venda ja cancelada."] * 2
    assert _estoque(codigo) == 5


# 8 — fechamento de caixa também é atômico e idempotente (dois fechamentos simultâneos)


def test_dois_fechamentos_simultaneos_do_mesmo_caixa_nao_duplicam(banco_temporario):
    caixa_id = abrir_caixa(100.0, "Teste")
    barreira = threading.Barrier(2)

    def fechar():
        barreira.wait(timeout=10)
        try:
            fechar_caixa_simples(caixa_id, 100.0)
            return "ok"
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(fechar) for _ in range(2)]
        resultados = [f.result(timeout=20) for f in futuros]

    assert sorted(resultados) == ["Caixa ja esta fechado.", "ok"]


def test_estorno_apos_caixa_fechado_no_mesmo_caixa_e_rejeitado(banco_temporario):
    codigo = _produto(quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id)
    resumo = resumo_fechamento_caixa()
    fechar_caixa_simples(caixa_id, resumo["saldo"])

    with pytest.raises(ValueError, match="caixa foi fechado"):
        cancelar_venda_service(venda_id, "Teste", caixa_id)

    assert _estoque(codigo) == 4  # nada mudou
    assert _status_venda(venda_id) == "Concluído"


# 9 — integridade financeira: forma de pagamento original é preservada e o
# valor estornado vem do banco (nunca de entrada externa), para dinheiro,
# Pix, cartão, misto, com desconto e com acréscimo (taxa de cartão).


@pytest.mark.parametrize(
    "forma,preco,desconto",
    [
        ("Dinheiro", 100.0, 0),
        ("Pix", 100.0, 0),
        ("Credito 3x", 100.0, 0),  # acréscimo: taxa fixa de cartão soma ao total
        ("Dinheiro", 100.0, 10),  # desconto percentual aplicado no subtotal
    ],
)
def test_estorno_preserva_forma_de_pagamento_e_valor_autoritativo(banco_temporario, forma, preco, desconto):
    codigo = _produto(quantidade=5, preco=preco)
    caixa_id = abrir_caixa(0.0, "Teste")
    carrinho = [{"id": codigo, "n": "Produto", "q": 1, "p": preco, "t": preco}]
    calculo = calcular_total_venda(carrinho, desconto, forma)
    venda_id = registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, forma, "Teste", caixa_id,
    )
    from database import query_db
    total_final_gravado = query_db("SELECT total_final FROM vendas WHERE id=?", (venda_id,))[0][0]

    cancelar_venda_service(venda_id, "Teste", caixa_id)

    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    assert len(saidas) == 1
    # O valor estornado é sempre o total_final gravado na venda — nunca um
    # valor arbitrário passado por quem chama cancelar_venda_service (a
    # função nem aceita esse parâmetro).
    assert saidas[0][2] == pytest.approx(total_final_gravado)
    assert _estoque(codigo) == 5


def test_estorno_de_venda_com_pagamento_misto_lanca_saida_por_forma(banco_temporario):
    codigo = _produto(quantidade=5, preco=100.0)
    caixa_id = abrir_caixa(0.0, "Teste")
    carrinho = [{"id": codigo, "n": "Produto", "q": 1, "p": 100.0, "t": 100.0}]
    calculo = calcular_total_venda_misto(carrinho, 0, [{"forma": "Dinheiro", "valor": 40}, {"forma": "Pix", "valor": 60}])
    venda_id = registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, "Misto", "Teste", caixa_id,
        pagamentos_mistos=[{"forma": "Dinheiro", "valor": 40}, {"forma": "Pix", "valor": 60}],
    )

    cancelar_venda_service(venda_id, "Teste", caixa_id)

    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    # Uma saída por forma de pagamento do misto, preservando o split original.
    assert len(saidas) == 2
    valores = sorted(linha[2] for linha in saidas)
    assert valores == [pytest.approx(40.0), pytest.approx(60.0)]
    assert _estoque(codigo) == 5


def test_estorno_de_venda_mista_com_cartao_devolve_valor_com_taxa(banco_temporario):
    """Regressão: services/venda_service.py::resumo_pagamentos_mistos grava a
    forma com taxa como "Credito 1x R$ X,XX (inclui taxa R$ Y,YY)" — um
    segundo "R$" só informativo. extrair_pagamentos_mistos precisa cortar no
    PRIMEIRO "R$" (o valor pago) e não no último (a taxa), senão a parcela em
    cartão é descartada do estorno e o caixa fecha com saldo inflado."""
    codigo = _produto(quantidade=5, preco=100.0)
    caixa_id = abrir_caixa(0.0, "Teste")
    carrinho = [{"id": codigo, "n": "Produto", "q": 1, "p": 100.0, "t": 100.0}]
    # Valor do Credito 1x já inclui a taxa fixa de R$ 1,50 (60 do produto +
    # 1,50 de taxa), exatamente como normalizar_pagamentos_mistos exige.
    calculo = calcular_total_venda_misto(carrinho, 0, [{"forma": "Dinheiro", "valor": 40}, {"forma": "Credito 1x", "valor": 61.5}])
    venda_id = registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, "Misto", "Teste", caixa_id,
        pagamentos_mistos=[{"forma": "Dinheiro", "valor": 40}, {"forma": "Credito 1x", "valor": 61.5}],
    )
    entradas_antes = sum(linha[2] for linha in _fluxo_caixa(caixa_id) if linha[0] == "Entrada")

    cancelar_venda_service(venda_id, "Teste", caixa_id)

    saidas = [linha for linha in _fluxo_caixa(caixa_id) if linha[0] == "Saida"]
    # As duas parcelas (Dinheiro e Credito 1x, esta com taxa embutida) têm
    # que ser estornadas — nenhuma pode ser descartada por causa do sufixo
    # "(inclui taxa ...)".
    assert len(saidas) == 2
    valores = sorted(linha[2] for linha in saidas)
    assert valores == [pytest.approx(40.0), pytest.approx(61.5)]
    total_saidas = sum(linha[2] for linha in saidas)
    # O caixa fecha zerado: nada de saldo inflado por parcela de cartão
    # perdida no parsing do estorno.
    assert total_saidas == pytest.approx(entradas_antes)
    assert _estoque(codigo) == 5


# 10 — estorno não grava em caixa diferente do informado, e não altera um
# fechamento já concluído anteriormente


def test_estorno_nao_grava_lancamento_em_caixa_diferente_do_informado(banco_temporario):
    codigo_a = _produto(quantidade=5)
    caixa_a = abrir_caixa(0.0, "Teste")
    venda_a = _vender(codigo_a, caixa_a)
    resumo_a = resumo_fechamento_caixa()
    fechar_caixa_simples(caixa_a, resumo_a["saldo"])

    codigo_b = _produto(quantidade=5)
    caixa_b = abrir_caixa(0.0, "Teste")
    venda_b = _vender(codigo_b, caixa_b)

    cancelar_venda_service(venda_b, "Teste", caixa_b)

    # O estorno da venda do caixa B não grava nada no caixa A, que já
    # fechou antes — o fechamento anterior nunca é alterado.
    assert _fluxo_caixa(caixa_a) == [
        linha for linha in _fluxo_caixa(caixa_a) if "no " + str(venda_b) not in linha[1]
    ]
    from database import query_db
    saldo_final_a = query_db("SELECT saldo_final FROM caixa_diario WHERE id=?", (caixa_a,))[0][0]
    assert saldo_final_a == pytest.approx(resumo_a["saldo"])


# 11 — estoque: mesmo produto em duas linhas da mesma venda soma corretamente


def test_produto_duplicado_na_mesma_venda_devolve_soma_correta(banco_temporario):
    codigo = _produto(quantidade=10)
    caixa_id = abrir_caixa(0.0, "Teste")
    carrinho = [
        {"id": codigo, "n": "Produto", "q": 2, "p": 50.0, "t": 100.0},
        {"id": codigo, "n": "Produto", "q": 3, "p": 50.0, "t": 150.0},
    ]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    venda_id = registrar_venda_service(
        carrinho, "Consumidor Final", "01/01/2026 10:00", "2026-01-01 10:00:00",
        calculo, "Dinheiro", "Teste", caixa_id,
    )
    assert _estoque(codigo) == 5  # 10 - 2 - 3

    cancelar_venda_service(venda_id, "Teste", caixa_id)

    assert _estoque(codigo) == 10  # 2 + 3 devolvidos corretamente
    cancelamentos = [m for m in _movimentacoes(venda_id) if m[0] == "Cancelamento"]
    assert len(cancelamentos) == 2  # uma movimentação coerente por linha do carrinho, sem se fundirem incorretamente


# 12 — produto inativo (soft-deleted) ainda recebe a devolução de estoque
# corretamente; só a exclusão física (DELETE) força rollback (já coberto
# pelo teste de rollback em falha intermediária acima)


def test_produto_inativo_ainda_recebe_devolucao_de_estoque(banco_temporario):
    codigo = _produto(quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _vender(codigo, caixa_id)
    assert _estoque(codigo) == 4

    from database import query_db
    query_db("UPDATE produtos SET ativo=0 WHERE codigo_p=?", (codigo,), commit=True)

    cancelar_venda_service(venda_id, "Teste", caixa_id)

    assert _estoque(codigo) == 5  # devolução de estoque não é bloqueada por ativo=0
