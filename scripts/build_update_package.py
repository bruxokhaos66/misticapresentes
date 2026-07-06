from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATES_DIR = ROOT / "updates"
DEFAULT_BASE_URL = "https://misticaesotericos.com.br/updates"

INCLUDE_FILES = [
    "mistica_presentes.py",
    "config.py",
    "app_version.py",
    "app_runtime_patch.py",
    "app_sync_status_patch.py",
    "app_painel_guard_patch.py",
    "app_scroll_patch.py",
]
INCLUDE_DIRS = [
    "database",
    "services",
    "assets",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add_file(zf: zipfile.ZipFile, file_path: Path, arcname: str) -> None:
    if file_path.exists() and file_path.is_file():
        zf.write(file_path, arcname)


def add_dir(zf: zipfile.ZipFile, dir_path: Path, arc_prefix: str) -> None:
    if not dir_path.exists():
        return
    for file_path in dir_path.rglob("*"):
        if file_path.is_file() and "__pycache__" not in file_path.parts:
            zf.write(file_path, str(Path(arc_prefix) / file_path.relative_to(dir_path)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera pacote de atualização online da Mística Presentes.")
    parser.add_argument("--version", required=True, help="Versão nova. Ex: 1.0.2")
    parser.add_argument("--notes", default="Atualização online da Mística Presentes.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    package_name = f"mistica-update-{args.version}.zip"
    package_path = UPDATES_DIR / package_name

    if package_path.exists():
        package_path.unlink()

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in INCLUDE_FILES:
            add_file(zf, ROOT / rel, rel)
        for rel in INCLUDE_DIRS:
            add_dir(zf, ROOT / rel, rel)

    digest = sha256_file(package_path)
    manifest = {
        "version": args.version,
        "package_url": f"{args.base_url.rstrip('/')}/{package_name}",
        "sha256": digest,
        "notes": args.notes,
    }
    (UPDATES_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pacote: {package_path}")
    print(f"SHA256: {digest}")
    print(f"Manifesto: {UPDATES_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
