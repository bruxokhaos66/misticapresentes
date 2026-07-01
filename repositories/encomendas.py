from datetime import datetime
from database import query_db


def criar(cliente, produto, quantidade=1, origem="", custo_estimado=0.0, preco_sugerido=0.0, margem=0.0, observacao=""):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    query_db(
        """
        INSERT INTO encomendas
        (cliente, produto, quantidade, origem, custo_estimado, preco_sugerido, margem, status, observacao, data_criacao, data_atualizacao)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (cliente, produto, int(quantidade or 1), origem, float(custo_estimado or 0), float(preco_sugerido or 0), float(margem or 0), "Pendente", observacao, agora, agora),
        commit=True,
    )


def listar(status=None, limite=50):
    if status:
        return query_db("SELECT id, cliente, produto, quantidade, status, data_criacao FROM encomendas WHERE status=? ORDER BY id DESC LIMIT ?", (status, int(limite)))
    return query_db("SELECT id, cliente, produto, quantidade, status, data_criacao FROM encomendas ORDER BY id DESC LIMIT ?", (int(limite),))
