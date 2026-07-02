from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import asyncio
import json

from cloud_server.security import comparar_token, exigir_admin, extrair_token_loja, hash_token
from cloud_server.storage import (
    get_loja,
    historico_snapshots,
    init_cloud_db,
    salvar_snapshot,
    ultimo_snapshot,
    upsert_loja,
)

app = FastAPI(
    title="Mística Presentes Cloud Server",
    version="0.1.0",
    description="Servidor dedicado para acompanhar a loja pela internet.",
)


class LojaCreate(BaseModel):
    loja_id: str = Field(min_length=3, max_length=60)
    nome: str = Field(min_length=2, max_length=120)
    token: str = Field(min_length=12, max_length=200)


class SnapshotIn(BaseModel):
    loja_id: str
    payload: dict
    origem: str = "sincronizador-local"


@app.on_event("startup")
def startup():
    init_cloud_db()


@app.get("/health")
def health():
    return {"ok": True, "servico": "Mística Presentes Cloud Server"}


@app.post("/admin/lojas", dependencies=[Depends(exigir_admin)])
def criar_ou_atualizar_loja(dados: LojaCreate):
    upsert_loja(dados.loja_id, dados.nome, hash_token(dados.token))
    return {"ok": True, "loja_id": dados.loja_id, "nome": dados.nome}


def validar_loja_token(loja_id: str, token: str):
    loja = get_loja(loja_id)
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não cadastrada no servidor cloud.")
    if not comparar_token(token, loja["token_hash"]):
        raise HTTPException(status_code=401, detail="Token da loja inválido.")
    return loja


@app.post("/api/sync/snapshot")
def receber_snapshot(dados: SnapshotIn, token: str = Depends(extrair_token_loja)):
    validar_loja_token(dados.loja_id, token)
    salvar_snapshot(dados.loja_id, dados.payload, dados.origem)
    return {"ok": True, "loja_id": dados.loja_id}


@app.get("/api/lojas/{loja_id}/dashboard")
def dashboard_cloud(loja_id: str, token: str = Depends(extrair_token_loja)):
    validar_loja_token(loja_id, token)
    snapshot = ultimo_snapshot(loja_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Ainda não há dados sincronizados desta loja.")
    return snapshot


@app.get("/api/lojas/{loja_id}/historico")
def historico_cloud(loja_id: str, limite: int = 20, token: str = Depends(extrair_token_loja)):
    validar_loja_token(loja_id, token)
    return {"loja_id": loja_id, "historico": historico_snapshots(loja_id, limite)}


@app.websocket("/ws/lojas/{loja_id}/dashboard")
async def ws_dashboard_cloud(websocket: WebSocket, loja_id: str):
    await websocket.accept()
    token = websocket.query_params.get("token", "")
    try:
        validar_loja_token(loja_id, token)
        while True:
            snapshot = ultimo_snapshot(loja_id)
            await websocket.send_text(json.dumps(snapshot or {"aguardando": True}, ensure_ascii=False))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
    except Exception as e:
        await websocket.send_text(json.dumps({"erro": str(e)}, ensure_ascii=False))
        await websocket.close()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><head><title>Mística Cloud</title><meta name='viewport' content='width=device-width,initial-scale=1'></head>
    <body style='font-family:Arial;background:#121018;color:#f6f0df;padding:24px'>
      <h1 style='color:#d8b56d'>🌙 Mística Presentes Cloud Server</h1>
      <p>Servidor dedicado ativo.</p>
      <p>Use o app Android ou a API com token da loja.</p>
    </body></html>
    """
