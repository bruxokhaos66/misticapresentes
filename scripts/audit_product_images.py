"""Auditoria somente-leitura das imagens de produtos já cadastradas.

Lista todo produto ativo com imagem (imagem_url/imagens_json), confere se a
URL responde, detecta 404/erro, caminhos locais ausentes no disco e URLs
duplicadas entre produtos diferentes. NÃO exclui nem modifica nada -- é só
diagnóstico, para decidir manualmente o que precisa de reenvio pelo painel
ou de migração para o storage remoto.

Uso:
    python -m scripts.audit_product_images
    python -m scripts.audit_product_images --json relatorio.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import listar  # noqa: E402
from backend.upload_routes import UPLOAD_DIR  # noqa: E402

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None


def _urls_do_produto(produto: dict) -> list[str]:
    urls = []
    if produto.get("imagem_url"):
        urls.append(produto["imagem_url"])
    try:
        extras = json.loads(produto.get("imagens_json") or "[]")
    except Exception:
        extras = []
    for url in extras:
        if url and url not in urls:
            urls.append(url)
    return urls


def _checar_url(url: str, timeout: float) -> tuple[str, str]:
    """Devolve (status, detalhe). status em: ok, 404, erro, local_ausente, sem_verificar."""
    if url.startswith("/uploads/produtos/"):
        nome = Path(url).name
        return ("ok", "arquivo local presente") if (UPLOAD_DIR / nome).is_file() else ("local_ausente", str(UPLOAD_DIR / nome))
    if not url.startswith(("http://", "https://")):
        return ("invalida", "não é uma URL http(s) nem caminho local conhecido")
    if httpx is None:
        return ("sem_verificar", "httpx indisponível neste ambiente")
    try:
        resposta = httpx.head(url, timeout=timeout, follow_redirects=True)
        if resposta.status_code == 405:  # alguns hosts não aceitam HEAD
            resposta = httpx.get(url, timeout=timeout, follow_redirects=True)
        if resposta.status_code == 404:
            return ("404", f"HTTP {resposta.status_code}")
        if resposta.status_code >= 400:
            return ("erro", f"HTTP {resposta.status_code}")
        return ("ok", f"HTTP {resposta.status_code}")
    except Exception as exc:
        return ("erro", f"{type(exc).__name__}: {exc}")


def auditar(*, timeout: float = 8.0) -> dict:
    produtos = listar("SELECT id, codigo_p, nome, imagem_url, imagens_json FROM produtos WHERE COALESCE(ativo,1)=1")
    por_url: dict[str, list[int]] = defaultdict(list)
    relatorio = {"total_produtos": len(produtos), "produtos_sem_imagem": 0, "itens": []}

    for produto in produtos:
        urls = _urls_do_produto(produto)
        if not urls:
            relatorio["produtos_sem_imagem"] += 1
            continue
        for url in urls:
            por_url[url].append(produto["id"])
            status, detalhe = _checar_url(url, timeout)
            relatorio["itens"].append({
                "produto_id": produto["id"],
                "codigo_p": produto.get("codigo_p"),
                "nome": produto.get("nome"),
                "url": url,
                "status": status,
                "detalhe": detalhe,
            })

    relatorio["duplicadas"] = {url: ids for url, ids in por_url.items() if len(ids) > 1}
    contagem = defaultdict(int)
    for item in relatorio["itens"]:
        contagem[item["status"]] += 1
    relatorio["resumo_status"] = dict(contagem)
    relatorio["precisam_reenvio"] = [
        item for item in relatorio["itens"] if item["status"] in ("404", "local_ausente", "invalida")
    ]
    return relatorio


def imprimir_relatorio(relatorio: dict) -> None:
    print("=" * 72)
    print("Auditoria de imagens de produtos (somente leitura)")
    print("=" * 72)
    print(f"Produtos ativos: {relatorio['total_produtos']}")
    print(f"Produtos sem nenhuma imagem cadastrada: {relatorio['produtos_sem_imagem']}")
    print(f"URLs verificadas: {len(relatorio['itens'])}")
    print(f"Resumo por status: {relatorio['resumo_status']}")
    print()
    if relatorio["duplicadas"]:
        print(f"URLs usadas por mais de um produto ({len(relatorio['duplicadas'])}):")
        for url, ids in relatorio["duplicadas"].items():
            print(f"  - {url} -> produtos {ids}")
        print()
    if relatorio["precisam_reenvio"]:
        print(f"Produtos que precisam de nova imagem pelo painel ({len(relatorio['precisam_reenvio'])}):")
        for item in relatorio["precisam_reenvio"]:
            print(f"  - produto {item['produto_id']} ({item['codigo_p'] or 's/código'} - {item['nome']}): "
                  f"{item['status']} em {item['url']} ({item['detalhe']})")
    else:
        print("Nenhuma URL quebrada encontrada.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=8.0, help="Timeout por requisição HTTP (segundos).")
    parser.add_argument("--json", dest="json_path", default=None, help="Também grava o relatório completo em JSON neste caminho.")
    args = parser.parse_args()

    relatorio = auditar(timeout=args.timeout)
    imprimir_relatorio(relatorio)

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRelatório completo salvo em {args.json_path}")


if __name__ == "__main__":
    main()
