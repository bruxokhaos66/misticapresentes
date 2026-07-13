import json
from datetime import datetime
from pathlib import Path

from database.backup import criar_backup_seguro

APP_DIR = Path.home() / "Documents" / "Mistica_Presentes_App"
BACKUP_DIR = APP_DIR / "backups"
STATUS_PATH = APP_DIR / "ultimo_backup.json"


def salvar_status(dados):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def encontrar_bancos():
    base = Path.cwd()
    candidatos = [
        base / "mistica_presentes.db",
        base / "database" / "mistica_presentes.db",
        base / "database" / "mistica.db",
        Path.home() / "Documents" / "mistica_presentes.db",
        APP_DIR / "mistica_presentes.db",
    ]
    return [c for c in candidatos if c.exists() and c.is_file()]


def criar_backup_local(motivo="manual"):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bancos = encontrar_bancos()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not bancos:
        dados = {"ok": False, "motivo": motivo, "erro": "Banco local nao encontrado", "data": agora}
        salvar_status(dados)
        return dados
    arquivos = []
    falhas = []
    for banco in bancos:
        try:
            info = criar_backup_seguro(str(banco), str(BACKUP_DIR), f"{banco.stem}_{motivo}")
            arquivos.append(info["caminho"])
        except Exception:
            falhas.append(banco.name)
    dados = {"ok": bool(arquivos), "motivo": motivo, "arquivos": arquivos, "data": agora}
    if falhas:
        dados["erro"] = f"Falha ao copiar: {', '.join(falhas)}"
    salvar_status(dados)
    return dados


def backup_ao_iniciar():
    status = ler_status()
    hoje = datetime.now().strftime("%Y-%m-%d")
    if status.get("ok") and status.get("motivo") == "inicializacao" and str(status.get("data", ""))[:10] == hoje:
        return status
    return criar_backup_local("inicializacao")


def backup_pre_atualizacao():
    return criar_backup_local("pre_atualizacao")
