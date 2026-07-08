from __future__ import annotations

import hashlib
import json
import platform
import shutil
import struct
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
UPDATE_BASE_URL = "https://misticaesotericos.com.br/updates"
DEFAULT_MANIFEST_URL = f"{UPDATE_BASE_URL}/manifest.json"


def detectar_windows():
    bits = struct.calcsize("P") * 8
    sistema = platform.system() or "Windows"
    release = platform.release() or ""
    version = platform.version() or ""
    machine = platform.machine() or ""
    try:
        build = int(version.split(".")[-1]) if version else 0
    except Exception:
        build = 0

    nome = f"{sistema} {release}".strip()
    canal = "win-modern-x64"
    manifest = "manifest.json"

    if release in {"7", "8", "8.1"}:
        if bits == 32:
            canal = "win7-x86"
            manifest = "manifest-win7-x86.json"
        else:
            canal = "win7-x64"
            manifest = "manifest-win7-x64.json"
    elif release == "10" and build >= 22000:
        nome = "Windows 11"
        canal = "win11-x64" if bits == 64 else "win10-x86"
        manifest = "manifest.json" if bits == 64 else "manifest-win10-x86.json"
    elif release == "10":
        canal = "win10-x64" if bits == 64 else "win10-x86"
        manifest = "manifest.json" if bits == 64 else "manifest-win10-x86.json"
    elif bits == 32:
        canal = "win-legacy-x86"
        manifest = "manifest-win7-x86.json"

    return {
        "nome": nome,
        "release": release,
        "version": version,
        "build": build,
        "bits": bits,
        "machine": machine,
        "canal": canal,
        "manifest": manifest,
        "manifest_url": f"{UPDATE_BASE_URL}/{manifest}",
    }


def preparar_atualizacao(progress_callback=None) -> Path | None:
    """Ativa a ultima versao boa e baixa uma nova quando houver manifesto valido."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    ambiente = detectar_windows()

    def progresso(etapa, mensagem, progresso_valor=None, **extra):
        if progress_callback:
            try:
                dados = {"etapa": etapa, "mensagem": mensagem, "ambiente": ambiente}
                if progresso_valor is not None:
                    dados["progresso"] = progresso_valor
                dados.update(extra)
                progress_callback(dados)
            except Exception:
                pass

    atual = atualizacao_instalada()
    ativar_caminho(atual)

    try:
        progresso("inicio", f"{ambiente['nome']} {ambiente['bits']} bits detectado. Canal: {ambiente['canal']}.", 0.03)
        progresso("verificando", "Verificando atualizacoes online...", 0.08)
        manifest = carregar_manifest(ambiente)
        if not manifest:
            progresso("sem_manifesto", "Nenhuma atualizacao online encontrada. Abrindo programa...", 1.0)
            return atual
        versao_online = str(manifest.get("version", "")).strip()
        if not versao_online:
            progresso("sem_versao", "Manifesto sem versao. Abrindo programa...", 1.0)
            return atual
        if versao_online in versoes_bloqueadas():
            progresso("bloqueada", f"Versao {versao_online} foi bloqueada por erro anterior. Abrindo versao atual...", 1.0)
            return atual
        if not versao_maior(versao_online, versao_atual_ativa()):
            progresso("atual", f"Programa ja esta atualizado ({versao_atual_ativa()}).", 1.0)
            return atual
        progresso("nova", f"Nova versao encontrada: {versao_online}. Baixando...", 0.15)
        pacote = obter_pacote(manifest, progress_callback=progress_callback)
        if not pacote:
            progresso("sem_pacote", "Nao encontrei pacote de atualizacao. Abrindo programa...", 1.0)
            return atual
        progresso("validando", "Validando pacote baixado...", 0.78)
        validar_sha256(pacote, str(manifest.get("sha256", "")).strip())
        progresso("instalando", "Instalando atualizacao...", 0.88)
        destino = instalar_pacote(pacote, versao_online)
        salvar_json(CURRENT_PATH, {
            "version": versao_online,
            "path": str(destino),
            "notes": manifest.get("notes", ""),
            "canal": ambiente.get("canal"),
        })
        salvar_status({"ok": True, "version": versao_online, "path": str(destino), "canal": ambiente.get("canal")})
        ativar_caminho(destino)
        progresso("concluido", f"Atualizacao {versao_online} instalada. Abrindo programa...", 1.0)
        return destino
    except Exception as exc:
        salvar_status({"ok": False, "erro": str(exc), "canal": ambiente.get("canal")})
        progresso("erro", f"Nao foi possivel atualizar agora: {exc}. Abrindo versao atual...", 1.0, erro=str(exc))
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


def carregar_manifest(ambiente=None) -> dict | None:
    ambiente = ambiente or detectar_windows()
    cfg = ler_json(CONFIG_PATH)
    manifest_url = str(cfg.get("manifest_url", "")).strip() or ambiente.get("manifest_url") or DEFAULT_MANIFEST_URL
    if manifest_url:
        if not manifest_url.lower().startswith("https://"):
            raise ValueError("URL de atualizacao precisa usar HTTPS.")
        return baixar_json(manifest_url)
    if LOCAL_MANIFEST_PATH.exists():
        return ler_json(LOCAL_MANIFEST_PATH)
    return None


def obter_pacote(manifest: dict, progress_callback=None) -> Path | None:
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
        baixar_arquivo_com_progresso(package_url, destino, progress_callback=progress_callback)
        return destino
    return None


def baixar_arquivo_com_progresso(url: str, destino: Path, progress_callback=None) -> Path:
    with urllib.request.urlopen(url, timeout=20) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        baixado = 0
        with open(destino, "wb") as f:
            while True:
                bloco = resp.read(1024 * 128)
                if not bloco:
                    break
                f.write(bloco)
                baixado += len(bloco)
                if progress_callback:
                    try:
                        frac = baixado / total if total else 0
                        progress_callback({
                            "etapa": "download",
                            "mensagem": f"Baixando atualizacao... {baixado // 1024} KB",
                            "progresso": 0.15 + min(frac, 1) * 0.60,
                            "baixado": baixado,
                            "total": total,
                        })
                    except Exception:
                        pass
    return destino


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
        for bloco in iter(lambda: f.read(1024 * 1024), b=""):
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
