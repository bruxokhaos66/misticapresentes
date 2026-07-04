from pathlib import Path
import sys

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

UPDATE_DIR = None
try:
    from auto_updater import desativar_atualizacao_com_erro, preparar_atualizacao
    UPDATE_DIR = preparar_atualizacao()
except Exception as exc:
    print(f"[Aviso] atualizador automatico: {exc}")


def executar_app(app_dir: Path) -> None:
    main_file = app_dir / "mistica_presentes.py"
    if not main_file.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {main_file}")
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    fonte = main_file.read_text(encoding="utf-8-sig")

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
        "__file__": str(main_file),
        "__package__": None,
        "__cached__": None,
    }
    codigo = compile(fonte, str(main_file), "exec")
    eval(codigo, globais)


if __name__ == "__main__":
    app_dir = Path(UPDATE_DIR) if UPDATE_DIR else BASE_DIR
    try:
        executar_app(app_dir)
    except Exception as exc:
        if UPDATE_DIR:
            try:
                desativar_atualizacao_com_erro(str(exc))
            except Exception:
                pass
            executar_app(BASE_DIR)
        else:
            raise


