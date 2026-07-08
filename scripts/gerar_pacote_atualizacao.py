from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_UPDATES = ROOT / "dist" / "updates"
UPDATE_BASE_URL = "https://misticaesotericos.com.br/updates"
INCLUIR_ARQUIVOS = [
    "app.py",
    "auto_updater.py",
    "app_frajola_patch.py",
    "app_pagamento_misto_patch.py",
    "app_sync_pagamento_misto_payload_patch.py",
    "app_caixa_fechamento_avancado_patch.py",
    "app_painel_guard_patch.py",
    "app_runtime_patch.py",
    "app_scroll_patch.py",
    "app_sync_status_patch.py",
    "app_version.py",
    "config.py",
    "mistica_presentes.py",
]
INCLUIR_PASTAS = [
    "api",
    "backend",
    "cloud_server",
    "database",
    "isis",
    "painel",
    "reports",
    "repositories",
    "services",
]
EXTENSOES = {".py", ".html", ".css", ".js", ".json"}


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b=""):
            h.update(bloco)
    return h.hexdigest()


def adicionar_arquivo(zf: zipfile.ZipFile, caminho: Path, destino: Path) -> None:
    if "__pycache__" in caminho.parts or caminho.suffix in {".pyc", ".pyo"}:
        return
    zf.write(caminho, destino.as_posix())


def gerar(versao: str) -> Path:
    DIST_UPDATES.mkdir(parents=True, exist_ok=True)
    pacote = DIST_UPDATES / f"mistica-update-{versao}.zip"
    if pacote.exists():
        pacote.unlink()
    with zipfile.ZipFile(pacote, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for nome in INCLUIR_ARQUIVOS:
            origem = ROOT / nome
            if origem.exists():
                adicionar_arquivo(zf, origem, Path(nome))
        for pasta in INCLUIR_PASTAS:
            origem_pasta = ROOT / pasta
            if not origem_pasta.exists():
                continue
            for origem in origem_pasta.rglob("*"):
                if origem.is_file() and origem.suffix.lower() in EXTENSOES:
                    adicionar_arquivo(zf, origem, origem.relative_to(ROOT))
    manifesto = {
        "version": versao,
        "package_file": "",
        "package_url": f"{UPDATE_BASE_URL}/{pacote.name}",
        "sha256": sha256(pacote),
        "notes": "Atualizacao Mistica Presentes",
    }
    with open(DIST_UPDATES / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
    return pacote


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Informe a versao. Exemplo: python scripts/gerar_pacote_atualizacao.py 1.0.1")
    versao = sys.argv[1].strip()
    (ROOT / "app_version.py").write_text(f'APP_VERSION = "{versao}"\n', encoding="utf-8")
    pacote = gerar(versao)
    pasta_local = Path.home() / "Documents" / "Mistica_Presentes_Updates"
    pasta_local.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pacote, pasta_local / pacote.name)
    shutil.copy2(DIST_UPDATES / "manifest.json", pasta_local / "manifest.json")
    print("Pacote gerado:", pacote)
    print("Manifesto:", DIST_UPDATES / "manifest.json")
    print("Copia local pronta em:", pasta_local)


if __name__ == "__main__":
    main()
