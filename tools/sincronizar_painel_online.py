import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import API_URL
from database import init_db, query_db
from services.sync_service import montar_payload_venda


def _api():
    return (API_URL or "https://api.misticaesotericos.com.br").rstrip("/")


def listar_produtos_locais():
    return query_db(
        """
        SELECT codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, COALESCE(ativo,1)
        FROM produtos
        ORDER BY nome
        """
    ) or []


def listar_vendas_locais():
    return query_db("SELECT id FROM vendas ORDER BY id") or []


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
        except Exception as exc:
            erros += 1
            print(f"Erro produto {nome}: {exc}")
    return {"criados": criados, "ignorados": ignorados, "erros": erros}


def sync_vendas(client):
    vendas = listar_vendas_locais()
    ok = 0
    erros = 0
    for (venda_id,) in vendas:
        try:
            payload = montar_payload_venda(venda_id)
            resp = client.post(f"{_api()}/api/sync/venda", json=payload)
            resp.raise_for_status()
            ok += 1
        except Exception as exc:
            erros += 1
            print(f"Erro venda {venda_id}: {exc}")
    return {"enviadas": ok, "erros": erros}


def main():
    init_db()
    print("API:", _api())
    with httpx.Client(timeout=15) as client:
        health = client.get(f"{_api()}/api/health")
        print("Health:", health.status_code)
        produtos = sync_produtos(client)
        vendas = sync_vendas(client)
        status = client.get(f"{_api()}/api/status").json()
        resumo = client.get(f"{_api()}/api/painel/resumo").json()
    print("Produtos:", json.dumps(produtos, ensure_ascii=False))
    print("Vendas:", json.dumps(vendas, ensure_ascii=False))
    print("Status API:", json.dumps(status, ensure_ascii=False))
    print("Resumo API:", json.dumps(resumo, ensure_ascii=False))


if __name__ == "__main__":
    main()
