from datetime import datetime

from database import get_connection


DEMO_PREFIXO = "[DEMO]"


def criar_modo_demonstracao():
    """Cria dados fictícios sem apagar dados reais.

    Seguro para testes: usa prefixo [DEMO] para facilitar identificação.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cur = conn.cursor()
    try:
        categorias = ["Incensos", "Velas", "Pedras", "Aromas"]
        for cat in categorias:
            cur.execute("INSERT OR IGNORE INTO categorias (nome, ativo) VALUES (?, 1)", (cat,))

        produtos = [
            ("DEMO-INC-001", f"{DEMO_PREFIXO} Incenso Natural", 2.50, 100.0, 5.00, 30, 5, "Incensos"),
            ("DEMO-VEL-001", f"{DEMO_PREFIXO} Vela Aromática", 8.00, 75.0, 14.00, 12, 3, "Velas"),
            ("DEMO-PED-001", f"{DEMO_PREFIXO} Pedra Ametista", 4.00, 100.0, 8.00, 20, 4, "Pedras"),
        ]
        for p in produtos:
            cur.execute(
                """
                INSERT OR IGNORE INTO produtos
                (codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria, ativo, criado_em)
                VALUES (?,?,?,?,?,?,?,?,1,?)
                """,
                (*p, agora),
            )

        clientes = [
            (f"{DEMO_PREFIXO} Cliente Maria", "49999990001", "", "08/06", "Cliente fictício"),
            (f"{DEMO_PREFIXO} Cliente João", "49999990002", "", "15/07", "Cliente fictício"),
        ]
        for c in clientes:
            cur.execute(
                """
                INSERT INTO clientes (nome, telefone, cpf, nascimento, observacao, ativo, criado_em)
                SELECT ?,?,?,?,?,1,?
                WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE nome=? LIMIT 1)
                """,
                (*c, agora, c[0]),
            )

        conn.commit()
        return {
            "produtos_demo": len(produtos),
            "clientes_demo": len(clientes),
            "observacao": "Dados fictícios criados/confirmados com prefixo [DEMO].",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remover_modo_demonstracao():
    """Remove apenas dados com prefixo/código DEMO, sem apagar dados reais."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM clientes WHERE nome LIKE ?", (f"{DEMO_PREFIXO}%",))
        clientes = cur.rowcount
        cur.execute("DELETE FROM produtos WHERE codigo_p LIKE 'DEMO-%' OR nome LIKE ?", (f"{DEMO_PREFIXO}%",))
        produtos = cur.rowcount
        conn.commit()
        return {"produtos_removidos": produtos, "clientes_removidos": clientes}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
