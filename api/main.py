from pathlib import Path
import asyncio
import json

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from api.security import validar_token
from api.service import (
    alertas_isis_api,
    caixa_status,
    cancelamentos_recentes,
    contas_alerta_api,
    dashboard_api,
    estoque_baixo_api,
    ultimas_vendas,
    vendas_do_dia,
)

BASE_DIR = Path(__file__).resolve().parent
PAINEL_HTML = BASE_DIR / "painel.html"

app = FastAPI(
    title="Mística Presentes API Local",
    version="0.1.0",
    description="API local somente leitura para rede da loja e painel mobile em tempo real.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def painel():
    if PAINEL_HTML.exists():
        return PAINEL_HTML.read_text(encoding="utf-8")
    return "<h1>Mística Presentes API</h1><p>Painel não encontrado.</p>"


@app.get("/health")
def health():
    return {"ok": True, "servico": "Mística Presentes API Local"}


@app.get("/api/dashboard", dependencies=[Depends(validar_token)])
def api_dashboard():
    return dashboard_api()


@app.get("/api/vendas/hoje", dependencies=[Depends(validar_token)])
def api_vendas_hoje():
    return vendas_do_dia()


@app.get("/api/vendas/recentes", dependencies=[Depends(validar_token)])
def api_vendas_recentes(limite: int = 10):
    return ultimas_vendas(limite)


@app.get("/api/vendas/cancelamentos", dependencies=[Depends(validar_token)])
def api_cancelamentos(limite: int = 10):
    return cancelamentos_recentes(limite)


@app.get("/api/caixa/status", dependencies=[Depends(validar_token)])
def api_caixa_status():
    return caixa_status()


@app.get("/api/estoque/baixo", dependencies=[Depends(validar_token)])
def api_estoque_baixo(limite: int = 10):
    return estoque_baixo_api(limite)


@app.get("/api/contas/alertas", dependencies=[Depends(validar_token)])
def api_contas_alertas():
    return contas_alerta_api()


@app.get("/api/alertas/isis", dependencies=[Depends(validar_token)])
def api_alertas_isis():
    return alertas_isis_api()


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps(dashboard_api(), ensure_ascii=False))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
