import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import API_URL
from services.dia_operacional_service import intervalo_vendas_hoje


def brl(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_data(v):
    bruto = str(v.get("data_iso") or v.get("data_venda") or "").replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(bruto[:19], fmt)
        except Exception:
            pass
    return None


def venda_ativa(v):
    status = str(v.get("status") or "Concluído").strip().lower()
    return status not in ("cancelado", "cancelada")


def main():
    api = (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")
    inicio, fim, dia = intervalo_vendas_hoje()
    inicio_dt = datetime.strptime(inicio, "%Y-%m-%d %H:%M:%S")
    fim_dt = datetime.strptime(fim, "%Y-%m-%d %H:%M:%S")

    with httpx.Client(timeout=20) as client:
        print("API:", api)
        for login, senha in [("bruxo", "1234"), ("bruxa", "1234")]:
            try:
                r = client.post(f"{api}/api/auth/login", json={"login": login, "senha": senha})
                print(f"Login {login}:", r.status_code, r.text[:300])
            except Exception as exc:
                print(f"Login {login}: ERRO {type(exc).__name__}: {exc}")
        status = client.get(f"{api}/api/status").json()
        resumo = client.get(f"{api}/api/painel/resumo").json()
        vendas = client.get(f"{api}/api/vendas?limite=500").json()

    hoje = []
    for v in vendas if isinstance(vendas, list) else []:
        if not venda_ativa(v):
            continue
        data = parse_data(v)
        dia_op = str(v.get("dia_operacional") or "").strip()
        if dia_op == dia or (data and inicio_dt <= data < fim_dt):
            hoje.append(v)

    total = sum(float(v.get("total_final") or 0) for v in hoje)
    print("Status API:", json.dumps(status, ensure_ascii=False))
    print("Resumo API:", json.dumps(resumo, ensure_ascii=False))
    print("Dia operacional:", dia, inicio, "até", fim)
    print("Vendas que o painel deveria mostrar hoje:", len(hoje), brl(total))
    for v in hoje:
        print(f"- id={v.get('id')} local_id={v.get('local_id')} data={v.get('data_venda') or v.get('data_iso')} vendedor={v.get('vendedor')} total={brl(v.get('total_final'))} dia={v.get('dia_operacional')}")

    if total == 0:
        print("\nATENÇÃO: a API está zerada ou sem vendas no dia operacional. Rode: python tools/sincronizar_painel_online.py")
    else:
        print("\nAPI OK. Se o celular mostra outro valor, o problema é cache, login errado ou APK antigo.")


if __name__ == "__main__":
    main()
