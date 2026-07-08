from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATES = ROOT / "dist" / "updates"
CANAIS = {
    "manifest.json": "win-modern-x64",
    "manifest-win10-x86.json": "win10-x86",
    "manifest-win7-x64.json": "win7-x64",
    "manifest-win7-x86.json": "win7-x86",
}


def main() -> None:
    base_path = UPDATES / "manifest.json"
    if not base_path.exists():
        raise SystemExit("manifest.json nao encontrado. Gere o pacote primeiro.")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    notas_base = str(base.get("notes") or "Atualizacao Mistica Presentes")
    for nome, canal in CANAIS.items():
        dados = dict(base)
        dados["channel"] = canal
        dados["notes"] = notas_base
        dados["channel_notes"] = f"Canal de atualizacao: {canal}"
        (UPDATES / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Manifestos por canal gerados em", UPDATES)


if __name__ == "__main__":
    main()
