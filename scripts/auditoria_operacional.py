"""Auditoria operacional do Mística Presentes.

Execute na raiz do projeto:
    python scripts/auditoria_operacional.py

Verifica problemas comuns antes de gerar EXE/APK ou abrir a loja.
Nao altera vendas, estoque, usuarios ou caixa.
"""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH
from database import init_db, query_db
from api.service import dashboard_api, metas_vendas_api

ERROS = []
AVISOS = []
OKS = []


def ok(msg):
    OKS.append(msg)


def aviso(msg):
    AVISOS.append(msg)


def erro(msg):
    ERROS.append(msg)


def verificar_arquivo(caminho, obrigatorio=True):
    p = ROOT / caminho
    if p.exists():
        ok(f"Arquivo encontrado: {caminho}")
    elif obrigatorio:
        erro(f"Arquivo ausente: {caminho}")
    else:
        aviso(f"Arquivo opcional ausente: {caminho}")


def verificar_imports():
    for modulo in [
        "customtkinter",
        "fastapi",
        "uvicorn",
        "pyinstaller",
    ]:
        try:
            importlib.import_module(modulo)
            ok(f"Dependencia OK: {modulo}")
        except Exception as exc:
            erro(f"Dependencia com problema: {modulo} - {exc}")


def verificar_banco():
    try:
        init_db()
        ok("Banco inicializado/migrado sem erro")
    except Exception as exc:
        erro(f"Falha ao inicializar/migrar banco: {exc}")
        return

    if not os.path.exists(DB_PATH):
        erro(f"Banco nao encontrado em: {DB_PATH}")
        return
    ok(f"Banco encontrado: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integridade = cur.fetchone()[0]
        conn.close()
        if str(integridade).lower() == "ok":
            ok("Integridade SQLite OK")
        else:
            erro(f"Integridade SQLite retornou: {integridade}")
    except Exception as exc:
        erro(f"Falha ao verificar integridade SQLite: {exc}")

    for tabela in ["produtos", "vendas", "usuarios", "caixa_diario", "fluxo_caixa", "logs"]:
        try:
            query_db(f"SELECT COUNT(*) FROM {tabela}")
            ok(f"Tabela OK: {tabela}")
        except Exception as exc:
            erro(f"Tabela com problema: {tabela} - {exc}")

    try:
        usuarios_sem_cpf = query_db("SELECT COUNT(*) FROM usuarios WHERE COALESCE(cpf,'')='' AND COALESCE(ativo,1)=1")
        qtd = int(usuarios_sem_cpf[0][0] or 0)
        if qtd:
            aviso(f"Usuarios ativos sem CPF cadastrado: {qtd}. Se futuramente usar recuperacao por CPF, cadastre CPF.")
        else:
            ok("Usuarios ativos com CPF cadastrado")
    except Exception:
        pass


def verificar_dashboard_api():
    try:
        data = dashboard_api()
        for chave in ["vendas_hoje", "metas_vendas", "caixa", "ultimas_vendas", "estoque_baixo", "alertas_isis"]:
            if chave not in data:
                erro(f"Dashboard sem campo: {chave}")
        ok("Dashboard API gerado sem erro")
    except Exception as exc:
        erro(f"Falha ao gerar dashboard API: {exc}")

    try:
        metas = metas_vendas_api()
        if float(metas.get("meta_semana", 0)) != 1000.0:
            erro("Meta semanal diferente de R$ 1.000,00")
        else:
            ok("Meta semanal OK: R$ 1.000,00")
        if float(metas.get("bonus_comissao", 0)) not in (0.0, 100.0):
            erro("Bonus de comissao deveria ser 0 ou 100")
        else:
            ok("Bonus de comissao OK")
    except Exception as exc:
        erro(f"Falha ao verificar metas: {exc}")


def verificar_fontes():
    for caminho in [
        "app.py",
        "mistica_presentes.py",
        "api/main.py",
        "api/service.py",
        "api/painel.html",
        "scripts/iniciar_servidor_dedicado.py",
        "mobile_android/app/build.gradle",
        "mobile_android/app/src/main/AndroidManifest.xml",
    ]:
        verificar_arquivo(caminho)


def main():
    print("=" * 72)
    print("Mística Presentes - Auditoria operacional")
    print("=" * 72)
    verificar_fontes()
    verificar_imports()
    verificar_banco()
    verificar_dashboard_api()

    print("\nOK:")
    for item in OKS:
        print("  [OK]", item)
    print("\nAVISOS:")
    if AVISOS:
        for item in AVISOS:
            print("  [AVISO]", item)
    else:
        print("  Nenhum aviso.")
    print("\nERROS:")
    if ERROS:
        for item in ERROS:
            print("  [ERRO]", item)
    else:
        print("  Nenhum erro critico encontrado.")

    if ERROS:
        print("\nResultado: FALHOU. Corrija os erros antes de gerar EXE/APK.")
        sys.exit(1)
    print("\nResultado: APROVADO para gerar EXE/APK.")


if __name__ == "__main__":
    main()
