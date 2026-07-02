from pathlib import Path
import asyncio
import json

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from api.audit import registrar_acesso_api
from api.security import validar_token, validar_token_valor
from api.service import (
    alertas_isis_api,
    app_android_info,
    caixa_status,
    cancelamentos_recentes,
    contas_alerta_api,
    dashboard_api,
    estoque_baixo_api,
    server_status_api,
    ultimas_vendas,
    vendas_do_dia,
)

BASE_DIR = Path(__file__).resolve().parent
PAINEL_HTML = BASE_DIR / "painel.html"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

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


@app.middleware("http")
async def logar_acesso_http(request: Request, call_next):
    response = await call_next(request)
    cliente = request.client.host if request.client else "-"
    registrar_acesso_api(request.method, request.url.path, response.status_code, cliente)
    return response


@app.on_event("startup")
def startup():
    init_db()


def resposta_painel():
    if PAINEL_HTML.exists():
        html = PAINEL_HTML.read_text(encoding="utf-8")
    else:
        html = "<h1>Mística Presentes API</h1><p>Painel não encontrado.</p>"
    return HTMLResponse(html, headers=NO_CACHE_HEADERS)


@app.get("/", response_class=HTMLResponse)
def painel():
    return resposta_painel()


@app.get("/app", response_class=HTMLResponse)
def app_online():
    return resposta_painel()


@app.get("/mobile", response_class=HTMLResponse)
def mobile_online():
    return resposta_painel()


@app.get("/status", response_class=HTMLResponse)
def status_visual():
    status_api = server_status_api()
    seguranca = status_api["seguranca"]
    cor = "#6fbf9b" if seguranca["token_forte_configurado"] else "#e07070"
    texto = "Token forte configurado" if seguranca["token_forte_configurado"] else "ATENÇÃO: token padrão/fraco em uso"
    html = f"""
    <html><head><title>Status Mística</title><meta name='viewport' content='width=device-width,initial-scale=1'></head>
    <body style='font-family:Arial;background:#121018;color:#f6f0df;padding:24px'>
      <h1 style='color:#d8b56d'>🌙 Status do Servidor Mística</h1>
      <p>Serviço: {status_api['servico']}</p>
      <p>Gerado em: {status_api['gerado_em']}</p>
      <p style='color:{cor};font-weight:bold'>{texto}</p>
      <p>Para uso externo com Cloudflare, defina MISTICA_API_TOKEN com um token forte.</p>
    </body></html>
    """
    return HTMLResponse(html, headers=NO_CACHE_HEADERS)


@app.get("/health")
def health():
    return {"ok": True, "servico": "Mística Presentes API Local"}


@app.get("/api/server/status")
def api_server_status():
    return server_status_api()


@app.get("/api/app/android", dependencies=[Depends(validar_token)])
def api_app_android():
    return app_android_info()


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
    token = websocket.query_params.get("token", "")
    if not validar_token_valor(token):
        await websocket.close(code=1008)
        registrar_acesso_api("WS", "/ws/dashboard", "401", websocket.client.host if websocket.client else "-")
        return
    await websocket.accept()
    registrar_acesso_api("WS", "/ws/dashboard", "101", websocket.client.host if websocket.client else "-")
    try:
        while True:
            await websocket.send_text(json.dumps(dashboard_api(), ensure_ascii=False))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
