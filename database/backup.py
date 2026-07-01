import os
import sqlite3
from datetime import datetime, timedelta

from config import BACKUP_DIR, DB_PATH


def realizar_backup(tag_extra=None):
    try:
        tag = datetime.now().strftime("%Y%m%d_%H")
        if tag_extra:
            tag = f"{tag}_{tag_extra}"
        caminho_bkp = os.path.join(BACKUP_DIR, f"mistica_auto_{tag}.db")
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(caminho_bkp)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        limpar_backups_antigos()
        return caminho_bkp
    except Exception:
        return None


def limpar_backups_antigos():
    try:
        limite = datetime.now() - timedelta(days=30)
        for arq in os.listdir(BACKUP_DIR):
            cam = os.path.join(BACKUP_DIR, arq)
            if os.path.isfile(cam) and arq.startswith("mistica_auto_"):
                if datetime.fromtimestamp(os.path.getmtime(cam)) < limite:
                    os.remove(cam)
    except Exception:
        pass
