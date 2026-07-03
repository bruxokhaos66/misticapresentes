import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _base_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def abrir_pagina_status():
    time.sleep(2)
    try:
        webbrowser.open("http://127.0.0.1:8000/docs")
    except Exception:
        pass


def main():
    base = _base_dir()
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    os.environ.setdefault("MISTICA_SERVER_MODE", "local")

    print("==============================================")
    print(" Mística Presentes - Servidor do Aplicativo")
    print("==============================================")
    print("Servidor local: http://127.0.0.1:8000")
    print("Documentação:   http://127.0.0.1:8000/docs")
    print("Para encerrar, feche esta janela.")
    print("==============================================")

    try:
        import uvicorn
    except Exception as exc:
        print("Erro: uvicorn não encontrado.")
        print("Instale as dependências com: pip install fastapi uvicorn")
        print(exc)
        input("Pressione ENTER para sair...")
        return

    threading.Thread(target=abrir_pagina_status, daemon=True).start()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
