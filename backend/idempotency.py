from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from typing import Callable

from fastapi import HTTPException


def resposta_idempotente_existente(conn, escopo: str, chave: str | None):
    """Se a mesma Idempotency-Key já foi usada neste escopo, devolve a resposta
    salva da primeira vez (para a requisição repetida não duplicar o efeito).
    Sem chave, a checagem é ignorada (mantém compatibilidade com clientes que
    ainda não enviam o header)."""
    if not chave:
        return None
    row = conn.execute(
        "SELECT resposta FROM idempotency_keys WHERE escopo=? AND chave=?",
        (escopo, chave),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["resposta"])
    except Exception:
        return None


def salvar_resposta_idempotente(conn, escopo: str, chave: str | None, resposta: dict):
    if not chave:
        return
    conn.execute(
        "INSERT OR IGNORE INTO idempotency_keys (escopo, chave, resposta, criado_em) VALUES (?,?,?,?)",
        (escopo, chave, json.dumps(resposta, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
    )


def calcular_payload_hash(payload: dict) -> str:
    """Hash canônico do payload relevante do pedido (itens, cupom, contato),
    usado para detectar se a mesma Idempotency-Key está sendo reaproveitada
    com um carrinho diferente."""
    canonico = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def reivindicar_chave_idempotente(conectar_fn: Callable, escopo: str, chave: str | None, payload: dict) -> dict | None:
    """Reivindica atomicamente uma Idempotency-Key antes de processar um pedido.

    - Sem chave: devolve None (o chamador processa normalmente, sem idempotência).
    - Chave reivindicada com sucesso (primeira vez que essa chave é usada):
      devolve None (o chamador deve processar o pedido e depois chamar
      concluir_chave_idempotente ou liberar_chave_idempotente em caso de erro).
    - Chave já concluída com o MESMO payload: devolve a resposta salva (a
      requisição não deve reprocessar; deve apenas repetir a resposta).
    - Chave já usada com um payload DIFERENTE: levanta HTTPException 409.
    - Chave sendo processada agora por outra requisição concorrente (mesmo
      payload, corrida de rede/clique duplo): aguarda um pouco e tenta de
      novo, até a outra requisição terminar e devolver a mesma resposta.
    """
    if not chave:
        return None
    hash_atual = calcular_payload_hash(payload)
    agora = datetime.now().isoformat(timespec="seconds")

    for _tentativa in range(40):
        try:
            with conectar_fn() as conn:
                conn.execute(
                    """
                    INSERT INTO idempotency_keys (escopo, chave, resposta, payload_hash, status, criado_em)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (escopo, chave, "{}", hash_atual, "pendente", agora),
                )
            return None
        except sqlite3.IntegrityError:
            with conectar_fn() as conn:
                linha = conn.execute(
                    "SELECT resposta, payload_hash, status FROM idempotency_keys WHERE escopo=? AND chave=?",
                    (escopo, chave),
                ).fetchone()
            if linha is None:
                # A chave foi liberada (erro na outra requisição) entre o INSERT
                # e o SELECT; tenta reivindicar de novo no próximo loop.
                continue
            if linha["payload_hash"] and linha["payload_hash"] != hash_atual:
                raise HTTPException(
                    status_code=409,
                    detail="Esta Idempotency-Key já foi usada para um pedido com dados diferentes.",
                )
            if linha["status"] == "concluido":
                try:
                    return json.loads(linha["resposta"])
                except Exception:
                    return {}
            time.sleep(0.15)

    raise HTTPException(
        status_code=409,
        detail="Este pedido ainda está sendo processado. Aguarde um instante e tente novamente.",
    )


def concluir_chave_idempotente(conn, escopo: str, chave: str | None, resposta: dict):
    """Grava a resposta final na chave já reivindicada (chamar dentro da mesma
    transação que criou o pedido, só depois de tudo confirmado)."""
    if not chave:
        return
    conn.execute(
        "UPDATE idempotency_keys SET resposta=?, status='concluido' WHERE escopo=? AND chave=?",
        (json.dumps(resposta, ensure_ascii=False), escopo, chave),
    )


def liberar_chave_idempotente(conectar_fn: Callable, escopo: str, chave: str | None):
    """Remove a reivindicação pendente quando o processamento falha (erro de
    validação, estoque insuficiente etc.), para que o cliente possa tentar de
    novo com a mesma chave sem ficar preso a uma reivindicação morta."""
    if not chave:
        return
    try:
        with conectar_fn() as conn:
            conn.execute(
                "DELETE FROM idempotency_keys WHERE escopo=? AND chave=? AND status='pendente'",
                (escopo, chave),
            )
    except Exception:
        pass
