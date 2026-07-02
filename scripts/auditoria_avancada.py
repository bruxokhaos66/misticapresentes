"""Auditoria avancada do Mística Presentes.

Execute na raiz do projeto:
    python scripts/auditoria_avancada.py

Esta auditoria usa banco temporario em memoria/arquivo temporario e nao altera
produtos, vendas, caixa ou usuarios reais.

Testa:
- login app vendedor/adm com sessao
- senha minima do app
- venda simulada
- baixa de estoque simulada
- cancelamento simulado com retorno de estoque
- geracao de relatorio TXT e HTML
"""
from __future__ import annotations

import html
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import hash_password_pbkdf2
import api.app_auth as app_auth

RELATORIO_DIR = Path.home() / "Documents" / "Mistica_Auditorias"

OKS: list[str] = []
AVISOS: list[str] = []
ERROS: list[str] = []


def ok(msg: str) -> None:
    OKS.append(msg)


def aviso(msg: str) -> None:
    AVISOS.append(msg)


def erro(msg: str) -> None:
    ERROS.append(msg)


class BancoTemporario:
    def __init__(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(prefix="mistica_auditoria_", suffix=".db", delete=False)
        self.path = self.tmp.name
        self.tmp.close()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def fechar(self) -> None:
        try:
            self.conn.close()
        finally:
            try:
                os.unlink(self.path)
            except Exception:
                pass

    def query(self, sql: str, params=(), commit: bool = False):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        dados = cur.fetchall()
        if commit:
            self.conn.commit()
        return [tuple(x) for x in dados]


def preparar_banco_fake(db: BancoTemporario) -> None:
    db.query("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, senha_hash TEXT, senha_salt TEXT, perfil TEXT, ativo INTEGER DEFAULT 1)", commit=True)
    db.query("CREATE TABLE logs (id INTEGER PRIMARY KEY, usuario TEXT, acao TEXT, detalhes TEXT, data_hora TEXT)", commit=True)
    db.query("CREATE TABLE app_sessoes (sessao TEXT PRIMARY KEY, login TEXT, nome TEXT, perfil TEXT, criada_em TEXT, expira_em TEXT, ultimo_acesso TEXT)", commit=True)
    db.query("CREATE TABLE produtos (id INTEGER PRIMARY KEY, codigo_p TEXT, nome TEXT, preco REAL, quantidade INTEGER, custo REAL DEFAULT 0, estoque_minimo INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1)", commit=True)
    db.query("CREATE TABLE vendas (id INTEGER PRIMARY KEY, cliente TEXT, data_venda TEXT, data_iso TEXT, subtotal REAL, desconto REAL, taxa REAL, total_final REAL, forma_pagamento TEXT, vendedor TEXT, status TEXT DEFAULT 'Concluído')", commit=True)
    db.query("CREATE TABLE vendas_itens (id INTEGER PRIMARY KEY, venda_id INTEGER, codigo_p TEXT, nome_p TEXT, quantidade INTEGER, valor_unitario REAL, valor_total REAL)", commit=True)
    db.query("CREATE TABLE movimentacao_estoque (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, quantidade INTEGER, tipo TEXT, motivo TEXT, usuario TEXT, data_hora TEXT, estoque_anterior INTEGER, estoque_posterior INTEGER, venda_id INTEGER)", commit=True)

    salt_adm = "salt_adm"
    salt_vend = "salt_vend"
    db.query(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,1)",
        ("Administrador Teste", "admin_teste", hash_password_pbkdf2("1234", salt_adm.encode("utf-8")), salt_adm, "adm"),
        commit=True,
    )
    db.query(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,1)",
        ("Vendedor Teste", "vendedor_teste", hash_password_pbkdf2("1234", salt_vend.encode("utf-8")), salt_vend, "vendedor"),
        commit=True,
    )
    db.query("INSERT INTO produtos (codigo_p, nome, preco, quantidade, custo, estoque_minimo) VALUES (?,?,?,?,?,?)", ("INC001", "Incenso Teste", 10.0, 10, 4.0, 2), commit=True)


def testar_login_app(db: BancoTemporario) -> None:
    original_query = app_auth.query_db
    original_sessoes = app_auth.SESSOES_APP
    app_auth.query_db = db.query
    app_auth.SESSOES_APP = {}
    try:
        curto = app_auth.login_app("admin_teste", "123")
        if curto.get("ok"):
            erro("Login aceitou senha com menos de 4 caracteres")
        else:
            ok("Login bloqueia senha menor que 4 caracteres")

        adm = app_auth.login_app("admin_teste", "1234")
        if adm.get("ok") and adm.get("usuario", {}).get("perfil") == "adm":
            ok("Login ADM reconhecido corretamente")
        else:
            erro(f"Login ADM falhou: {adm}")

        vend = app_auth.login_app("vendedor_teste", "1234")
        if vend.get("ok") and vend.get("usuario", {}).get("perfil") == "vendedor":
            ok("Login vendedor reconhecido corretamente")
        else:
            erro(f"Login vendedor falhou: {vend}")

        sessao = vend.get("sessao")
        dados = app_auth.validar_sessao_app(sessao)
        if dados and dados.get("perfil") == "vendedor":
            ok("Sessao persistente do vendedor validada")
        else:
            erro("Sessao persistente do vendedor nao validou")

        app_auth.logout_app(sessao)
        if app_auth.validar_sessao_app(sessao) is None:
            ok("Logout remove sessao do app")
        else:
            erro("Logout nao removeu sessao do app")
    finally:
        app_auth.query_db = original_query
        app_auth.SESSOES_APP = original_sessoes


def venda_simulada(db: BancoTemporario) -> int:
    produto = db.query("SELECT codigo_p, nome, preco, quantidade FROM produtos WHERE codigo_p=?", ("INC001",))[0]
    codigo, nome, preco, estoque = produto
    qtd = 2
    if estoque < qtd:
        raise RuntimeError("Estoque insuficiente no teste fake")
    total = float(preco) * qtd
    hoje_br = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    hoje_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.query(
        "INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Cliente Teste", hoje_br, hoje_iso, total, 0, 0, total, "PIX", "Vendedor Teste", "Concluído"),
        commit=True,
    )
    venda_id = db.query("SELECT MAX(id) FROM vendas")[0][0]
    db.query("INSERT INTO vendas_itens (venda_id, codigo_p, nome_p, quantidade, valor_unitario, valor_total) VALUES (?,?,?,?,?,?)", (venda_id, codigo, nome, qtd, preco, total), commit=True)
    db.query("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (estoque - qtd, codigo), commit=True)
    db.query("INSERT INTO movimentacao_estoque (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (codigo, nome, qtd, "saida", "Venda simulada", "Auditoria", hoje_br, estoque, estoque - qtd, venda_id), commit=True)
    return int(venda_id)


def cancelar_venda_simulada(db: BancoTemporario, venda_id: int) -> None:
    itens = db.query("SELECT codigo_p, nome_p, quantidade FROM vendas_itens WHERE venda_id=?", (venda_id,))
    for codigo, nome, qtd in itens:
        estoque_atual = db.query("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
        novo = int(estoque_atual) + int(qtd)
        db.query("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (novo, codigo), commit=True)
        db.query("INSERT INTO movimentacao_estoque (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (codigo, nome, qtd, "entrada", "Cancelamento simulado", "Auditoria", datetime.now().strftime("%d/%m/%Y %H:%M:%S"), estoque_atual, novo, venda_id), commit=True)
    db.query("UPDATE vendas SET status='Cancelado' WHERE id=?", (venda_id,), commit=True)


def testar_venda_cancelamento_estoque(db: BancoTemporario) -> None:
    estoque_inicial = db.query("SELECT quantidade FROM produtos WHERE codigo_p='INC001'")[0][0]
    venda_id = venda_simulada(db)
    estoque_apos_venda = db.query("SELECT quantidade FROM produtos WHERE codigo_p='INC001'")[0][0]
    if estoque_apos_venda == estoque_inicial - 2:
        ok("Venda simulada baixou estoque corretamente")
    else:
        erro(f"Baixa de estoque incorreta: inicial {estoque_inicial}, apos venda {estoque_apos_venda}")

    cancelar_venda_simulada(db, venda_id)
    estoque_final = db.query("SELECT quantidade FROM produtos WHERE codigo_p='INC001'")[0][0]
    status = db.query("SELECT status FROM vendas WHERE id=?", (venda_id,))[0][0]
    if estoque_final == estoque_inicial and status == "Cancelado":
        ok("Cancelamento simulado retornou estoque e marcou venda como Cancelado")
    else:
        erro(f"Cancelamento incorreto: estoque final {estoque_final}, status {status}")

    movs = db.query("SELECT COUNT(*) FROM movimentacao_estoque WHERE venda_id=?", (venda_id,))[0][0]
    if int(movs) >= 2:
        ok("Movimentacao de estoque registrada para venda e cancelamento")
    else:
        erro("Movimentacao de estoque insuficiente no teste fake")


def gerar_relatorio() -> tuple[Path, Path]:
    RELATORIO_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt = RELATORIO_DIR / f"auditoria_avancada_{stamp}.txt"
    html_path = RELATORIO_DIR / f"auditoria_avancada_{stamp}.html"

    linhas = []
    linhas.append("Mistica Presentes - Auditoria Avancada")
    linhas.append(datetime.now().strftime("Gerado em %d/%m/%Y %H:%M:%S"))
    linhas.append("")
    linhas.append("OK:")
    linhas.extend([f"[OK] {x}" for x in OKS] or ["Nenhum OK registrado."])
    linhas.append("")
    linhas.append("AVISOS:")
    linhas.extend([f"[AVISO] {x}" for x in AVISOS] or ["Nenhum aviso."])
    linhas.append("")
    linhas.append("ERROS:")
    linhas.extend([f"[ERRO] {x}" for x in ERROS] or ["Nenhum erro."])
    txt.write_text("\n".join(linhas), encoding="utf-8")

    def lista_html(titulo: str, itens: list[str], classe: str) -> str:
        conteudo = "".join(f"<li>{html.escape(x)}</li>" for x in itens) or "<li>Nenhum.</li>"
        return f"<h2>{html.escape(titulo)}</h2><ul class='{classe}'>{conteudo}</ul>"

    pagina = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Auditoria Mística</title>
<style>body{{font-family:Arial;background:#121018;color:#f6f0df;padding:24px}}h1,h2{{color:#d8b56d}}.ok li{{color:#9be0bc}}.aviso li{{color:#ffd27d}}.erro li{{color:#ff9b9b}}</style></head><body>
<h1>Mística Presentes - Auditoria Avançada</h1><p>{html.escape(datetime.now().strftime('%d/%m/%Y %H:%M:%S'))}</p>
{lista_html('OK', OKS, 'ok')}{lista_html('Avisos', AVISOS, 'aviso')}{lista_html('Erros', ERROS, 'erro')}
</body></html>"""
    html_path.write_text(pagina, encoding="utf-8")
    return txt, html_path


def main() -> None:
    print("=" * 72)
    print("Mística Presentes - Auditoria avançada")
    print("=" * 72)
    db = BancoTemporario()
    try:
        preparar_banco_fake(db)
        ok("Banco temporario criado sem afetar banco real")
        testar_login_app(db)
        testar_venda_cancelamento_estoque(db)
    except Exception as exc:
        erro(f"Falha inesperada na auditoria avancada: {exc}")
    finally:
        db.fechar()

    txt, html_path = gerar_relatorio()
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
        print("  Nenhum erro.")
    print("\nRelatorio TXT:", txt)
    print("Relatorio HTML:", html_path)
    if ERROS:
        sys.exit(1)


if __name__ == "__main__":
    main()
