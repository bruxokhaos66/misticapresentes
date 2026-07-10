#!/usr/bin/env python3
"""Move o site público de mistica-v2/ para a raiz com validações e rollback simples.

Uso:
    python scripts/migrate_mistica_v2_to_root.py --check
    python scripts/migrate_mistica_v2_to_root.py --apply

O modo --check não altera arquivos. O modo --apply:
- arquiva o index antigo da raiz;
- move o conteúdo ativo de mistica-v2/ para a raiz;
- corrige referências relativas conhecidas;
- mantém mistica-v2/index.html apenas como redirecionamento 301-equivalente estático;
- valida referências antigas e arquivos essenciais.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mistica-v2"
ARCHIVE = ROOT / "docs" / "archive" / "site-pre-v2-root"
TEXT_EXTENSIONS = {".html", ".css", ".js", ".json", ".xml", ".md", ".txt", ".webmanifest"}

ESSENTIAL = {
    "index.html",
    "v2.css",
    "v2-commerce.css",
    "v2-commerce.js",
    "v2-shamanic-player.css",
    "v2-shamanic-player.js",
    "v2-admin-access.js",
    "v2-admin-products.css",
    "v2-admin-products.js",
}

REPLACEMENTS = (
    ('href="../assets/', 'href="assets/'),
    ("href='../assets/", "href='assets/"),
    ('src="../assets/', 'src="assets/'),
    ("src='../assets/", "src='assets/"),
    ('href="../isis-lower-image.css', 'href="isis-lower-image.css'),
    ('src="../seo-site.js', 'src="seo-site.js'),
    ('src="../app.js', 'src="app.js'),
    ("mistica-v2/assets/", "assets/"),
    ("/mistica-v2/assets/", "/assets/"),
    ("https://www.misticaesotericos.com.br/mistica-v2/", "https://www.misticaesotericos.com.br/"),
    ("https://misticaesotericos.com.br/mistica-v2/", "https://misticaesotericos.com.br/"),
)

REDIRECT_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex,follow">
  <link rel="canonical" href="https://www.misticaesotericos.com.br/">
  <meta http-equiv="refresh" content="0; url=/">
  <title>Mística Presentes</title>
  <script>
    const target = '/' + window.location.search + window.location.hash;
    window.location.replace(target);
  </script>
</head>
<body>
  <p>Esta página mudou. <a href="/">Abrir Mística Presentes</a>.</p>
</body>
</html>
"""


def fail(message: str) -> None:
    print(f"ERRO: {message}", file=sys.stderr)
    raise SystemExit(1)


def inventory() -> list[Path]:
    if not SOURCE.is_dir():
        fail("a pasta mistica-v2/ não existe")
    files = sorted(path for path in SOURCE.rglob("*") if path.is_file())
    if not files:
        fail("mistica-v2/ está vazia")
    return files


def check_collisions(files: list[Path]) -> list[str]:
    collisions: list[str] = []
    for source_file in files:
        relative = source_file.relative_to(SOURCE)
        destination = ROOT / relative
        if destination.exists() and relative.as_posix() != "index.html":
            if destination.is_file() and destination.read_bytes() == source_file.read_bytes():
                continue
            collisions.append(relative.as_posix())
    return collisions


def rewrite_text(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    updated = original
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    if updated != original:
        path.write_text(updated, encoding="utf-8", newline="\n")
        return True
    return False


def validate() -> list[str]:
    errors: list[str] = []
    for required in sorted(ESSENTIAL):
        if not (ROOT / required).is_file():
            errors.append(f"arquivo essencial ausente: {required}")

    root_index = ROOT / "index.html"
    if root_index.is_file():
        content = root_index.read_text(encoding="utf-8", errors="replace")
        if "mistica-v2/" in content:
            errors.append("index.html da raiz ainda contém referência a mistica-v2/")
        if "noindex" in content.lower():
            errors.append("index.html da raiz contém noindex")

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path == SOURCE / "index.html":
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "mistica-v2/" in text and "docs/archive" not in path.as_posix():
            errors.append(f"referência antiga em {path.relative_to(ROOT)}")

    return errors


def apply(files: list[Path]) -> None:
    collisions = check_collisions(files)
    if collisions:
        fail("colisões não resolvidas: " + ", ".join(collisions))

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    root_index = ROOT / "index.html"
    if root_index.exists():
        shutil.copy2(root_index, ARCHIVE / "index.html")

    for source_file in files:
        relative = source_file.relative_to(SOURCE)
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.is_file() and destination.read_bytes() == source_file.read_bytes():
            source_file.unlink()
            continue
        shutil.move(str(source_file), str(destination))

    for directory in sorted((p for p in SOURCE.rglob("*") if p.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass

    SOURCE.mkdir(parents=True, exist_ok=True)
    (SOURCE / "index.html").write_text(REDIRECT_HTML, encoding="utf-8", newline="\n")

    changed = 0
    for path in ROOT.rglob("*"):
        if path.is_file() and ".git" not in path.parts and rewrite_text(path):
            changed += 1

    errors = validate()
    if errors:
        print("A migração foi aplicada, mas falhou na validação:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(2)

    print(f"Migração concluída. {len(files)} arquivos processados; {changed} textos reescritos.")
    print("Revise git diff, rode os testes e publique somente após validar o site localmente.")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="somente inventaria e valida riscos")
    mode.add_argument("--apply", action="store_true", help="aplica a migração")
    args = parser.parse_args()

    files = inventory()
    collisions = check_collisions(files)
    print(f"Arquivos encontrados em mistica-v2/: {len(files)}")
    if collisions:
        print("Colisões que exigem revisão:")
        for collision in collisions:
            print(f"- {collision}")
    else:
        print("Nenhuma colisão não resolvida encontrada.")

    if args.check:
        raise SystemExit(1 if collisions else 0)
    apply(files)


if __name__ == "__main__":
    main()
