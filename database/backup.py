import os
import sqlite3
import traceback
from datetime import datetime, timedelta

from config import BACKUP_DIR, DB_PATH, ERROR_LOG_PATH


def _registrar_falha_backup(erro):
    try:
        os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " | Falha no backup automatico\n")
            f.write(str(erro) + "\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def realizar_backup(tag_extra=None):
    src = None
    dst = None
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        if tag_extra:
            tag = f"{tag}_{tag_extra}"
        caminho_bkp = os.path.join(BACKUP_DIR, f"mistica_auto_{tag}.db")
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(caminho_bkp)
        with dst:
            src.backup(dst)
        limpar_backups_antigos()
        return caminho_bkp
    except Exception as e:
        _registrar_falha_backup(e)
        return None
    finally:
        try:
            if src:
                src.close()
        except Exception:
            pass
        try:
            if dst:
                dst.close()
        except Exception:
            pass


def limpar_backups_antigos():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        limite = datetime.now() - timedelta(days=30)
        for arq in os.listdir(BACKUP_DIR):
            cam = os.path.join(BACKUP_DIR, arq)
            if os.path.isfile(cam) and arq.startswith("mistica_auto_"):
                if datetime.fromtimestamp(os.path.getmtime(cam)) < limite:
                    os.remove(cam)
    except Exception as e:
        _registrar_falha_backup(e)
