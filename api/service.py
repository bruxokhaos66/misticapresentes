"""Serviços de leitura para painel/API local.

Esta primeira fase não grava vendas nem estoque pela rede. O objetivo é
acompanhar em tempo real sem quebrar o sistema desktop atual.
"""
from datetime import date, datetime
import os

from database import query_db
from reports.estoque_report import estoque_baixo
from reports.financeiro_report import contas_para_alerta
from services.caixa_service import status_caixa_aberto, resumo_fechamento_caixa
from services.isis_service import alertas_operacionais
from api.security import resumo_seguranca_api

ANDROID_APP_VERSION = "1.1.0"
ANDROID_APP_VERSION_CODE = 2


def _moeda(valor):
    try:
        return float(valor or 0.0)
    except Exception:
        return 0.0


def app_android_info():
    return {
        "app": "Mística Painel Android",
        "latest_version": ANDROID_APP_VERSION,
        "latest_version_code": ANDROID_APP_VERSION_CODE,
        "apk_name": "app-debug.apk",
        "message": "Versão com tela Sobre / Atualização, status de conexão e visual premium.",
        "manual_update": True,
        "instructions": [
            "Atualize o repositório com git pull origin main.",
            "Gere um novo APK no Android Studio.",
            "Instale o APK novo por cima do antigo no celular.",
        ],
    }


def server_status_api():
    seguranca = resumo_seguranca_api()
    return {
        "ok": True,
        "servico": "Mística Presentes API Local",
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "app_android": app_android_info(),
        "seguranca": seguranca,
        "ambiente": {
            "porta": os.getenv("MISTICA_SERVER_PORT", "8000"),
            "modo_externo_recomendado": seguranca["token_forte_configurado"],
        },
    }


def vendas_do_dia():
    hoje_br = datetime.now().strftime("%d/%m/%Y")
    hoje_iso = date.today().strftime("%Y-%m-%d")
    res = query_db(
        """
        SELECT COUNT(*), COALESCE(SUM(total_final),0)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND (
              data_iso LIKE ?
              OR (COALESCE(data_iso,'')='' AND data_venda LIKE ?)
          )
        """,
        (f"{hoje_iso}%", f"%{hoje_br}%"),
    )
    qtd, total = res[0] if res else (0, 0.0)
    return {"data": hoje_br, "quantidade": int(qtd or 0), "faturamento": _moeda(total)}


def ultimas_vendas(limite=10):
    linhas = query_db(
        """
        SELECT id, data_venda, cliente, total_final, forma_pagamento, vendedor, status
        FROM vendas
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limite),),
    )
    return [
        {
            "id": r[0],
            "data_venda": r[1],
            "cliente": r[2],
            "total_final": _moeda(r[3]),
            "forma_pagamento": r[4],
            "vendedor": r[5],
            "status": r[6],
        }
        for r in linhas
    ]


def cancelamentos_recentes(limite=10):
    linhas = query_db(
        """
        SELECT id, data_venda, cliente, total_final, forma_pagamento, vendedor, status
        FROM vendas
        WHERE status='Cancelado'
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limite),),
    )
    return [
        {
            "id": r[0],
            "data_venda": r[1],
            "cliente": r[2],
            "total_final": _moeda(r[3]),
            "forma_pagamento": r[4],
            "vendedor": r[5],
            "status": r[6],
        }
        for r in linhas
    ]


def caixa_status():
    caixa = status_caixa_aberto()
    resumo = resumo_fechamento_caixa() if caixa else None
    return {
        "aberto": bool(caixa),
        "status": caixa[0] if caixa else "Fechado",
        "saldo_inicial": _moeda(caixa[1]) if caixa else 0.0,
        "data_abertura": caixa[2] if caixa else None,
        "resumo": resumo,
    }


def estoque_baixo_api(limite=10):
    return [
        {"produto": r[0], "quantidade": int(r[1] or 0), "estoque_minimo": int(r[2] or 0)}
        for r in estoque_baixo(limite)
    ]


def contas_alerta_api():
    contas = []
    for desc, valor, vencimento in contas_para_alerta():
        contas.append({"descricao": desc, "valor": _moeda(valor), "vencimento": vencimento})
    return contas


def alertas_isis_api():
    texto = alertas_operacionais(formatador=lambda v: f"R$ {float(v or 0):.2f}".replace(".", ","))
    return {"texto": texto}


def dashboard_api():
    return {
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "seguranca": resumo_seguranca_api(),
        "vendas_hoje": vendas_do_dia(),
        "caixa": caixa_status(),
        "ultimas_vendas": ultimas_vendas(8),
        "estoque_baixo": estoque_baixo_api(8),
        "cancelamentos": cancelamentos_recentes(5),
        "contas_alerta": contas_alerta_api(),
        "alertas_isis": alertas_isis_api(),
    }
