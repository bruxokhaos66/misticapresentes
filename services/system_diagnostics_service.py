import os
from datetime import datetime

from config import DB_PATH
from database import get_connection, realizar_backup


TABELAS_OBRIGATORIAS = [
    "usuarios",
    "login_tentativas",
    "logs",
    "categorias",
    "produtos",
    "clientes",
    "fornecedores",
    "vendas",
    "vendas_itens",
    "movimentacao_estoque",
    "inventario_estoque",
    "caixa_diario",
    "fluxo_caixa",
    "contas_a_pagar",
    "historico_precos",
    "isis_logs",
]


def diagnosticar_banco():
    """Executa diagnóstico somente leitura e retorna dict amigável para tela/Isis."""
    resultado = {
        "ok": True,
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "db_path": DB_PATH,
        "problemas": [],
        "avisos": [],
        "metricas": {},
    }
    if not os.path.exists(DB_PATH):
        resultado["ok"] = False
        resultado["problemas"].append("Banco de dados ainda não existe no caminho configurado.")
        return resultado

    conn = get_connection()
    try:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        faltando = [t for t in TABELAS_OBRIGATORIAS if t not in tabelas]
        if faltando:
            resultado["ok"] = False
            resultado["problemas"].append("Tabelas ausentes: " + ", ".join(faltando))

        checks = {
            "produtos_ativos": "SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1",
            "clientes_ativos": "SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1",
            "vendas_total": "SELECT COUNT(*) FROM vendas",
            "caixas_abertos": "SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'",
            "contas_pendentes": "SELECT COUNT(*) FROM contas_a_pagar WHERE status='Pendente'",
        }
        for nome, sql in checks.items():
            try:
                resultado["metricas"][nome] = int(conn.execute(sql).fetchone()[0] or 0)
            except Exception as exc:
                resultado["avisos"].append(f"Não foi possível calcular {nome}: {exc}")

        if resultado["metricas"].get("caixas_abertos", 0) > 1:
            resultado["ok"] = False
            resultado["problemas"].append("Existe mais de um caixa aberto ao mesmo tempo.")

        inconsistencias = conn.execute(
            """
            SELECT COUNT(*)
            FROM vendas_itens vi
            LEFT JOIN vendas v ON v.id = vi.venda_id
            WHERE v.id IS NULL
            """
        ).fetchone()[0]
        if inconsistencias:
            resultado["ok"] = False
            resultado["problemas"].append(f"Existem {inconsistencias} item(ns) de venda sem venda principal.")

        produtos_negativos = conn.execute("SELECT COUNT(*) FROM produtos WHERE COALESCE(quantidade,0) < 0").fetchone()[0]
        if produtos_negativos:
            resultado["ok"] = False
            resultado["problemas"].append(f"Existem {produtos_negativos} produto(s) com estoque negativo.")
    finally:
        conn.close()
    return resultado


def diagnostico_texto():
    dados = diagnosticar_banco()
    linhas = [f"Diagnóstico do sistema em {dados['data_hora']}", f"Banco: {dados['db_path']}"]
    linhas.append("Status: OK" if dados["ok"] else "Status: ATENÇÃO")
    if dados["metricas"]:
        linhas.append("\nMétricas:")
        for chave, valor in dados["metricas"].items():
            linhas.append(f"- {chave}: {valor}")
    if dados["problemas"]:
        linhas.append("\nProblemas:")
        linhas.extend(f"- {p}" for p in dados["problemas"])
    if dados["avisos"]:
        linhas.append("\nAvisos:")
        linhas.extend(f"- {a}" for a in dados["avisos"])
    return "\n".join(linhas)


def backup_manual():
    caminho = realizar_backup()
    if not caminho:
        raise FileNotFoundError("Nenhum banco encontrado para backup.")
    return caminho
