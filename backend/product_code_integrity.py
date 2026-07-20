from __future__ import annotations

import functools
import sqlite3
from typing import Optional

from fastapi import HTTPException


MENSAGEM_CODIGO_DUPLICADO = "Já existe um produto com este código, inclusive entre os produtos inativos."


def buscar_codigo_duplicado_incluindo_inativos(conn, codigo: Optional[str], *, excluir_id: Optional[int] = None):
    """Alinha a validação da aplicação ao índice único real do banco.

    Um produto inativo continua existindo e pode ser reativado; portanto, seu
    código não fica livre para um segundo cadastro. A busca é normalizada da
    mesma forma usada pelo cadastro e não filtra ``ativo``.
    """
    if not codigo:
        return None
    sql = "SELECT id, ativo FROM produtos WHERE UPPER(TRIM(codigo_p))=?"
    parametros: list[object] = [str(codigo).strip().upper()]
    if excluir_id is not None:
        sql += " AND id<>?"
        parametros.append(excluir_id)
    return conn.execute(sql, tuple(parametros)).fetchone()


def converter_erro_integridade_produto(erro: sqlite3.IntegrityError) -> HTTPException | None:
    """Converte somente violações de unicidade do código em HTTP 409.

    Outras violações de integridade continuam sendo propagadas para não
    esconder problemas de schema ou dados sem relação com código de produto.
    """
    mensagem = str(erro).lower()
    if "unique constraint failed" in mensagem and "produtos.codigo_p" in mensagem:
        return HTTPException(status_code=409, detail=MENSAGEM_CODIGO_DUPLICADO)
    return None


def _proteger_endpoint(endpoint):
    if getattr(endpoint, "__mistica_codigo_integridade__", False):
        return endpoint

    @functools.wraps(endpoint)
    def protegido(*args, **kwargs):
        try:
            return endpoint(*args, **kwargs)
        except sqlite3.IntegrityError as erro:
            traduzido = converter_erro_integridade_produto(erro)
            if traduzido is not None:
                raise traduzido from erro
            raise

    protegido.__mistica_codigo_integridade__ = True
    return protegido


def instalar_integridade_codigo_produto() -> None:
    """Instala a correção nas rotas já registradas pelo FastAPI.

    O patch cobre tanto a validação anterior ao INSERT/UPDATE quanto uma
    corrida concorrente entre duas requisições, quando apenas o índice único do
    SQLite consegue decidir qual escrita vence.
    """
    from backend import product_routes

    product_routes._codigo_duplicado = buscar_codigo_duplicado_incluindo_inativos

    endpoints_alvo = {"criar_produto_completo", "atualizar_produto_completo"}
    for rota in product_routes.router.routes:
        endpoint = getattr(rota, "endpoint", None)
        if not endpoint or getattr(endpoint, "__name__", "") not in endpoints_alvo:
            continue
        protegido = _proteger_endpoint(endpoint)
        rota.endpoint = protegido
        if getattr(rota, "dependant", None) is not None:
            rota.dependant.call = protegido
