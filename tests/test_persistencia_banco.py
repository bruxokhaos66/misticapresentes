"""Testes de sobrevivência do banco SQLite (Fase 1 - PR 4).

Nunca usa o banco de produção: cada teste aponta `DB_PATH` para um arquivo
temporário isolado (tmp_path), simulando abertura, fechamento, reinício e
recuperação sem tocar em dados reais.
"""

import sqlite3
import threading

import database.connection as connection
import database.migrations as migrations
from database.migrations import init_db


def _usar_banco_temporario(monkeypatch, tmp_path, nome="teste_persistencia.db"):
    caminho = str(tmp_path / nome)
    monkeypatch.setattr(connection, "DB_PATH", caminho)
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))
    return caminho


def test_banco_e_criado_automaticamente_ao_inicializar(monkeypatch, tmp_path):
    caminho = _usar_banco_temporario(monkeypatch, tmp_path)
    assert not (tmp_path / "teste_persistencia.db").exists()

    init_db()

    assert (tmp_path / "teste_persistencia.db").exists()
    tabelas = connection.query_db("SELECT name FROM sqlite_master WHERE type='table'")
    nomes = {row[0] for row in tabelas}
    assert "produtos" in nomes
    assert "usuarios" in nomes


def test_reinicializacao_e_idempotente(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-1", "Produto Teste", 10.0, 5),
        commit=True,
    )

    # Simula um segundo start (ex.: outro redeploy) rodando as migrações de novo.
    init_db()
    init_db()

    linhas = connection.query_db("SELECT nome FROM produtos WHERE codigo_p='COD-1'")
    assert len(linhas) == 1
    assert linhas[0][0] == "Produto Teste"


def test_conexao_fecha_e_libera_o_arquivo(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()

    conn = connection.get_connection()
    conn.execute("INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)", ("COD-2", "X", 1.0, 1))
    conn.commit()
    conn.close()

    # Uma nova conexão precisa conseguir abrir o mesmo arquivo sem lock pendente.
    conn2 = sqlite3.connect(connection.DB_PATH, timeout=5)
    total = conn2.execute("SELECT COUNT(*) FROM produtos WHERE codigo_p='COD-2'").fetchone()[0]
    conn2.close()
    assert total == 1


def test_dados_sobrevivem_a_reabertura_simulando_restart(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO clientes (nome, telefone) VALUES (?,?)",
        ("Cliente Persistente", "49999990000"),
        commit=True,
    )

    # "Restart": nenhum estado em memória do processo é reaproveitado, apenas
    # o caminho do arquivo -- uma nova conexão do zero, como após um reboot.
    init_db()
    linhas = connection.query_db("SELECT nome FROM clientes WHERE nome='Cliente Persistente'")
    assert len(linhas) == 1


def test_leitura_imediatamente_apos_escrita(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-3", "Produto Imediato", 20.0, 2),
        commit=True,
    )
    linha = connection.query_db("SELECT quantidade FROM produtos WHERE codigo_p='COD-3'")
    assert linha[0][0] == 2


def test_acesso_simultaneo_de_duas_conexoes_nao_corrompe_o_banco(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-CONC", "Produto Concorrente", 5.0, 100),
        commit=True,
    )

    erros = []

    def _baixar_estoque():
        try:
            conn = sqlite3.connect(connection.DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "UPDATE produtos SET quantidade = quantidade - 1 WHERE codigo_p='COD-CONC'"
            )
            conn.commit()
            conn.close()
        except Exception as exc:  # pragma: no cover - só have o teste falhar com detalhe
            erros.append(exc)

    threads = [threading.Thread(target=_baixar_estoque) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros
    linha = connection.query_db("SELECT quantidade FROM produtos WHERE codigo_p='COD-CONC'")
    assert linha[0][0] == 90


def test_banco_e_recriado_se_arquivo_for_removido_apos_um_restart(monkeypatch, tmp_path):
    caminho = _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-4", "Produto Antes", 1.0, 1),
        commit=True,
    )

    # Simula disco efêmero: o arquivo desaparece entre um restart e outro.
    import os

    os.remove(caminho)
    assert not (tmp_path / "teste_persistencia.db").exists()

    # A aplicação deve conseguir recriar o schema sem quebrar (mesmo que os
    # dados antigos não existam mais -- é exatamente o risco que este PR
    # documenta e monitora via /api/health e os logs de inicialização).
    init_db()
    assert (tmp_path / "teste_persistencia.db").exists()
    linhas = connection.query_db("SELECT * FROM produtos WHERE codigo_p='COD-4'")
    assert linhas == []
