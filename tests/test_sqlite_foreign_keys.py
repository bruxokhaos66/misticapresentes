import sqlite3

import pytest

import backend.database as backend_database
import config
import database.connection as connection
from backend.lms import garantir_tabelas_lms
from database.migrations import init_db
from scripts.auditoria_integridade_referencial import auditar


def _preparar_banco(tmp_path, monkeypatch):
    db_path = tmp_path / "fk_test.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(backend_database, "DB_PATH", str(db_path))
    init_db()
    return str(db_path)


def test_get_connection_ativa_foreign_keys(tmp_path, monkeypatch):
    _preparar_banco(tmp_path, monkeypatch)
    conn = connection.get_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_query_db_ativa_foreign_keys(tmp_path, monkeypatch):
    _preparar_banco(tmp_path, monkeypatch)
    resultado = connection.query_db("PRAGMA foreign_keys")
    assert resultado[0][0] == 1


def test_conectar_backend_ativa_foreign_keys(tmp_path, monkeypatch):
    _preparar_banco(tmp_path, monkeypatch)
    with backend_database.conectar() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fk_declarada_rejeita_registro_orfao(tmp_path, monkeypatch):
    db_path = _preparar_banco(tmp_path, monkeypatch)
    with backend_database.conectar() as conn:
        garantir_tabelas_lms(conn)

    with pytest.raises(sqlite3.IntegrityError):
        with backend_database.conectar() as conn:
            conn.execute(
                """
                INSERT INTO curso_aulas
                    (modulo_id, titulo, tipo, ordem, obrigatoria, publicado, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (999999, "Aula orfa", "texto", 0, 1, 1),
            )

    # A inserção não deve ter persistido (rollback automático do rollback do
    # gerenciador de contexto ao propagar a exceção).
    with backend_database.conectar() as conn:
        total = conn.execute("SELECT COUNT(*) FROM curso_aulas").fetchone()[0]
    assert total == 0

    assert auditar(db_path) == []


def test_auditoria_detecta_registro_orfao_pre_existente(tmp_path, monkeypatch):
    db_path = _preparar_banco(tmp_path, monkeypatch)
    with backend_database.conectar() as conn:
        garantir_tabelas_lms(conn)

    # Insere um registro órfão contornando a aplicação (conexão crua sem
    # `PRAGMA foreign_keys`), simulando dados legados/anteriores à correção.
    raw = sqlite3.connect(db_path)
    try:
        raw.execute(
            """
            INSERT INTO curso_aulas
                (modulo_id, titulo, tipo, ordem, obrigatoria, publicado, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (999999, "Aula orfa legada", "texto", 0, 1, 1),
        )
        raw.commit()
    finally:
        raw.close()

    violacoes = auditar(db_path)
    assert len(violacoes) == 1
    assert violacoes[0]["table"] == "curso_aulas"
