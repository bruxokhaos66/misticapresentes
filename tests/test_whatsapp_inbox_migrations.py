"""Testes de migração das tabelas da Central de Atendimento WhatsApp
(database/migrations.py::_criar_tabelas_whatsapp_central_atendimento)."""
from __future__ import annotations

import os
import sqlite3
import tempfile

from database.migrations import init_db


def _tabelas(conn) -> set[str]:
    linhas = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in linhas}


def test_migracao_cria_tabelas_em_banco_limpo():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "banco_limpo.db")
        init_db(caminho)
        conn = sqlite3.connect(caminho)
        try:
            tabelas = _tabelas(conn)
            for esperada in (
                "whatsapp_contacts",
                "whatsapp_conversations",
                "whatsapp_messages",
                "whatsapp_webhook_events",
            ):
                assert esperada in tabelas
        finally:
            conn.close()


def test_migracao_e_idempotente_rodando_duas_vezes():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "banco.db")
        init_db(caminho)
        init_db(caminho)  # não deve levantar erro nem duplicar estrutura
        conn = sqlite3.connect(caminho)
        try:
            assert "whatsapp_messages" in _tabelas(conn)
        finally:
            conn.close()


def test_unicidade_wa_id_contato():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "banco.db")
        init_db(caminho)
        conn = sqlite3.connect(caminho)
        try:
            agora = "2026-01-01T00:00:00"
            conn.execute(
                "INSERT INTO whatsapp_contacts (wa_id, first_seen_at, last_seen_at, created_at) VALUES (?,?,?,?)",
                ("5511999998888", agora, agora, agora),
            )
            conn.commit()
            try:
                conn.execute(
                    "INSERT INTO whatsapp_contacts (wa_id, first_seen_at, last_seen_at, created_at) VALUES (?,?,?,?)",
                    ("5511999998888", agora, agora, agora),
                )
                conn.commit()
                assert False, "deveria ter rejeitado wa_id duplicado"
            except sqlite3.IntegrityError:
                pass
        finally:
            conn.close()


def test_unicidade_meta_message_id():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "banco.db")
        init_db(caminho)
        conn = sqlite3.connect(caminho)
        try:
            agora = "2026-01-01T00:00:00"
            conn.execute(
                "INSERT INTO whatsapp_contacts (wa_id, first_seen_at, last_seen_at, created_at) VALUES ('5511999997777',?,?,?)",
                (agora, agora, agora),
            )
            contato_id = conn.execute("SELECT id FROM whatsapp_contacts WHERE wa_id='5511999997777'").fetchone()[0]
            conn.execute(
                "INSERT INTO whatsapp_conversations (contact_id, status, created_at) VALUES (?, 'open', ?)",
                (contato_id, agora),
            )
            conversa_id = conn.execute("SELECT id FROM whatsapp_conversations WHERE contact_id=?", (contato_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO whatsapp_messages (conversation_id, meta_message_id, direction, message_type, status, created_at) "
                "VALUES (?, 'wamid.dup', 'inbound', 'text', 'received', ?)",
                (conversa_id, agora),
            )
            conn.commit()
            try:
                conn.execute(
                    "INSERT INTO whatsapp_messages (conversation_id, meta_message_id, direction, message_type, status, created_at) "
                    "VALUES (?, 'wamid.dup', 'inbound', 'text', 'received', ?)",
                    (conversa_id, agora),
                )
                conn.commit()
                assert False, "deveria ter rejeitado meta_message_id duplicado"
            except sqlite3.IntegrityError:
                pass
        finally:
            conn.close()


def test_unicidade_event_key_webhook():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "banco.db")
        init_db(caminho)
        conn = sqlite3.connect(caminho)
        try:
            agora = "2026-01-01T00:00:00"
            conn.execute(
                "INSERT INTO whatsapp_webhook_events (event_key, event_type, received_at) VALUES ('chave-1','message',?)",
                (agora,),
            )
            conn.commit()
            try:
                conn.execute(
                    "INSERT INTO whatsapp_webhook_events (event_key, event_type, received_at) VALUES ('chave-1','message',?)",
                    (agora,),
                )
                conn.commit()
                assert False, "deveria ter rejeitado event_key duplicado"
            except sqlite3.IntegrityError:
                pass
        finally:
            conn.close()
