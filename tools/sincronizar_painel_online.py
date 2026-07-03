import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import API_URL
from database import init_db, query_db
from services.sync_service import montar_payload_venda


REQ_TIMEOUT = httpx.Timeout(connect=5, read=8, write=8, pool=5)


def _api():
    return (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")


def _parse_data(txt):
    bruto = str(txt or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(bruto[:19], fmt)
        except Exception:
            pass
    return None


def listar_produtos_locais():
    return query_db(
        """
        SELECT codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, COALESCE(ativo,1)
        FROM produtos
        ORDER BY nome
        """
    ) or []


def listar_vendas_locais():
    corte = datetime.now() - timedelta(days=120)
    rows = query_db("SELECT id, data_venda, data_iso FROM vendas ORDER BY id") or []
    filtradas = []
    for venda_id, data_venda, data_iso in rows:
        data = _parse_data(data_iso) or _parse_data(data_venda)
        if data is None or data >= corte:
            filtradas.append((venda_id,))
    return filtradas


def sync_produtos(client):
    locais = listar_produtos_locais()
    try:
        remotos = client.get(f"{_api()}/api/produtos?limite=500").json()
    except Exception:
        remotos = []
    chaves_remotas = set()
    for p in remotos if isinstance(remotos, list) else []:
        chaves_remotas.add(str(p.get("codigo_p") or p.get("nome") or "").strip().lower())
        chaves_remotas.add(str(p.get("nome") or "").strip().lower())

    criados = 0
    ignorados = 0
    erros = 0
    for codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, ativo in locais:
        if not int(ativo or 0):
            ignorados += 1
            continue
        chave = str(codigo_p or nome or "").strip().lower()
        nome_chave = str(nome or "").strip().lower()
        if chave in chaves_remotas or nome_chave in chaves_remotas:
            ignorados += 1
            continue
        payload = {
            "codigo_p": codigo_p,
            "nome": nome,
            "preco": float(preco or 0),
            "quantidade": int(quantidade or 0),
            "categoria": categoria,
            "custo": float(custo or 0),
            "lucro": float(lucro or 0),
            "estoque_minimo": int(estoque_minimo or 0),
        }
        try:
            resp = client.post(f"{_api()}/api/produtos", json=payload)
            resp.raise_for_status()
            criados += 1
            chaves_remotas.add(chave)
            chaves_remotas.add(nome_chave)
        except Exception as exc:
            erros += 1
            print(f"Erro produto {nome}: {exc}", flush=True)
    return {"criados": criados, "ignorados": ignorados, "erros": erros}


def sync_vendas(client):
    vendas = listar_vendas_locais()
    total = len(vendas)
    ok = 0
    erros = 0
    print(f"Vendas locais para enviar: {total}", flush=True)
    for idx, (venda_id,) in enumerate(vendas, start=1):
        try:
            payload = montar_payload_venda(venda_id)
            resp = client.post(f"{_api()}/api/sync/venda", json=payload)
            resp.raise_for_status()
            ok += 1
        except Exception as exc:
            erros += 1
            print(f"Erro venda {venda_id}: {type(exc).__name__}: {exc}", flush=True)
        if idx == 1 or idx % 10 == 0 or idx == total:
            print(f"Progresso vendas: {idx}/{total} | ok={ok} | erros={erros}", flush=True)
    return {"enviadas": ok, "erros": erros, "total_local": total}


def main():
    init_db()
    print("API:", _api(), flush=True)
    with httpx.Client(timeout=REQ_TIMEOUT) as client:
        health = client.get(f"{_api()}/api/health")
        print("Health:", health.status_code, flush=True)
        produtos = sync_produtos(client)
        print("Produtos:", json.dumps(produtos, ensure_ascii=False), flush=True)
        vendas = sync_vendas(client)
        print("Vendas:", json.dumps(vendas, ensure_ascii=False), flush=True)
        status = client.get(f"{_api()}/api/status").json()
        resumo = client.get(f"{_api()}/api/painel/resumo").json()
    print("Status API:", json.dumps(status, ensure_ascii=False), flush=True)
    print("Resumo API:", json.dumps(resumo, ensure_ascii=False), flush=True)
    print("Concluido. Abra o painel no celular e toque em Atualizar.", flush=True)


if __name__ == "__main__":
    main()
