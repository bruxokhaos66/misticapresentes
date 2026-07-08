from pathlib import Path
import sys
import threading
import queue
import time

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def mostrar_atualizador_pre_login():
    """Mostra uma janela de atualizacao antes do login e retorna o diretorio ativo."""
    try:
        import customtkinter as ctk
        from auto_updater import preparar_atualizacao
    except Exception as exc:
        print(f"[Aviso] atualizador visual indisponivel: {exc}")
        try:
            from auto_updater import preparar_atualizacao
            return preparar_atualizacao()
        except Exception:
            return None

    eventos = queue.Queue()
    resultado = {"path": None, "erro": None, "finalizado": False}

    def callback(dados):
        eventos.put(dados)

    def worker():
        try:
            resultado["path"] = preparar_atualizacao(progress_callback=callback)
        except Exception as exc:
            resultado["erro"] = str(exc)
            eventos.put({"etapa": "erro", "mensagem": f"Nao foi possivel atualizar agora: {exc}", "progresso": 1.0})
        finally:
            resultado["finalizado"] = True
            eventos.put({"etapa": "fim", "mensagem": "Abrindo Mística Presentes...", "progresso": 1.0})

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("Atualizando Mística Presentes")
    root.geometry("520x260")
    root.resizable(False, False)
    try:
        root.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    frame = ctk.CTkFrame(root, corner_radius=18, fg_color="#1a1621")
    frame.pack(fill="both", expand=True, padx=18, pady=18)

    ctk.CTkLabel(frame, text="Mística Presentes", font=("Georgia", 28, "bold"), text_color="#d8b56d").pack(pady=(22, 4))
    status_lbl = ctk.CTkLabel(frame, text="Verificando atualizações online...", font=("Arial", 14, "bold"), text_color="#f0e6d2", wraplength=440)
    status_lbl.pack(pady=(8, 14))
    barra = ctk.CTkProgressBar(frame, width=420, height=18, progress_color="#d8b56d")
    barra.pack(pady=(0, 12))
    barra.set(0.03)
    detalhe_lbl = ctk.CTkLabel(frame, text="Isso acontece antes do login para manter o programa sempre atualizado.", font=("Arial", 11), text_color="#c8bfae", wraplength=440)
    detalhe_lbl.pack(pady=(0, 8))

    threading.Thread(target=worker, daemon=True).start()
    inicio_fim = {"valor": None}

    def processar_eventos():
        try:
            while True:
                dados = eventos.get_nowait()
                msg = str(dados.get("mensagem") or "Atualizando...")
                prog = dados.get("progresso")
                status_lbl.configure(text=msg)
                if prog is not None:
                    try:
                        barra.set(max(0.0, min(1.0, float(prog))))
                    except Exception:
                        pass
                if dados.get("etapa") == "fim":
                    inicio_fim["valor"] = time.time()
        except queue.Empty:
            pass

        if resultado["finalizado"] and inicio_fim["valor"] and time.time() - inicio_fim["valor"] > 0.85:
            root.destroy()
            return
        root.after(120, processar_eventos)

    root.after(120, processar_eventos)
    root.mainloop()
    return resultado["path"]


UPDATE_DIR = mostrar_atualizador_pre_login()


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
        from app_pagamento_misto_patch import aplicar_pagamento_misto_runtime
        fonte = aplicar_pagamento_misto_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] pagamento misto: {exc}")

    try:
        from app_sync_status_patch import aplicar_sync_status_runtime
        fonte = aplicar_sync_status_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] status de sincronizacao: {exc}")

    try:
        from app_painel_guard_patch import aplicar_painel_guard_runtime
        fonte = aplicar_painel_guard_runtime(fonte)
    except Exception as exc:
        print(f"[Aviso] protecao painel mobile: {exc}")

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
                from auto_updater import desativar_atualizacao_com_erro
                desativar_atualizacao_com_erro(str(exc))
            except Exception:
                pass
            executar_app(BASE_DIR)
        else:
            raise
