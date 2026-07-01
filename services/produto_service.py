import re
from datetime import datetime

from repositories import produtos as produtos_repo
from services.estoque_service import registrar_movimentacao_estoque_service


def _prefixo_categoria(categoria):
    base = re.sub(r"[^A-Z0-9]", "", (categoria or "PRO").upper())
    return (base[:3] or "PRO").ljust(3, "X")


def gerar_codigo_produto(categoria):
    prefixo = _prefixo_categoria(categoria)
    seq = produtos_repo.contar_por_categoria(categoria) + 1
    while True:
        codigo = f"{prefixo}-{seq:03d}"
        if not produtos_repo.codigo_existe(codigo):
            return codigo
        seq += 1


def cadastrar_produto_service(nome, custo, lucro, preco, quantidade, estoque_minimo, categoria, usuario):
    nome = (nome or "").strip()
    categoria = (categoria or "").strip()
    if not nome:
        raise ValueError("Informe o nome do produto.")
    if not categoria:
        raise ValueError("Selecione uma categoria.")
    if preco < 0 or quantidade < 0 or estoque_minimo < 0 or custo < 0:
        raise ValueError("Valores de produto e estoque nao podem ser negativos.")

    codigo = gerar_codigo_produto(categoria)
    produtos_repo.inserir_produto(codigo, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria)
    if int(quantidade or 0) != 0:
        registrar_movimentacao_estoque_service(
            codigo,
            nome,
            int(quantidade or 0),
            "Entrada",
            "Cadastro inicial de produto",
            usuario,
            0,
            int(quantidade or 0),
        )
    return codigo


def editar_produto_service(codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, usuario):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do produto.")
    if preco < 0 or quantidade < 0 or estoque_minimo < 0 or custo < 0:
        raise ValueError("Valores de produto e estoque nao podem ser negativos.")

    anterior = produtos_repo.buscar_preco_estoque(codigo_p)
    if not anterior:
        raise ValueError("Produto nao localizado no banco de dados.")

    estoque_antigo = int(anterior[0] or 0)
    nome_antigo = anterior[1]
    preco_antigo = float(anterior[2] or 0)
    custo_antigo = float(anterior[3] or 0)
    estoque_novo = int(quantidade or 0)

    produtos_repo.atualizar_produto(codigo_p, nome, custo, lucro, preco, estoque_novo, estoque_minimo)

    if estoque_novo != estoque_antigo:
        registrar_movimentacao_estoque_service(
            codigo_p,
            nome,
            estoque_novo - estoque_antigo,
            "Ajuste",
            "Edicao manual do estoque",
            usuario,
            estoque_antigo,
            estoque_novo,
        )

    alterou_valor = (
        round(float(preco_antigo or 0), 2) != round(float(preco or 0), 2)
        or round(float(custo_antigo or 0), 2) != round(float(custo or 0), 2)
    )
    if alterou_valor:
        produtos_repo.registrar_historico_preco(
            codigo_p,
            nome,
            preco_antigo or 0.0,
            preco or 0.0,
            custo_antigo or 0.0,
            custo or 0.0,
            usuario,
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Edicao de produto",
        )

    return {
        "nome_antigo": nome_antigo,
        "preco_antigo": preco_antigo,
        "preco_novo": preco,
        "estoque_antigo": estoque_antigo,
        "estoque_novo": estoque_novo,
    }


def consultar_produto_edicao(codigo_p):
    return produtos_repo.buscar_edicao(codigo_p)


def listar_estoque_produtos(termo=""):
    return produtos_repo.listar_estoque(termo)


def pesquisar_produtos_venda(termo=""):
    return produtos_repo.pesquisar_para_venda(termo)


def inativar_produto_service(codigo_p):
    produtos_repo.inativar_produto(codigo_p)


def listar_categorias_produto():
    return produtos_repo.listar_categorias()


def adicionar_categoria_produto(nome):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome da categoria.")
    produtos_repo.adicionar_categoria(nome)


def contar_produtos_categoria(categoria):
    return produtos_repo.contar_produtos_ativos_categoria(categoria)


def inativar_categoria_produto(nome):
    produtos_repo.inativar_categoria(nome, datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
