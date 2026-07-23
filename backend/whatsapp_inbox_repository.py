"""Acesso a dados da Central de Atendimento WhatsApp (mensagens recebidas de
clientes, conversas e respostas do painel).

Completamente separado das tabelas de notificações administrativas
(backend/whatsapp_outbox.py / notification_outbox) -- nenhuma função aqui lê
ou escreve nessas tabelas, e vice-versa. Toda função recebe uma conexão já
aberta (``backend.database.conectar()``) e nunca abre a sua própria, para que
o chamador controle a transação (commit único por requisição/evento de
webhook).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from backend.whatsapp_flags import mascarar_numero_whatsapp, normalizar_numero_whatsapp

STATUS_CONVERSA_VALIDOS = {"open", "pending", "resolved", "archived"}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def sanitizar_texto(valor: str | None, *, limite: int = 4096) -> str | None:
    """Remove caracteres de controle (nunca executa/renderiza HTML vindo da
    mensagem -- isso é responsabilidade do frontend via textContent, mas o
    texto persistido também nunca deve carregar bytes de controle) e trunca
    para um limite defensivo."""
    if valor is None:
        return None
    texto = "".join(ch for ch in str(valor) if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    texto = texto.strip()
    return texto[:limite] if texto else None


def sanitizar_nome_perfil(valor: str | None) -> str | None:
    return sanitizar_texto(valor, limite=120)


def upsert_contact(conn, *, wa_id: str, profile_name: str | None) -> dict[str, Any]:
    """Cria ou atualiza o contato pelo wa_id (identificador estável da Meta).
    Nunca sobrescreve profile_name com vazio (mensagens de status/localização
    podem não trazer o nome de perfil)."""
    wa_id_normalizado = _somente_digitos(wa_id)
    if not wa_id_normalizado:
        raise ValueError("wa_id vazio ou inválido.")
    agora = _agora()
    phone_e164 = normalizar_numero_whatsapp(wa_id_normalizado) or wa_id_normalizado
    phone_last4 = phone_e164[-4:] if len(phone_e164) >= 4 else phone_e164
    nome_sanitizado = sanitizar_nome_perfil(profile_name)

    existente = conn.execute("SELECT * FROM whatsapp_contacts WHERE wa_id=?", (wa_id_normalizado,)).fetchone()
    if existente:
        conn.execute(
            """
            UPDATE whatsapp_contacts
               SET profile_name=COALESCE(?, profile_name), last_seen_at=?, updated_at=?
             WHERE id=?
            """,
            (nome_sanitizado, agora, agora, existente["id"]),
        )
        return dict(conn.execute("SELECT * FROM whatsapp_contacts WHERE id=?", (existente["id"],)).fetchone())

    cur = conn.execute(
        """
        INSERT INTO whatsapp_contacts
            (wa_id, phone_e164, phone_last4, profile_name, first_seen_at, last_seen_at, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (wa_id_normalizado, phone_e164, phone_last4, nome_sanitizado, agora, agora, agora, agora),
    )
    return dict(conn.execute("SELECT * FROM whatsapp_contacts WHERE id=?", (cur.lastrowid,)).fetchone())


def obter_ou_criar_conversa(conn, *, contact_id: int) -> dict[str, Any]:
    """Uma conversa aberta/pendente por contato -- se a última conversa desse
    contato já estiver resolvida/arquivada, abre uma nova em vez de reabrir
    silenciosamente uma conversa que o administrador já encerrou."""
    linha = conn.execute(
        """
        SELECT * FROM whatsapp_conversations
         WHERE contact_id=? AND status IN ('open','pending')
         ORDER BY id DESC LIMIT 1
        """,
        (contact_id,),
    ).fetchone()
    if linha:
        return dict(linha)
    agora = _agora()
    cur = conn.execute(
        """
        INSERT INTO whatsapp_conversations (contact_id, status, unread_count, created_at, updated_at)
        VALUES (?, 'open', 0, ?, ?)
        """,
        (contact_id, agora, agora),
    )
    return dict(conn.execute("SELECT * FROM whatsapp_conversations WHERE id=?", (cur.lastrowid,)).fetchone())


def registrar_mensagem_recebida(
    conn,
    *,
    conversation_id: int,
    meta_message_id: str | None,
    message_type: str,
    text_body: str | None = None,
    media_id: str | None = None,
    media_mime_type: str | None = None,
    reply_to_meta_message_id: str | None = None,
    timestamp_meta: str | None = None,
) -> tuple[int | None, bool]:
    """Insere uma mensagem inbound. Retorna (id, inserida). Se
    meta_message_id já existir, não duplica (retorna (id_existente, False))
    -- proteção adicional além da checagem de evento em
    whatsapp_webhook_events, para o caso de duas mensagens do mesmo evento
    compartilharem id por payload malformado."""
    if meta_message_id:
        existente = conn.execute(
            "SELECT id FROM whatsapp_messages WHERE meta_message_id=?", (meta_message_id,)
        ).fetchone()
        if existente:
            return int(existente["id"]), False

    agora = _agora()
    cur = conn.execute(
        """
        INSERT INTO whatsapp_messages
            (conversation_id, meta_message_id, direction, message_type, text_body,
             media_id, media_mime_type, reply_to_meta_message_id, status,
             timestamp_meta, created_at, updated_at)
        VALUES (?,?, 'inbound', ?, ?, ?, ?, ?, 'received', ?, ?, ?)
        """,
        (
            conversation_id,
            meta_message_id,
            message_type,
            sanitizar_texto(text_body),
            media_id,
            media_mime_type,
            reply_to_meta_message_id,
            timestamp_meta,
            agora,
            agora,
        ),
    )
    return cur.lastrowid, True


def atualizar_conversa_apos_inbound(conn, *, conversation_id: int, quando: str | None = None) -> None:
    agora = quando or _agora()
    conn.execute(
        """
        UPDATE whatsapp_conversations
           SET last_message_at=?, last_inbound_at=?, unread_count=unread_count+1, updated_at=?,
               status=CASE WHEN status='resolved' OR status='archived' THEN 'open' ELSE status END
         WHERE id=?
        """,
        (agora, agora, agora, conversation_id),
    )


def registrar_mensagem_enviada(
    conn,
    *,
    conversation_id: int,
    message_type: str,
    text_body: str | None,
    template_name: str | None,
    sent_by_admin: str,
    reply_to_meta_message_id: str | None = None,
    status: str = "queued",
) -> int:
    agora = _agora()
    cur = conn.execute(
        """
        INSERT INTO whatsapp_messages
            (conversation_id, direction, message_type, text_body, template_name,
             sent_by_admin, reply_to_meta_message_id, status, created_at, updated_at)
        VALUES (?, 'outbound', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (conversation_id, message_type, sanitizar_texto(text_body), template_name, sent_by_admin, reply_to_meta_message_id, status, agora, agora),
    )
    conn.execute(
        "UPDATE whatsapp_conversations SET last_message_at=?, last_outbound_at=?, updated_at=? WHERE id=?",
        (agora, agora, agora, conversation_id),
    )
    return cur.lastrowid


def atualizar_status_mensagem_enviada(conn, message_id: int, *, meta_message_id: str | None, status: str, error_code: str | None = None, error_message_sanitized: str | None = None) -> None:
    agora = _agora()
    conn.execute(
        """
        UPDATE whatsapp_messages
           SET meta_message_id=COALESCE(?, meta_message_id), status=?, error_code=?,
               error_message_sanitized=?, updated_at=?
         WHERE id=?
        """,
        (meta_message_id, status, error_code, sanitizar_texto(error_message_sanitized, limite=300), agora, message_id),
    )


def registrar_evento_webhook(conn, *, event_key: str, event_type: str, payload_hash: str, expires_at: str | None) -> bool:
    """Reivindica um evento de webhook pelo event_key. Retorna True se este é
    o primeiro processamento (a linha foi inserida agora), False se já
    existia (evento duplicado -- nunca reprocessa)."""
    try:
        conn.execute(
            """
            INSERT INTO whatsapp_webhook_events
                (event_key, event_type, payload_hash, received_at, processing_status, expires_at)
            VALUES (?,?,?,?, 'pending', ?)
            """,
            (event_key, event_type, payload_hash, _agora(), expires_at),
        )
        return True
    except Exception:
        return False


def concluir_evento_webhook(conn, *, event_key: str, status: str, erro_sanitizado: str | None = None) -> None:
    conn.execute(
        "UPDATE whatsapp_webhook_events SET processed_at=?, processing_status=?, last_error_sanitized=? WHERE event_key=?",
        (_agora(), status, sanitizar_texto(erro_sanitizado, limite=300) if erro_sanitizado else None, event_key),
    )


def listar_conversas(conn, *, status: str | None, apenas_nao_lidas: bool, busca: str | None, pagina: int, tamanho_pagina: int) -> tuple[list[dict], int]:
    condicoes = []
    parametros: list = []
    if status:
        condicoes.append("c.status=?")
        parametros.append(status)
    if apenas_nao_lidas:
        condicoes.append("c.unread_count > 0")
    if busca:
        condicoes.append("(ct.profile_name LIKE ? OR ct.phone_last4 LIKE ?)")
        termo = f"%{busca.strip()[:60]}%"
        parametros.extend([termo, termo])
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    total_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM whatsapp_conversations c JOIN whatsapp_contacts ct ON ct.id=c.contact_id {where}",
        parametros,
    ).fetchone()
    total = int(total_row["n"] if total_row else 0)

    offset = max(0, (pagina - 1) * tamanho_pagina)
    linhas = conn.execute(
        f"""
        SELECT c.*, ct.profile_name, ct.phone_last4, ct.customer_id AS contato_customer_id
          FROM whatsapp_conversations c
          JOIN whatsapp_contacts ct ON ct.id = c.contact_id
          {where}
         ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
         LIMIT ? OFFSET ?
        """,
        [*parametros, tamanho_pagina, offset],
    ).fetchall()
    return [dict(row) for row in linhas], total


def obter_conversa(conn, conversation_id: int) -> dict | None:
    linha = conn.execute(
        """
        SELECT c.*, ct.profile_name, ct.phone_last4, ct.phone_e164, ct.wa_id, ct.customer_id AS contato_customer_id
          FROM whatsapp_conversations c
          JOIN whatsapp_contacts ct ON ct.id = c.contact_id
         WHERE c.id=?
        """,
        (conversation_id,),
    ).fetchone()
    return dict(linha) if linha else None


def listar_mensagens(conn, conversation_id: int, *, antes_de_id: int | None, limite: int) -> list[dict]:
    if antes_de_id:
        linhas = conn.execute(
            "SELECT * FROM whatsapp_messages WHERE conversation_id=? AND id < ? ORDER BY id DESC LIMIT ?",
            (conversation_id, antes_de_id, limite),
        ).fetchall()
    else:
        linhas = conn.execute(
            "SELECT * FROM whatsapp_messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limite),
        ).fetchall()
    return list(reversed([dict(row) for row in linhas]))


def marcar_conversa_lida(conn, conversation_id: int) -> None:
    conn.execute(
        "UPDATE whatsapp_conversations SET unread_count=0, updated_at=? WHERE id=?",
        (_agora(), conversation_id),
    )


def atualizar_conversa(conn, conversation_id: int, *, status: str | None = None, assigned_admin: str | None = None) -> None:
    campos = []
    parametros: list = []
    if status is not None:
        if status not in STATUS_CONVERSA_VALIDOS:
            raise ValueError(f"Status de conversa inválido: {status!r}")
        campos.append("status=?")
        parametros.append(status)
    if assigned_admin is not None:
        campos.append("assigned_admin=?")
        parametros.append(assigned_admin)
    if not campos:
        return
    campos.append("updated_at=?")
    parametros.append(_agora())
    parametros.append(conversation_id)
    conn.execute(f"UPDATE whatsapp_conversations SET {', '.join(campos)} WHERE id=?", parametros)


def vincular_cliente(conn, conversation_id: int, customer_id: int) -> None:
    agora = _agora()
    conn.execute("UPDATE whatsapp_conversations SET customer_id=?, updated_at=? WHERE id=?", (customer_id, agora, conversation_id))
    conversa = conn.execute("SELECT contact_id FROM whatsapp_conversations WHERE id=?", (conversation_id,)).fetchone()
    if conversa:
        conn.execute("UPDATE whatsapp_contacts SET customer_id=?, updated_at=? WHERE id=?", (customer_id, agora, conversa["contact_id"]))


def vincular_pedido(conn, conversation_id: int, order_id: int) -> None:
    conn.execute("UPDATE whatsapp_conversations SET order_id=?, updated_at=? WHERE id=?", (order_id, _agora(), conversation_id))


def linha_mensagem_publica(row: dict) -> dict:
    """Serialização segura para o painel -- nunca inclui media_path (caminho
    de disco interno); mídia é servida só pelo endpoint autenticado
    /api/admin/whatsapp/media/{message_id}."""
    campos = (
        "id", "conversation_id", "meta_message_id", "direction", "message_type",
        "text_body", "media_id", "media_mime_type", "media_size",
        "reply_to_meta_message_id", "template_name", "status", "error_code",
        "error_message_sanitized", "sent_by_admin", "timestamp_meta", "created_at", "updated_at",
    )
    return {campo: row.get(campo) for campo in campos}


def linha_conversa_publica(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "assigned_admin": row.get("assigned_admin"),
        "unread_count": row.get("unread_count"),
        "last_message_at": row.get("last_message_at"),
        "last_inbound_at": row.get("last_inbound_at"),
        "last_outbound_at": row.get("last_outbound_at"),
        "customer_id": row.get("customer_id") or row.get("contato_customer_id"),
        "order_id": row.get("order_id"),
        "created_at": row.get("created_at"),
        "contact": {
            "profile_name": row.get("profile_name"),
            "phone_last4": row.get("phone_last4"),
        },
    }
