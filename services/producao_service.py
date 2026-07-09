from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from config import BACKUP_DIR, DB_PATH, DOCS_PATH
from database.migrations import init_db
from database.connection import get_connection


TABELAS_OPERACIONAIS = [
    "vendas_itens",
    "vendas",
    "fluxo_caixa",
    "caixa_diario",
    "contas_a_pagar",
    "movimentacao_estoque",
    "historico_precos",
    "inventario_estoque",
    "encomendas",
    "pesquisas_online",
    "isis_logs",
    "logs",
]

TABELAS_CADASTRO = [
    "clientes",
    "fornecedores",
]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _tabela_existe(conn: sqlite3.Connection, tabela: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,))
    return cur.fetchone() is not None


def _contar(conn: sqlite3.Connection, tabela: str) -> int:
    if not _tabela_existe(conn, tabela):
        return 0
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {tabela}")
        return int(cur.fetchone()[0] or 0)
    except Exception:
        return 0


def _limpar_tabela(conn: sqlite3.Connection, tabela: str) -> int:
    if not _tabela_existe(conn, tabela):
        return 0
    total = _contar(conn, tabela)
    conn.execute(f"DELETE FROM {tabela}")
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (tabela,))
    except Exception:
        pass
    return total


def _criar_backup_banco() -> str:
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(DB_PATH):
        return ""
    destino = os.path.join(BACKUP_DIR, f"backup_preparar_producao_{_timestamp()}.db")
    origem = sqlite3.connect(DB_PATH)
    backup = sqlite3.connect(destino)
    try:
        origem.backup(backup)
    finally:
        backup.close()
        origem.close()
    return destino


def _salvar_relatorio(linhas: list[str]) -> str:
    pasta = Path(DOCS_PATH) / "Mistica_Relatorios_Manutencao"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"relatorio_preparar_producao_{_timestamp()}.txt"
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return str(caminho)


def preparar_sistema_para_producao(
    *,
    operador: str = "Sistema",
    remover_produtos: bool = True,
    remover_clientes: bool = True,
    remover_fornecedores: bool = True,
    limpar_memoria_isis: bool = False,
) -> dict[str, Any]:
    """Limpa dados de teste para iniciar uso real em producao.

    A funcao sempre cria backup antes da limpeza. Ela preserva a estrutura do banco,
    configuracoes, Launcher, atualizador e o usuario admin.
    """
    init_db()
    backup_path = _criar_backup_banco()
    removidos: dict[str, int] = {}
    alteracoes: list[str] = []

    conn = get_connection()
    try:
        conn.execute("BEGIN")

        for tabela in TABELAS_OPERACIONAIS:
            removidos[tabela] = _limpar_tabela(conn, tabela)

        if remover_clientes:
            removidos["clientes"] = _limpar_tabela(conn, "clientes")
        else:
            removidos["clientes"] = 0

        if remover_fornecedores:
            removidos["fornecedores"] = _limpar_tabela(conn, "fornecedores")
        else:
            removidos["fornecedores"] = 0

        if remover_produtos:
            removidos["produtos"] = _limpar_tabela(conn, "produtos")
            alteracoes.append("Produtos ficticios removidos.")
        else:
            if _tabela_existe(conn, "produtos"):
                total_produtos = _contar(conn, "produtos")
                conn.execute("UPDATE produtos SET quantidade=0")
                removidos["produtos"] = 0
                alteracoes.append(f"Produtos mantidos e estoque zerado em {total_produtos} item(ns).")

        if limpar_memoria_isis:
            removidos["isis_memoria"] = _limpar_tabela(conn, "isis_memoria")
        else:
            removidos["isis_memoria"] = 0

        if _tabela_existe(conn, "usuarios"):
            total_usuarios = _contar(conn, "usuarios")
            conn.execute("DELETE FROM usuarios WHERE COALESCE(lower(login),'') <> 'admin'")
            try:
                conn.execute("UPDATE usuarios SET ativo=1, perfil=COALESCE(NULLIF(perfil,''),'adm') WHERE lower(login)='admin'")
            except Exception:
                pass
            restantes = _contar(conn, "usuarios")
            removidos["usuarios_nao_admin"] = max(0, total_usuarios - restantes)

        try:
            conn.execute("VACUUM")
        except Exception:
            pass

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    total_removido = sum(int(v or 0) for v in removidos.values())
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linhas = [
        "MISTICA PRESENTES - PREPARACAO PARA PRODUCAO",
        "=" * 58,
        f"Data/hora: {agora}",
        f"Operador: {operador}",
        f"Banco: {DB_PATH}",
        f"Backup criado: {backup_path or 'Banco ainda nao existia'}",
        "",
        "Resumo de limpeza:",
    ]
    for tabela, total in sorted(removidos.items()):
        linhas.append(f"- {tabela}: {total} registro(s) removido(s)")
    if alteracoes:
        linhas.append("")
        linhas.append("Alteracoes adicionais:")
        for item in alteracoes:
            linhas.append(f"- {item}")
    linhas.extend([
        "",
        f"Total aproximado removido: {total_removido}",
        "",
        "Itens preservados:",
        "- Estrutura do banco",
        "- Configuracoes do sistema",
        "- Launcher e atualizador",
        "- Usuario admin",
        "- Categorias padrao",
        "- Backup anterior a limpeza",
    ])
    relatorio_path = _salvar_relatorio(linhas)
    return {
        "ok": True,
        "backup": backup_path,
        "relatorio": relatorio_path,
        "removidos": removidos,
        "total_removido": total_removido,
        "mensagem": "Sistema preparado para producao com backup e relatorio.",
    }


__all__ = ["preparar_sistema_para_producao"]
