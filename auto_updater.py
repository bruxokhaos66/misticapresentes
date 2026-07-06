from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from app_version import APP_VERSION


APP_DATA_DIR = Path.home() / "Documents" / "Mistica_Presentes_App"
UPDATES_DIR = APP_DATA_DIR / "updates"
CONFIG_PATH = Path.home() / "Documents" / "mistica_atualizador.json"
LOCAL_MANIFEST_PATH = Path.home() / "Documents" / "Mistica_Presentes_Updates" / "manifest.json"
STATUS_PATH = APP_DATA_DIR / "atualizador_status.json"
CURRENT_PATH = APP_DATA_DIR / "current.json"
BAD_VERSIONS_PATH = APP_DATA_DIR / "bad_versions.json"
DEFAULT_MANIFEST_URL = "https://misticaesotericos.com.br/updates/manifest.json"


def preparar_atualizacao() -> Path | None:
    """Ativa a ultima versao boa e baixa uma nova quando houver manifesto valido."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    atual = atualizacao_instalada()
    ativar_caminho(atual)

    try:
        manifest = carregar_manifest()
        if not manifest:
            return atual
        versao_online = str(manifest.get("version", "")).strip()
        if not versao_online or versao_online in versoes_bloqueadas():
            return atual
        if not versao_maior(versao_online, versao_atual_ativa()):
            return atual
        pacote = obter_pacote(manifest)
        if not pacote:
            return atual
        validar_sha256(pacote, str(manifest.get("sha256", "")).strip())
        destino = instalar_pacote(pacote, versao_online)
        salvar_json(CURRENT_PATH, {
            "version": versao_online,
            "path": str(destino),
            "notes": manifest.get("notes", ""),
        })
        salvar_status({"ok": True, "version": versao_online, "path": str(destino)})
        ativar_caminho(destino)
        return destino
    except Exception as exc:
        salvar_status({"ok": False, "erro": str(exc)})
        return atual


def atualizacao_instalada() -> Path | None:
    info = ler_json(CURRENT_PATH)
    caminho = Path(str(info.get("path", ""))) if info else None
    if caminho and caminho.exists() and str(info.get("version", "")) not in versoes_bloqueadas():
        return caminho
    return None


def ativar_caminho(caminho: Path | None) -> None:
    if caminho and caminho.exists() and str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))


def desativar_atualizacao_com_erro(erro: str) -> None:
    info = ler_json(CURRENT_PATH)
    versao = str(info.get("version", "")).strip()
    bloqueadas = versoes_bloqueadas()
    if versao:
        bloqueadas.add(versao)
        salvar_json(BAD_VERSIONS_PATH, {"versions": sorted(bloqueadas)})
    if CURRENT_PATH.exists():
        CURRENT_PATH.unlink()
    salvar_status({"ok": False, "rollback": True, "version": versao, "erro": erro})


def versao_atual_ativa() -> str:
    info = ler_json(CURRENT_PATH)
    return str(info.get("version") or APP_VERSION)


def versoes_bloqueadas() -> set[str]:
    dados = ler_json(BAD_VERSIONS_PATH)
    return set(str(v) for v in dados.get("versions", []))


def carregar_manifest() -> dict | None:
    cfg = ler_json(CONFIG_PATH)
    manifest_url = str(cfg.get("manifest_url", "")).strip() or DEFAULT_MANIFEST_URL
    if manifest_url:
        if not manifest_url.lower().startswith("https://"):
            raise ValueError("URL de atualizacao precisa usar HTTPS.")
        return baixar_json(manifest_url)
    if LOCAL_MANIFEST_PATH.exists():
        return ler_json(LOCAL_MANIFEST_PATH)
    return None


def obter_pacote(manifest: dict) -> Path | None:
    package_file = str(manifest.get("package_file", "")).strip()
    package_url = str(manifest.get("package_url", "")).strip()
    if package_file:
        caminho = Path(package_file).expanduser()
        if not caminho.is_absolute():
            caminho = LOCAL_MANIFEST_PATH.parent / caminho
        return caminho if caminho.exists() else None
    if package_url:
        if not package_url.lower().startswith("https://"):
            raise ValueError("Pacote online precisa usar HTTPS.")
        nome = package_url.rsplit("/", 1)[-1] or "update.zip"
        destino = Path(tempfile.gettempdir()) / f"mistica_update_{nome}"
        urllib.request.urlretrieve(package_url, destino)
        return destino
    return None


def instalar_pacote(pacote: Path, versao: str) -> Path:
    destino = UPDATES_DIR / nome_seguro(versao)
    temp_dir = UPDATES_DIR / f".tmp_{nome_seguro(versao)}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pacote, "r") as zf:
        extrair_zip_seguro(zf, temp_dir)
    if not (temp_dir / "mistica_presentes.py").exists():
        raise ValueError("Pacote de atualizacao invalido: mistica_presentes.py nao encontrado.")
    temp_dir.rename(destino)
    return destino


def validar_sha256(caminho: Path, esperado: str) -> None:
    if not esperado:
        raise ValueError("Manifesto sem sha256 do pacote.")
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    if h.hexdigest().lower() != esperado.lower():
        raise ValueError("Pacote de atualizacao com hash diferente do manifesto.")


def extrair_zip_seguro(zf: zipfile.ZipFile, destino: Path) -> None:
    raiz = destino.resolve()
    for item in zf.infolist():
        alvo = (destino / item.filename).resolve()
        if not str(alvo).startswith(str(raiz)):
            raise ValueError("Pacote de atualizacao contem caminho inseguro.")
    zf.extractall(destino)


def baixar_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ler_json(caminho: Path) -> dict:
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def salvar_status(dados: dict) -> None:
    salvar_json(STATUS_PATH, dados)


def versao_maior(nova: str, atual: str) -> bool:
    return partes_versao(nova) > partes_versao(atual)


def partes_versao(valor: str) -> tuple:
    partes = []
    for pedaco in valor.replace("-", ".").split("."):
        partes.append(int(pedaco) if pedaco.isdigit() else pedaco)
    return tuple(partes)


def nome_seguro(valor: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in valor)
