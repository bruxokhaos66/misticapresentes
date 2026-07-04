import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import API_URL
from database import init_db, query_db
from services.dia_operacional_service import intervalo_vendas_hoje


def brl(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def vendas_locais():
    inicio, fim, dia = intervalo_vendas_hoje()
    rows = query_db(
        """
        SELECT id, COALESCE(data_venda,''), COALESCE(data_iso,''),
               COALESCE(vendedor,''), COALESCE(cliente,''),
               COALESCE(total_final,0), COALESCE(status,''), COALESCE(dia_operacional,'')
        FROM vendas
        WHERE COALESCE(status,'Concluído') NOT IN ('Cancelado','Cancelada')
          AND (
                COALESCE(dia_operacional,'') = ?
                OR (datetime(data_iso) >= datetime(?) AND datetime(data_iso) < datetime(?))
          )
        ORDER BY id DESC
        """,
        (dia, inicio, fim),
    ) or []
    return inicio, fim, dia, rows


def vendas_api():
    api = (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")
    with httpx.Client(timeout=20) as client:
        vendas = client.get(f"{api}/api/vendas?limite=500").json()
        status = client.get(f"{api}/api/status").json()
        resumo = client.get(f"{api}/api/painel/resumo").json()
    return api, vendas, status, resumo


def parse_iso(txt):
    bruto = str(txt or "").replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(bruto[:19], fmt)
        except Exception:
            pass
    return None


def filtrar_api(vendas, inicio, fim, dia):
    inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    fim_dt = datetime.strptime(fim, "%Y-%m-%d %H:%M:%S")
    out = []
    for v in vendas if isinstance(vendas, list) else []:
        status = str(v.get("status") or "Concluído")
        if status in ("Cancelado", "Cancelada"):
            continue
        data = parse_iso(v.get("data_iso") or v.get("data_venda"))
        dia_op = str(v.get("dia_operacional") or "")
        if dia_op == dia or (data and inicio_dt <= data < fim_dt):
            out.append(v)
    return out


def main():
    init_db()
    inicio, fim, dia, locais = vendas_locais()
    total_local = sum(float(r[5] or 0) for r in locais)
    api, vendas, status, resumo = vendas_api()
    api_hoje = filtrar_api(vendas, inicio, fim, dia)
    total_api = sum(float(v.get("total_final") or 0) for v in api_hoje)

    print("=== COMPARAÇÃO DESKTOP x APP/API ===")
    print("API:", api)
    print("Dia operacional:", dia)
    print("Intervalo:", inicio, "até", fim)
    print("Desktop vendas hoje:", len(locais), brl(total_local))
    print("API/App vendas hoje:", len(api_hoje), brl(total_api))
    print("Status API:", json.dumps(status, ensure_ascii=False))
    print("Resumo API:", json.dumps(resumo, ensure_ascii=False))
    print()

    print("--- VENDAS NO DESKTOP ---")
    for r in locais[:80]:
        print(f"LOCAL id={r[0]} | {r[1] or r[2]} | {r[3]} | {r[4]} | {brl(r[5])} | dia={r[7]}")
    print()

    print("--- VENDAS NA API/APP ---")
    for v in api_hoje[:80]:
        print(
            f"API id={v.get('id')} local_id={v.get('local_id')} | "
            f"{v.get('data_venda') or v.get('data_iso')} | {v.get('vendedor')} | "
            f"{v.get('cliente')} | {brl(v.get('total_final'))} | dia={v.get('dia_operacional')}"
        )

    ids_local = {str(r[0]) for r in locais}
    ids_api = {str(v.get("local_id") or "") for v in api_hoje}
    extras = [v for v in api_hoje if str(v.get("local_id") or "") not in ids_local]
    faltando = [r for r in locais if str(r[0]) not in ids_api]
    print()
    print("Extras na API sem venda local correspondente hoje:", len(extras))
    for v in extras[:30]:
        print(f"EXTRA API id={v.get('id')} local_id={v.get('local_id')} total={brl(v.get('total_final'))} data={v.get('data_venda') or v.get('data_iso')} dia={v.get('dia_operacional')}")
    print("Faltando na API:", len(faltando))
    for r in faltando[:30]:
        print(f"FALTA LOCAL id={r[0]} total={brl(r[5])} data={r[1] or r[2]} dia={r[7]}")


if __name__ == "__main__":
    main()
