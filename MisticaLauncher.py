from pathlib import Path
import queue
import sys
import threading
import time

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def janela_atualizacao_launcher():
    try:
        import customtkinter as ctk
        from auto_updater import preparar_atualizacao, detectar_windows
    except Exception as exc:
        print(f"[Launcher] Atualizador visual indisponivel: {exc}")
        try:
            from auto_updater import preparar_atualizacao
            return preparar_atualizacao()
        except Exception:
            return None

    ambiente = detectar_windows()
    eventos = queue.Queue()
    resultado = {"path": None, "erro": None, "finalizado": False}

    def callback(dados):
        eventos.put(dados)

    def worker():
        try:
            resultado["path"] = preparar_atualizacao(progress_callback=callback)
        except Exception as exc:
            resultado["erro"] = str(exc)
            eventos.put({"etapa": "erro", "mensagem": f"Atualizacao indisponivel: {exc}", "progresso": 1.0})
        finally:
            resultado["finalizado"] = True
            eventos.put({"etapa": "fim", "mensagem": "Abrindo sistema da Mística Presentes...", "progresso": 1.0})

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.title("Mística Presentes - Atualizador")
    root.geometry("590x325")
    root.resizable(False, False)
    try:
        root.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    frame = ctk.CTkFrame(root, corner_radius=22, fg_color="#17131d")
    frame.pack(fill="both", expand=True, padx=18, pady=18)

    ctk.CTkLabel(frame, text="☾ Mística Presentes", font=("Georgia", 30, "bold"), text_color="#f0c56a").pack(pady=(20, 4))
    ctk.CTkLabel(frame, text="Atualizador online inteligente", font=("Arial", 13, "bold"), text_color="#b8c977").pack(pady=(0, 6))

    ambiente_txt = f"Detectado: {ambiente['nome']} • {ambiente['bits']} bits • Canal: {ambiente['canal']}"
    ambiente_lbl = ctk.CTkLabel(frame, text=ambiente_txt, font=("Arial", 11, "bold"), text_color="#d8cbb6", wraplength=500)
    ambiente_lbl.pack(pady=(0, 8))

    status = ctk.CTkLabel(frame, text="Verificando atualizações antes do login...", font=("Arial", 14, "bold"), text_color="#efe1c5", wraplength=500)
    status.pack(pady=(8, 14))

    barra = ctk.CTkProgressBar(frame, width=460, height=18, progress_color="#f0c56a")
    barra.pack(pady=(0, 12))
    barra.set(0.04)

    detalhe = ctk.CTkLabel(frame, text="O launcher escolhe automaticamente a versão correta para este Windows.", font=("Arial", 11), text_color="#c8bfae", wraplength=500)
    detalhe.pack(pady=(0, 8))

    threading.Thread(target=worker, daemon=True).start()
    tempo_fim = {"valor": None}

    def processar():
        try:
            while True:
                dados = eventos.get_nowait()
                status.configure(text=str(dados.get("mensagem") or "Atualizando..."))
                amb = dados.get("ambiente") or ambiente
                ambiente_lbl.configure(text=f"Detectado: {amb['nome']} • {amb['bits']} bits • Canal: {amb['canal']}")
                prog = dados.get("progresso")
                if prog is not None:
                    try:
                        barra.set(max(0.0, min(1.0, float(prog))))
                    except Exception:
                        pass
                if dados.get("etapa") == "download":
                    total = int(dados.get("total") or 0)
                    baixado = int(dados.get("baixado") or 0)
                    if total > 0:
                        detalhe.configure(text=f"Download: {baixado // 1024} KB de {total // 1024} KB")
                if dados.get("etapa") == "fim":
                    tempo_fim["valor"] = time.time()
        except queue.Empty:
            pass

        if resultado["finalizado"] and tempo_fim["valor"] and time.time() - tempo_fim["valor"] > 0.8:
            root.destroy()
            return
        root.after(110, processar)

    root.after(110, processar)
    root.mainloop()
    return resultado["path"]


def executar_sistema(app_dir: Path | None):
    if app_dir and app_dir.exists():
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        main_file = app_dir / "mistica_presentes.py"
    else:
        main_file = BASE_DIR / "mistica_presentes.py"

    if not main_file.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {main_file}")

    fonte = main_file.read_text(encoding="utf-8-sig")

    for modulo, funcao in [
        ("app_runtime_patch", "aplicar_patches_runtime"),
        ("app_pagamento_misto_patch", "aplicar_pagamento_misto_runtime"),
        ("app_sync_status_patch", "aplicar_sync_status_runtime"),
        ("app_painel_guard_patch", "aplicar_painel_guard_runtime"),
        ("app_scroll_patch", "aplicar_scrollbars_runtime"),
    ]:
        try:
            mod = __import__(modulo, fromlist=[funcao])
            fonte = getattr(mod, funcao)(fonte)
        except Exception as exc:
            print(f"[Launcher] Patch {modulo}: {exc}")

    globais = {
        "__name__": "__main__",
        "__file__": str(main_file),
        "__package__": None,
        "__cached__": None,
    }
    codigo = compile(fonte, str(main_file), "exec")
    eval(codigo, globais)


if __name__ == "__main__":
    update_dir = janela_atualizacao_launcher()
    try:
        executar_sistema(Path(update_dir) if update_dir else None)
    except Exception as exc:
        if update_dir:
            try:
                from auto_updater import desativar_atualizacao_com_erro
                desativar_atualizacao_com_erro(str(exc))
            except Exception:
                pass
            executar_sistema(None)
        else:
            raise
