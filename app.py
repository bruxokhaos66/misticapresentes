from pathlib import Path
import sys

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MAIN_FILE = BASE_DIR / "mistica_presentes.py"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {MAIN_FILE}")

    fonte = MAIN_FILE.read_text(encoding="utf-8-sig")

    try:
        from app_runtime_patch import aplicar_patches_runtime
        fonte = aplicar_patches_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] complementos do app: {exc}")

    try:
        from app_sync_status_patch import aplicar_sync_status_runtime
        fonte = aplicar_sync_status_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] status de sincronizacao: {exc}")

    try:
        from app_scroll_patch import aplicar_scrollbars_runtime
        fonte = aplicar_scrollbars_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] barras de rolagem: {exc}")

    globais = {
        "__name__": "__main__",
        "__file__": str(MAIN_FILE),
        "__package__": None,
        "__cached__": None,
    }
    codigo = compile(fonte, str(MAIN_FILE), "exec")
    eval(codigo, globais)
