"""Pontuação de produtos para o "Produto do dia" (backend/isis_content_scoring.py).

Testes puros, sem banco de dados: cobrem as regras de exclusão obrigatórias
(inativo, oculto, sem estoque) e o efeito dos principais sinais na
pontuação (rotação, vendas recentes, favoritos/carrinho, margem com peso
limitado, produto novo)."""
from backend.isis_content_scoring import (
    PESOS,
    elegivel,
    pontuar_produto,
    selecionar_produto_do_dia,
)


def _produto(**kwargs):
    base = {"id": 1, "nome": "Produto", "ativo": 1, "isis_oculto": 0, "quantidade": 10, "preco": 50.0, "custo": 20.0, "categoria": "Velas"}
    base.update(kwargs)
    return base


def test_produto_inativo_e_inelegivel():
    pode, motivo = elegivel(_produto(ativo=0))
    assert pode is False
    assert "inativo" in motivo


def test_produto_oculto_para_isis_e_inelegivel():
    pode, motivo = elegivel(_produto(isis_oculto=1))
    assert pode is False
    assert "oculto" in motivo


def test_produto_sem_estoque_e_inelegivel_por_padrao():
    pode, motivo = elegivel(_produto(quantidade=0))
    assert pode is False
    assert "estoque" in motivo


def test_produto_sem_estoque_pode_ser_liberado_por_regra_explicita():
    pode, motivo = elegivel(_produto(quantidade=0), permitir_sem_estoque=True)
    assert pode is True
    assert motivo is None


def test_selecionar_produto_do_dia_nunca_escolhe_inativo_oculto_ou_sem_estoque():
    produtos = [
        _produto(id=1, ativo=0, quantidade=99),
        _produto(id=2, isis_oculto=1, quantidade=99),
        _produto(id=3, quantidade=0),
        _produto(id=4, quantidade=5),
    ]
    escolhido = selecionar_produto_do_dia(produtos, {})
    assert escolhido is not None
    assert escolhido.produto["id"] == 4


def test_selecionar_produto_do_dia_sem_candidatos_devolve_none():
    produtos = [_produto(id=1, ativo=0), _produto(id=2, quantidade=0)]
    assert selecionar_produto_do_dia(produtos, {}) is None


def test_rotacao_favorece_produto_nunca_divulgado():
    produtos = [_produto(id=1), _produto(id=2)]
    sinais = {
        1: {"dias_desde_ultima_divulgacao": 1},
        2: {"dias_desde_ultima_divulgacao": None},
    }
    escolhido = selecionar_produto_do_dia(produtos, sinais)
    assert escolhido.produto["id"] == 2
    assert "nunca divulgado" in " ".join(escolhido.motivos)


def test_rotacao_favorece_produto_ha_mais_tempo_sem_divulgacao():
    produtos = [_produto(id=1), _produto(id=2)]
    sinais = {
        1: {"dias_desde_ultima_divulgacao": 2},
        2: {"dias_desde_ultima_divulgacao": 40},
    }
    escolhido = selecionar_produto_do_dia(produtos, sinais)
    assert escolhido.produto["id"] == 2


def test_vendas_recentes_aumentam_pontuacao():
    produto = _produto()
    maximos = {"quantidade": 10, "vendas_recentes": 10, "visualizacoes": 1, "favoritos": 1, "carrinhos": 1, "campanhas_anteriores": 1, "margem_percentual": 1}
    sem_vendas = pontuar_produto(produto, {}, maximos=maximos)
    com_vendas = pontuar_produto(produto, {"vendas_recentes": 10}, maximos=maximos)
    assert com_vendas.score > sem_vendas.score
    assert "vendas recentes" in " ".join(com_vendas.motivos)


def test_produto_novo_recebe_bonus_mas_nao_domina_pontuacao():
    produto = _produto()
    maximos = {"quantidade": 10, "vendas_recentes": 1, "visualizacoes": 1, "favoritos": 1, "carrinhos": 1, "campanhas_anteriores": 1, "margem_percentual": 1}
    normal = pontuar_produto(produto, {}, maximos=maximos)
    novo = pontuar_produto(produto, {"dias_desde_cadastro": 5}, maximos=maximos)
    assert novo.score > normal.score
    assert (novo.score - normal.score) <= PESOS["produto_novo"] + 1e-9


def test_margem_tem_peso_limitado_e_nao_supera_vendas_recentes():
    assert PESOS["margem"] < PESOS["vendas_recentes"]
    produto = _produto()
    maximos = {"quantidade": 10, "vendas_recentes": 1, "visualizacoes": 1, "favoritos": 1, "carrinhos": 1, "campanhas_anteriores": 1, "margem_percentual": 100}
    so_margem = pontuar_produto(produto, {"margem_percentual": 100}, maximos=maximos)
    so_vendas = pontuar_produto(produto, {"vendas_recentes": 1}, maximos=maximos)
    assert so_vendas.score >= so_margem.score


def test_nunca_inventa_preco_ou_desconto_ausentes():
    produto = _produto()
    del produto["preco"]
    resultado = pontuar_produto(produto, {}, maximos={"quantidade": 10})
    assert "preco" not in resultado.produto
    assert "desconto" not in resultado.produto
