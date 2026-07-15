from pathlib import Path
import asyncio
import json
import os

from fastapi import Depends, FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db
from api.audit import registrar_acesso_api
from api.security import (
    APP_SESSION_COOKIE,
    origem_websocket_permitida,
    validar_origem_csrf,
    validar_token,
    validar_token_valor,
)
from api.app_auth import DURACAO_SESSAO_HORAS, login_app, logout_app, validar_sessao_app
from api.service import (
    alertas_isis_api,
    app_android_info,
    caixa_status,
    cancelamentos_recentes,
    contas_alerta_api,
    dashboard_api,
    dashboard_app,
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


class LoginAppRequest(BaseModel):
    login: str
    senha: str


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"


def _allowed_origins() -> list[str]:
    padrao = "" if IS_PRODUCTION else "http://localhost,http://127.0.0.1"
    configurado = os.getenv("MISTICA_ALLOWED_ORIGINS", padrao).strip()
    if not configurado:
        return []
    return [origem.strip() for origem in configurado.split(",") if origem.strip()]


app = FastAPI(
    title="Mística Presentes API Local",
    version="0.1.0",
    description="API local somente leitura para rede da loja e painel mobile em tempo real.",
    # Mesmo em rede local, o schema completo (rotas, formatos, exemplos) não deve
    # ficar acessível sem o token da API; as rotas nativas de docs são
    # desativadas e recriadas abaixo exigindo o mesmo header X-Mistica-Token.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_OPENAPI_URL = "/openapi.json"


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(validar_token)])
def openapi_protegido():
    return app.openapi()


@app.get("/docs", include_in_schema=False, dependencies=[Depends(validar_token)])
def swagger_docs_protegido():
    return get_swagger_ui_html(openapi_url=_OPENAPI_URL, title=f"{app.title} - Swagger UI")


@app.get("/redoc", include_in_schema=False, dependencies=[Depends(validar_token)])
def redoc_protegido():
    return get_redoc_html(openapi_url=_OPENAPI_URL, title=f"{app.title} - ReDoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Mistica-Token"],
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


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"ok": True, "servico": "Mística Presentes API Local"}


@app.get("/api/server/status")
def api_server_status():
    return server_status_api()


@app.get("/api/app/android", dependencies=[Depends(validar_token)])
def api_app_android():
    return app_android_info()


@app.post("/api/app/login", dependencies=[Depends(validar_token)])
def api_app_login(payload: LoginAppRequest, request: Request):
    validar_origem_csrf(request)
    resultado = login_app(payload.login, payload.senha)
    if not resultado.get("ok"):
        return JSONResponse(
            status_code=401,
            content={"detail": resultado.get("erro", "Usuário ou senha incorretos.")},
            headers=NO_CACHE_HEADERS,
        )
    sessao = resultado.pop("sessao")
    response = JSONResponse(content=resultado, headers=NO_CACHE_HEADERS)
    response.set_cookie(
        key=APP_SESSION_COOKIE,
        value=sessao,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        max_age=DURACAO_SESSAO_HORAS * 3600,
        path="/",
    )
    return response


@app.post("/api/app/logout")
def api_app_logout(request: Request, response: Response):
    validar_origem_csrf(request)
    sessao_cookie = request.cookies.get(APP_SESSION_COOKIE)
    resultado = logout_app(sessao_cookie)
    response.delete_cookie(APP_SESSION_COOKIE, path="/")
    response.headers.update(NO_CACHE_HEADERS)
    return resultado


@app.get("/api/app/painel")
def api_app_painel(request: Request):
    sessao = validar_sessao_app(request.cookies.get(APP_SESSION_COOKIE))
    if not sessao:
        return JSONResponse(
            status_code=401,
            content={"detail": "Faça login novamente no app."},
            headers=NO_CACHE_HEADERS,
        )
    return JSONResponse(content=dashboard_app(sessao), headers=NO_CACHE_HEADERS)


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
    cookie_sessao = websocket.cookies.get(APP_SESSION_COOKIE)
    sessao_app = validar_sessao_app(cookie_sessao) if cookie_sessao else None
    if cookie_sessao and sessao_app and not origem_websocket_permitida(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        registrar_acesso_api("WS", "/ws/dashboard", "403", websocket.client.host if websocket.client else "-")
        return
    if not validar_token_valor(token) and not sessao_app:
        await websocket.close(code=1008)
        registrar_acesso_api("WS", "/ws/dashboard", "401", websocket.client.host if websocket.client else "-")
        return
    await websocket.accept()
    registrar_acesso_api("WS", "/ws/dashboard", "101", websocket.client.host if websocket.client else "-")
    try:
        while True:
            if cookie_sessao:
                sessao_app = validar_sessao_app(cookie_sessao)
                if not sessao_app:
                    await websocket.close(code=1008)
                    return
                payload = dashboard_app(sessao_app)
            else:
                payload = dashboard_api()
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
