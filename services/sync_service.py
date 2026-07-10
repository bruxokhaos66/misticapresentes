import json
import os
from datetime import datetime

import httpx

from config import API_URL
from database.connection import query_db


SYNC_TIMEOUT = 6
STATUS_TIMEOUT = 2


def garantir_tabela_sync():
    query_db(
        """
        CREATE TABLE IF NOT EXISTS sync_pendencias (
            id INTEGER PRIMARY KEY,
            tipo TEXT NOT NULL,
            referencia_id INTEGER,
            payload TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente',
            tentativas INTEGER DEFAULT 0,
            ultimo_erro TEXT,
            data_criacao TEXT,
            data_atualizacao TEXT,
            sincronizado_em TEXT
        )
        """,
        commit=True,
    )
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_pendencias(status)",
        "CREATE INDEX IF NOT EXISTS idx_sync_tipo_ref ON sync_pendencias(tipo, referencia_id)",
    ]:
        try:
            query_db(sql, commit=True)
        except Exception:
            pass


def montar_payload_venda(venda_id):
    venda = query_db(
        """
        SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
               forma_pagamento, vendedor, status, data_iso, dia_operacional
        FROM vendas
        WHERE id=?
        """,
        (venda_id,),
    )
    if not venda:
        raise ValueError(f"Venda {venda_id} nao encontrada para sincronizacao.")

    v = venda[0]
    itens = query_db(
        """
        SELECT codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total
        FROM vendas_itens
        WHERE venda_id=?
        ORDER BY id
        """,
        (venda_id,),
    )
    return {
        "local_id": v[0],
        "cliente": v[1],
        "data_venda": v[2],
        "subtotal": float(v[3] or 0),
        "desconto": float(v[4] or 0),
        "taxa": float(v[5] or 0),
        "total_final": float(v[6] or 0),
        "forma_pagamento": v[7],
        "vendedor": v[8],
        "status": v[9] or "Concluído",
        "data_iso": v[10],
        "dia_operacional": v[11],
        "itens": [
            {
                "codigo_p": item[0],
                "nome_p": item[1],
                "quantidade": int(item[2] or 0),
                "custo_unitario": float(item[3] or 0),
                "valor_unitario": float(item[4] or 0),
                "valor_total": float(item[5] or 0),
            }
            for item in itens
        ],
    }


def enfileirar_venda_para_sync(venda_id):
    garantir_tabela_sync()
    payload = montar_payload_venda(venda_id)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existente = query_db(
        "SELECT id FROM sync_pendencias WHERE tipo='venda' AND referencia_id=? AND status!='Sincronizado'",
        (venda_id,),
    )
    payload_json = json.dumps(payload, ensure_ascii=False)
    if existente:
        query_db(
            """
            UPDATE sync_pendencias
               SET payload=?, status='Pendente', data_atualizacao=?
             WHERE id=?
            """,
            (payload_json, agora, existente[0][0]),
            commit=True,
        )
        return existente[0][0]
    query_db(
        """
        INSERT INTO sync_pendencias
        (tipo, referencia_id, payload, status, tentativas, data_criacao, data_atualizacao)
        VALUES ('venda', ?, ?, 'Pendente', 0, ?, ?)
        """,
        (venda_id, payload_json, agora, agora),
        commit=True,
    )
    novo = query_db(
        "SELECT id FROM sync_pendencias WHERE tipo='venda' AND referencia_id=? ORDER BY id DESC LIMIT 1",
        (venda_id,),
    )
    return novo[0][0] if novo else None


def _enviar_pendencia(pendencia_id, tipo, payload_json):
    endpoint = f"{API_URL.rstrip('/')}/api/sync/{tipo}"
    payload = json.loads(payload_json)
    headers = {}
    chave = os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if chave:
        headers["x-mistica-sync-key"] = chave
    with httpx.Client(timeout=SYNC_TIMEOUT) as client:
        resp = client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _buscar_pendencias(limite=20, referencia_id_prioritaria=None):
    garantir_tabela_sync()
    if referencia_id_prioritaria is not None:
        return query_db(
            """
            SELECT id, tipo, payload
            FROM sync_pendencias
            WHERE status IN ('Pendente', 'Erro')
            ORDER BY
                CASE WHEN tipo='venda' AND referencia_id=? THEN 0 ELSE 1 END,
                id DESC
            LIMIT ?
            """,
            (int(referencia_id_prioritaria), int(limite)),
        )
    return query_db(
        """
        SELECT id, tipo, payload
        FROM sync_pendencias
        WHERE status IN ('Pendente', 'Erro')
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limite),),
    )


def sincronizar_pendencias(limite=20, referencia_id_prioritaria=None):
    pendencias = _buscar_pendencias(limite=limite, referencia_id_prioritaria=referencia_id_prioritaria)
    resultado = {"sincronizados": 0, "erros": 0, "detalhes": []}
    for pendencia_id, tipo, payload_json in pendencias:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            retorno = _enviar_pendencia(pendencia_id, tipo, payload_json)
            query_db(
                """
                UPDATE sync_pendencias
                   SET status='Sincronizado', ultimo_erro=NULL, data_atualizacao=?, sincronizado_em=?
                 WHERE id=?
                """,
                (agora, agora, pendencia_id),
                commit=True,
            )
            resultado["sincronizados"] += 1
            resultado["detalhes"].append({"id": pendencia_id, "ok": True, "retorno": retorno})
        except Exception as exc:
            erro = str(exc)[:500]
            query_db(
                """
                UPDATE sync_pendencias
                   SET status='Erro', tentativas=COALESCE(tentativas,0)+1,
                       ultimo_erro=?, data_atualizacao=?
                 WHERE id=?
                """,
                (erro, agora, pendencia_id),
                commit=True,
            )
            resultado["erros"] += 1
            resultado["detalhes"].append({"id": pendencia_id, "ok": False, "erro": erro})
    return resultado


def sincronizar_venda_agora(venda_id):
    """Enfileira e tenta sincronizar a venda recem-salva antes de pendencias antigas."""
    enfileirar_venda_para_sync(venda_id)
    return sincronizar_pendencias(limite=6, referencia_id_prioritaria=venda_id)


def sincronizar_venda_obrigatoria(venda_id):
    """Envia a venda para o servidor central de forma síncrona e devolve o
    resultado só dessa venda (não de outras pendências antigas que porventura
    sejam processadas na mesma leva). Usada por registrar_venda_service para
    decidir se a venda pode ser considerada concluída."""
    pendencia_id = enfileirar_venda_para_sync(venda_id)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        payload = query_db("SELECT payload FROM sync_pendencias WHERE id=?", (pendencia_id,))
        payload_json = payload[0][0] if payload else None
        if not payload_json:
            return False, "Pendência de sincronização não encontrada."
        retorno = _enviar_pendencia(pendencia_id, "venda", payload_json)
        query_db(
            """
            UPDATE sync_pendencias
               SET status='Sincronizado', ultimo_erro=NULL, data_atualizacao=?, sincronizado_em=?
             WHERE id=?
            """,
            (agora, agora, pendencia_id),
            commit=True,
        )
        return True, retorno
    except Exception as exc:
        erro = str(exc)[:500]
        query_db(
            """
            UPDATE sync_pendencias
               SET status='Erro', tentativas=COALESCE(tentativas,0)+1,
                   ultimo_erro=?, data_atualizacao=?
             WHERE id=?
            """,
            (erro, agora, pendencia_id),
            commit=True,
        )
        return False, erro


def enfileirar_e_tentar_sincronizar_venda(venda_id):
    try:
        return sincronizar_venda_agora(venda_id)
    except Exception as exc:
        return {"sincronizados": 0, "erros": 1, "detalhes": [{"erro": str(exc)}]}


def resumo_sync():
    garantir_tabela_sync()
    rows = query_db(
        """
        SELECT status, COUNT(*)
        FROM sync_pendencias
        GROUP BY status
        """
    )
    return {status or "Pendente": total for status, total in rows}


def ultima_sincronizacao():
    garantir_tabela_sync()
    row = query_db(
        """
        SELECT MAX(sincronizado_em)
        FROM sync_pendencias
        WHERE status='Sincronizado'
        """
    )
    return row[0][0] if row and row[0] else "Nunca"


def api_online():
    try:
        with httpx.Client(timeout=STATUS_TIMEOUT) as client:
            resp = client.get(f"{API_URL.rstrip('/')}/api/health")
            return resp.status_code == 200
    except Exception:
        return False


def estado_sincronizacao(tentar_enviar=True):
    garantir_tabela_sync()
    if tentar_enviar:
        try:
            sincronizar_pendencias(limite=10)
        except Exception:
            pass
    resumo = resumo_sync()
    pendencias = int(resumo.get("Pendente", 0) or 0) + int(resumo.get("Erro", 0) or 0)
    online = api_online()
    return {
        "online": online,
        "status": "Online" if online else "Offline",
        "pendencias": pendencias,
        "ultima_sincronizacao": ultima_sincronizacao(),
        "api_url": API_URL,
    }
