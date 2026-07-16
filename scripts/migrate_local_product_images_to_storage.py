"""Migra imagens de produtos que ainda estão no disco local para o storage
remoto configurado (PRODUCT_IMAGES_*), atualizando imagem_url/imagens_json
no banco.

Não é destrutivo por padrão:
- roda em --dry-run por padrão (nada é enviado nem gravado, só relata o que
  faria);
- passe --apply para efetivar o envio e a atualização do banco;
- é seguro rodar mais de uma vez: produtos cuja URL já aponta para
  PRODUCT_IMAGES_PUBLIC_BASE_URL são pulados (não duplica upload);
- produtos cujo arquivo local já não existe mais são listados à parte --
  o script nunca inventa uma imagem, só sinaliza que aquele produto precisa
  de reenvio manual pelo painel.

Uso:
    python -m scripts.migrate_local_product_images_to_storage            # dry-run
    python -m scripts.migrate_local_product_images_to_storage --apply     # efetiva
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import conectar, listar  # noqa: E402
from backend.product_image_storage import ProductImageStorageError  # noqa: E402
from backend.upload_routes import UPLOAD_DIR, imagem_storage  # noqa: E402

FORMATO_POR_EXTENSAO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _extrair_nome_local(url: str) -> str | None:
    if url and url.startswith("/uploads/produtos/"):
        return Path(url).name
    return None


def _substituir(url: str, antigo_nome: str, nova_url: str) -> str:
    if _extrair_nome_local(url) == antigo_nome:
        return nova_url
    return url


def migrar(*, aplicar: bool) -> dict:
    if not imagem_storage.remote_enabled:
        raise SystemExit(
            "PRODUCT_IMAGES_STORAGE_ENABLED não está ativo. Configure o storage remoto "
            "(veja .env.example / render.yaml) antes de migrar."
        )

    produtos = listar("SELECT id, codigo_p, nome, imagem_url, imagens_json FROM produtos WHERE COALESCE(ativo,1)=1")
    relatorio = {"migrados": [], "ja_migrados": [], "arquivos_ausentes": [], "sem_imagem_local": []}

    for produto in produtos:
        imagem_url = produto.get("imagem_url") or ""
        try:
            extras = json.loads(produto.get("imagens_json") or "[]")
        except Exception:
            extras = []

        nome_local = _extrair_nome_local(imagem_url)
        if not nome_local:
            relatorio["sem_imagem_local"].append(produto["id"])
            continue
        if imagem_storage.remote_enabled and imagem_storage.config.public_base_url in imagem_url:
            relatorio["ja_migrados"].append(produto["id"])
            continue

        caminho = UPLOAD_DIR / nome_local
        if not caminho.is_file():
            relatorio["arquivos_ausentes"].append({"produto_id": produto["id"], "codigo_p": produto.get("codigo_p"), "arquivo_esperado": str(caminho)})
            continue

        ext = caminho.suffix.lower()
        content_type = FORMATO_POR_EXTENSAO.get(ext, "application/octet-stream")
        dados = caminho.read_bytes()

        if not aplicar:
            relatorio["migrados"].append({"produto_id": produto["id"], "arquivo": str(caminho), "dry_run": True})
            continue

        try:
            resultado = imagem_storage.upload(dados, produto_id=produto.get("codigo_p") or str(produto["id"]), ext=ext, content_type=content_type)
        except ProductImageStorageError as exc:
            relatorio["arquivos_ausentes"].append({"produto_id": produto["id"], "erro": str(exc)})
            continue

        nova_imagem_url = _substituir(imagem_url, nome_local, resultado["url"])
        novas_extras = [_substituir(url, nome_local, resultado["url"]) for url in extras]
        with conectar() as conn:
            conn.execute(
                "UPDATE produtos SET imagem_url=?, imagens_json=? WHERE id=?",
                (nova_imagem_url, json.dumps(novas_extras, ensure_ascii=False), produto["id"]),
            )
            conn.commit()
        relatorio["migrados"].append({"produto_id": produto["id"], "nova_url": resultado["url"], "dry_run": False})

    return relatorio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", dest="aplicar", action="store_true", help="Efetiva a migração (padrão: dry-run).")
    args = parser.parse_args()

    relatorio = migrar(aplicar=args.aplicar)
    modo = "APLICADO" if args.aplicar else "DRY-RUN (nada foi enviado ou alterado)"
    print(f"Modo: {modo}")
    print(f"Migrados: {len(relatorio['migrados'])}")
    print(f"Já migrados anteriormente: {len(relatorio['ja_migrados'])}")
    print(f"Sem imagem local (já usam storage remoto/externo): {len(relatorio['sem_imagem_local'])}")
    if relatorio["arquivos_ausentes"]:
        print(f"Produtos com arquivo local ausente -- precisam de reenvio pelo painel ({len(relatorio['arquivos_ausentes'])}):")
        for item in relatorio["arquivos_ausentes"]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
