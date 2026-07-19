from __future__ import annotations

from datetime import datetime

from fastapi import Body, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api

FORMAS_RECEBIMENTO = {"retirada", "entrega"}


class LogisticaPedidoIn(BaseModel):
    forma_recebimento: str = Field(min_length=1, max_length=20)
    endereco_entrega: str | None = Field(default=None, max_length=500)
    transportadora: str | None = Field(default=None, max_length=120)
    codigo_rastreio: str | None = Field(default=None, max_length=120)
    prazo_entrega: str | None = Field(default=None, max_length=80)
    observacao_logistica: str | None = Field(default=None, max_length=500)


def _texto_seguro(valor, limite: int) -> str | None:
    texto = str(valor or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite] or None


def garantir_schema_logistica() -> None:
    """Aplica o schema aditivo uma vez durante o bootstrap da API.

    As rotas não executam DDL durante requisições, evitando contenção de lock e
    mantendo leitura/atualização logística separadas da preparação do banco.
    """
    with conectar() as conn:
        colunas = {
            row["name"] for row in conn.execute("PRAGMA table_info(pedidos)").fetchall()
        }
        desejadas = {
            "forma_recebimento": "TEXT",
            "endereco_entrega": "TEXT",
            "transportadora": "TEXT",
            "codigo_rastreio": "TEXT",
            "prazo_entrega": "TEXT",
            "observacao_logistica": "TEXT",
            "logistica_atualizada_em": "TEXT",
            "logistica_atualizada_por": "TEXT",
        }
        for nome, tipo in desejadas.items():
            if nome not in colunas:
                conn.execute(f"ALTER TABLE pedidos ADD COLUMN {nome} {tipo}")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pedido_logistica_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                forma_recebimento TEXT NOT NULL,
                endereco_entrega TEXT,
                transportadora TEXT,
                codigo_rastreio TEXT,
                prazo_entrega TEXT,
                observacao TEXT,
                usuario TEXT NOT NULL,
                data_hora TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pedido_logistica_log_pedido "
            "ON pedido_logistica_log(pedido_id, id DESC)"
        )
        conn.commit()


def registrar_rotas_admin_logistica() -> None:
    from backend.pedido_notificacao_routes import router

    @router.get("/pedidos/{venda_id}/logistica")
    def consultar_logistica(
        venda_id: int,
        sessao: dict = Depends(exigir_sessao_ou_chave_api("vendedor")),
    ):
        del sessao
        with conectar() as conn:
            pedido = conn.execute(
                """
                SELECT id, status, status_pedido, forma_recebimento,
                       endereco_entrega, transportadora, codigo_rastreio,
                       prazo_entrega, observacao_logistica,
                       logistica_atualizada_em, logistica_atualizada_por
                  FROM pedidos
                 WHERE id=?
                """,
                (venda_id,),
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            historico = conn.execute(
                """
                SELECT id, forma_recebimento, endereco_entrega, transportadora,
                       codigo_rastreio, prazo_entrega, observacao, usuario, data_hora
                  FROM pedido_logistica_log
                 WHERE pedido_id=?
                 ORDER BY id DESC
                 LIMIT 100
                """,
                (venda_id,),
            ).fetchall()
            resposta = dict(pedido)
            resposta["historico_logistica"] = [dict(item) for item in historico]
            return resposta

    @router.patch("/pedidos/{venda_id}/logistica")
    def atualizar_logistica(
        venda_id: int,
        payload: LogisticaPedidoIn = Body(...),
        sessao: dict = Depends(exigir_sessao_ou_chave_api("adm")),
    ):
        forma = (_texto_seguro(payload.forma_recebimento, 20) or "").lower()
        if forma not in FORMAS_RECEBIMENTO:
            raise HTTPException(status_code=400, detail="Forma de recebimento inválida.")

        endereco = _texto_seguro(payload.endereco_entrega, 500)
        transportadora = _texto_seguro(payload.transportadora, 120)
        rastreio = _texto_seguro(payload.codigo_rastreio, 120)
        prazo = _texto_seguro(payload.prazo_entrega, 80)
        observacao = _texto_seguro(payload.observacao_logistica, 500)

        if forma == "entrega" and not endereco:
            raise HTTPException(status_code=400, detail="Informe o endereço para pedidos com entrega.")
        if forma == "retirada" and (transportadora or rastreio):
            raise HTTPException(
                status_code=400,
                detail="Transportadora e rastreio não se aplicam a pedidos para retirada.",
            )

        usuario = _texto_seguro(sessao.get("nome") or sessao.get("login") or "Admin", 120) or "Admin"
        agora = datetime.now().isoformat(timespec="seconds")

        with conectar() as conn:
            pedido = conn.execute(
                """
                SELECT id, status, status_pedido, forma_recebimento,
                       endereco_entrega, transportadora, codigo_rastreio,
                       prazo_entrega, observacao_logistica
                  FROM pedidos
                 WHERE id=?
                """,
                (venda_id,),
            ).fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            if str(pedido["status_pedido"] or "").lower() == "cancelado":
                raise HTTPException(status_code=409, detail="Pedido cancelado não pode ter a logística alterada.")

            antes = dict(pedido)
            conn.execute(
                """
                UPDATE pedidos
                   SET forma_recebimento=?, endereco_entrega=?, transportadora=?,
                       codigo_rastreio=?, prazo_entrega=?, observacao_logistica=?,
                       logistica_atualizada_em=?, logistica_atualizada_por=?
                 WHERE id=?
                """,
                (forma, endereco, transportadora, rastreio, prazo, observacao, agora, usuario, venda_id),
            )
            conn.execute(
                """
                INSERT INTO pedido_logistica_log
                    (pedido_id, forma_recebimento, endereco_entrega, transportadora,
                     codigo_rastreio, prazo_entrega, observacao, usuario, data_hora)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (venda_id, forma, endereco, transportadora, rastreio, prazo, observacao, usuario, agora),
            )
            registrar_auditoria(
                conn,
                "pedido",
                venda_id,
                "atualizar_logistica",
                usuario,
                antes=antes,
                depois={
                    "status_financeiro": pedido["status"],
                    "status_pedido": pedido["status_pedido"],
                    "forma_recebimento": forma,
                    "endereco_entrega": endereco,
                    "transportadora": transportadora,
                    "codigo_rastreio": rastreio,
                    "prazo_entrega": prazo,
                    "observacao_logistica": observacao,
                },
            )
            conn.commit()

        return {
            "ok": True,
            "venda_id": venda_id,
            "forma_recebimento": forma,
            "logistica_atualizada_em": agora,
        }
