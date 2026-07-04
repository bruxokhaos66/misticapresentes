from __future__ import annotations

from datetime import datetime, timedelta
import json
import threading
import time
from typing import Any

import httpx

from config import API_URL
from database import query_db
from services.usuario_sync_service import sincronizar_usuarios_com_api
from tools.sincronizar_painel_online import main as sincronizar_painel_online_main


API_TIMEOUT = httpx.Timeout(connect=4, read=8, write=8, pool=4)


def _api_url() -> str:
    return (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")


def _local_qtd_vendas_35_dias() -> int:
    corte = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
    row = query_db(
        """
        SELECT COUNT(*)
        FROM vendas
        WHERE COALESCE(status,'Concluído') NOT IN ('Cancelado','Cancelada')
          AND (
                datetime(COALESCE(data_iso,'')) >= datetime(?)
                OR COALESCE(data_iso,'') = ''
              )
        """,
        (corte,),
    )
    return int(row[0][0] if row and row[0] else 0)


def _local_qtd_produtos() -> int:
    row = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1")
    return int(row[0][0] if row and row[0] else 0)


def _status_api() -> dict[str, Any]:
    with httpx.Client(timeout=API_TIMEOUT) as client:
        status = client.get(f"{_api_url()}/api/status").json()
        resumo = client.get(f"{_api_url()}/api/painel/resumo").json()
    return {
        "status": status,
        "resumo": resumo,
        "api_produtos": int(status.get("produtos") or resumo.get("produtos") or 0),
        "api_vendas": int(status.get("vendas") or resumo.get("vendas") or 0),
    }


def diagnosticar_api_painel() -> dict[str, Any]:
    local_produtos = _local_qtd_produtos()
    local_vendas = _local_qtd_vendas_35_dias()
    try:
        remoto = _status_api()
        api_produtos = remoto["api_produtos"]
        api_vendas = remoto["api_vendas"]
        api_ok = True
        erro = ""
    except Exception as exc:
        api_produtos = 0
        api_vendas = 0
        api_ok = False
        erro = f"{type(exc).__name__}: {exc}"

    produtos_zerados = local_produtos > 0 and api_produtos == 0
    vendas_muito_abaixo = local_vendas >= 3 and api_vendas < max(1, int(local_vendas * 0.5))
    precisa_sync = (not api_ok) or produtos_zerados or vendas_muito_abaixo

    return {
        "api_ok": api_ok,
        "precisa_sync": bool(precisa_sync),
        "local_produtos": local_produtos,
        "local_vendas_35_dias": local_vendas,
        "api_produtos": api_produtos,
        "api_vendas": api_vendas,
        "motivo": "api_indisponivel" if not api_ok else "api_incompleta" if precisa_sync else "ok",
        "erro": erro,
    }


def sincronizar_painel_completo() -> dict[str, Any]:
    inicio = time.time()
    usuarios = {}
    try:
        usuarios = sincronizar_usuarios_com_api(timeout=15)
    except Exception as exc:
        usuarios = {"status": "erro", "erro": f"{type(exc).__name__}: {exc}"}
    try:
        sincronizar_painel_online_main()
        depois = diagnosticar_api_painel()
        return {
            "status": "ok" if not depois.get("precisa_sync") else "parcial",
            "usuarios": usuarios,
            "diagnostico": depois,
            "duracao_seg": round(time.time() - inicio, 2),
        }
    except Exception as exc:
        return {
            "status": "erro",
            "usuarios": usuarios,
            "erro": f"{type(exc).__name__}: {exc}",
            "duracao_seg": round(time.time() - inicio, 2),
        }


_guard_lock = threading.Lock()
_guard_rodando = False
_ultima_execucao = 0.0


def proteger_api_zerada_async(callback=None, intervalo_minimo_seg: int = 60) -> bool:
    global _guard_rodando, _ultima_execucao
    agora = time.time()
    with _guard_lock:
        if _guard_rodando or (agora - _ultima_execucao) < intervalo_minimo_seg:
            return False
        _guard_rodando = True
        _ultima_execucao = agora

    def executar():
        global _guard_rodando
        resultado: dict[str, Any]
        try:
            diag = diagnosticar_api_painel()
            if diag.get("precisa_sync"):
                resultado = sincronizar_painel_completo()
            else:
                resultado = {"status": "ok", "diagnostico": diag, "sincronizacao": "nao_necessaria"}
        except Exception as exc:
            resultado = {"status": "erro", "erro": f"{type(exc).__name__}: {exc}"}
        finally:
            with _guard_lock:
                _guard_rodando = False
        if callback:
            try:
                callback(resultado)
            except Exception:
                pass

    threading.Thread(target=executar, daemon=True).start()
    return True


def resultado_resumido(resultado: dict[str, Any]) -> str:
    try:
        diag = resultado.get("diagnostico") or {}
        return (
            f"API: {resultado.get('status')} | "
            f"produtos local/api {diag.get('local_produtos')}/{diag.get('api_produtos')} | "
            f"vendas local/api {diag.get('local_vendas_35_dias')}/{diag.get('api_vendas')}"
        )
    except Exception:
        return json.dumps(resultado, ensure_ascii=False)[:250]
