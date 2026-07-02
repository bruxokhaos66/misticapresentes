"""Entrada alternativa do sistema Mística Presentes.

Funciona em modo Python normal e dentro do EXE gerado pelo PyInstaller.
Esta versão evita executar o arquivo principal via exec e usa importação normal.
"""
from pathlib import Path
import sys
from tkinter import messagebox

import customtkinter as ctk

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mistica_presentes import MisticaApp, garantir_instancia_unica, init_db, realizar_backup  # noqa: E402
from ui.admin_maintenance_patch import patch_mistica_app  # noqa: E402
from ui.dashboard_runtime_patch import patch_dashboard_runtime  # noqa: E402
from ui.maintenance_center_patch import patch_maintenance_center  # noqa: E402

patch_mistica_app(MisticaApp)
patch_dashboard_runtime(MisticaApp)
patch_maintenance_center(MisticaApp)


def main():
    if not garantir_instancia_unica():
        try:
            root = ctk.CTk()
            root.withdraw()
            messagebox.showwarning("Mística Presentes", "O sistema ja está aberto.")
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    init_db()
    realizar_backup()
    app = MisticaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
