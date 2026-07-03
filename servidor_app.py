import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from config import DEFAULT_API_URL, DEFAULT_SERVER_URL


def _base_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def abrir_painel_oficial():
    time.sleep(1)
    try:
        webbrowser.open(DEFAULT_SERVER_URL)
    except Exception:
        pass


def main():
    base = _base_dir()
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    os.environ.setdefault("MISTICA_SERVER_MODE", "production")

    print("==============================================")
    print(" Mistica Presentes - Painel Online Oficial")
    print("==============================================")
    print(f"Painel: {DEFAULT_SERVER_URL}")
    print(f"API:    {DEFAULT_API_URL}")
    print("Local auxiliar: http://127.0.0.1:8000")
    print("==============================================")

    threading.Thread(target=abrir_painel_oficial, daemon=True).start()

    try:
        import uvicorn
    except Exception as exc:
        print("Uvicorn nao encontrado.")
        print(exc)
        input("Pressione ENTER para sair...")
        return

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
