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


API_TIMEOUT = httpx.Timeout(connect=4, read=8, write=8, pool=4)
INTERVALO_VERIFICACAO_SEG = 600


def _api_url() -> str:
    return (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")


def _log_auto(evento: str, detalhe: str = "") -> None:
    texto = f"[PainelMobileAuto] {evento} {detalhe}".strip()
    try:
        print(f"{datetime.now().isoformat(timespec='seconds')} {texto}", flush=True)
    except Exception:
        pass
    try:
        query_db(
            """
            INSERT INTO logs (usuario, acao, detalhes, data_hora)
            VALUES (?, ?, ?, ?)
            """,
            ("Sistema", "Painel mobile automatico", texto, datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            commit=True,
        )
    except Exception:
        pass


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


def _local_qtd_usuarios() -> int:
    row = query_db("SELECT COUNT(*) FROM usuarios WHERE COALESCE(ativo,1)=1 AND COALESCE(login,'')!=''")
    return int(row[0][0] if row and row[0] else 0)


def _status_api() -> dict[str, Any]:
    with httpx.Client(timeout=API_TIMEOUT) as client:
        status = client.get(f"{_api_url()}/api/status").json()
        resumo = client.get(f"{_api_url()}/api/painel/resumo").json()
        try:
            usuarios = client.get(f"{_api_url()}/api/usuarios").json()
        except Exception:
            usuarios = []
    return {
        "status": status,
        "resumo": resumo,
        "api_produtos": int(status.get("produtos") or resumo.get("produtos") or 0),
        "api_vendas": int(status.get("vendas") or resumo.get("vendas") or 0),
        "api_usuarios": len(usuarios) if isinstance(usuarios, list) else 0,
    }


def diagnosticar_api_painel() -> dict[str, Any]:
    local_produtos = _local_qtd_produtos()
    local_vendas = _local_qtd_vendas_35_dias()
    local_usuarios = _local_qtd_usuarios()
    try:
        remoto = _status_api()
        api_produtos = remoto["api_produtos"]
        api_vendas = remoto["api_vendas"]
        api_usuarios = remoto["api_usuarios"]
        api_ok = True
        erro = ""
    except Exception as exc:
        api_produtos = 0
        api_vendas = 0
        api_usuarios = 0
        api_ok = False
        erro = f"{type(exc).__name__}: {exc}"

    produtos_zerados = local_produtos > 0 and api_produtos == 0
    vendas_zeradas = local_vendas > 0 and api_vendas == 0
    usuarios_zerados = local_usuarios > 0 and api_usuarios == 0
    produtos_incompletos = local_produtos >= 5 and api_produtos < max(1, int(local_produtos * 0.9))
    vendas_incompletas = local_vendas >= 3 and api_vendas < max(1, int(local_vendas * 0.8))
    api_zerada = produtos_zerados or vendas_zeradas or usuarios_zerados
    api_incompleta = produtos_incompletos or vendas_incompletas
    precisa_sync = api_zerada or api_incompleta
    if not api_ok:
        motivo = "api_indisponivel"
    elif api_zerada:
        motivo = "api_zerada"
    elif api_incompleta:
        motivo = "api_incompleta"
    else:
        motivo = "ok"

    return {
        "api_ok": api_ok,
        "precisa_sync": bool(precisa_sync),
        "precisa_reparo": bool(precisa_sync),
        "local_produtos": local_produtos,
        "local_vendas_35_dias": local_vendas,
        "local_usuarios": local_usuarios,
        "api_produtos": api_produtos,
        "api_vendas": api_vendas,
        "api_usuarios": api_usuarios,
        "motivo": motivo,
        "erro": erro,
    }


def sincronizar_painel_completo() -> dict[str, Any]:
    inicio = time.time()
    _log_auto("reparo_inicio")
    usuarios = {}
    try:
        usuarios = sincronizar_usuarios_com_api(timeout=15)
    except Exception as exc:
        usuarios = {"status": "erro", "erro": f"{type(exc).__name__}: {exc}"}
    try:
        from tools.sincronizar_painel_online import main as sincronizar_painel_online_main
        sincronizar_painel_online_main()
        depois = diagnosticar_api_painel()
        status = "ok" if not depois.get("precisa_sync") else "parcial"
        _log_auto("reparo_fim", f"status={status} motivo={depois.get('motivo')}")
        return {
            "status": status,
            "usuarios": usuarios,
            "diagnostico": depois,
            "duracao_seg": round(time.time() - inicio, 2),
        }
    except Exception as exc:
        _log_auto("reparo_erro", f"{type(exc).__name__}: {exc}")
        return {
            "status": "erro",
            "usuarios": usuarios,
            "erro": f"{type(exc).__name__}: {exc}",
            "duracao_seg": round(time.time() - inicio, 2),
        }


_guard_lock = threading.Lock()
_guard_rodando = False
_ultima_execucao = 0.0


def proteger_api_zerada_async(callback=None, intervalo_minimo_seg: int = INTERVALO_VERIFICACAO_SEG, contexto: str = "automatico") -> bool:
    global _guard_rodando, _ultima_execucao
    agora = time.time()
    with _guard_lock:
        if _guard_rodando:
            _log_auto("verificacao_ignorada", "ja existe verificacao em andamento")
            return False
        if (agora - _ultima_execucao) < intervalo_minimo_seg:
            return False
        _guard_rodando = True
        _ultima_execucao = agora

    def executar():
        global _guard_rodando
        resultado: dict[str, Any]
        try:
            diag = diagnosticar_api_painel()
            _log_auto("verificacao", f"contexto={contexto} motivo={diag.get('motivo')}")
            if diag.get("motivo") in ("api_zerada", "api_incompleta"):
                resultado = {
                    "status": "sincronizando",
                    "diagnostico_inicial": diag,
                    "acao": "reparo_automatico",
                }
                if callback:
                    try:
                        callback(resultado)
                    except Exception:
                        pass
                resultado = sincronizar_painel_completo()
                resultado["diagnostico_inicial"] = diag
                resultado["acao"] = "reparo_automatico"
            else:
                status = "indisponivel" if diag.get("motivo") == "api_indisponivel" else "ok"
                resultado = {"status": status, "diagnostico": diag, "sincronizacao": "nao_necessaria", "acao": "aguardar" if status == "indisponivel" else "ok"}
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

    threading.Thread(target=executar, daemon=True, name="MisticaPainelMobileAutoGuard").start()
    return True


def resultado_resumido(resultado: dict[str, Any]) -> str:
    try:
        diag = resultado.get("diagnostico") or {}
        return (
            f"API: {resultado.get('status')} | "
            f"produtos local/api {diag.get('local_produtos')}/{diag.get('api_produtos')} | "
            f"vendas local/api {diag.get('local_vendas_35_dias')}/{diag.get('api_vendas')} | "
            f"motivo {diag.get('motivo')}"
        )
    except Exception:
        return json.dumps(resultado, ensure_ascii=False)[:250]
