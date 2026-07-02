from tkinter import messagebox


def _forcar_recarregar_dashboard(app):
    """Limpa e remonta a aba Dashboard imediatamente."""
    try:
        if hasattr(app, "tab_d") and app.tab_d is not None:
            for widget in app.tab_d.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
        if hasattr(app, "montar_dashboard"):
            app.montar_dashboard()
        if hasattr(app, "tabs"):
            try:
                app.tabs.set("Dashboard")
            except Exception:
                pass
        try:
            app.update_idletasks()
            app.update()
        except Exception:
            pass
        return True
    except Exception as exc:
        messagebox.showerror("Dashboard", f"Não consegui recarregar o Dashboard: {exc}")
        return False


def patch_dashboard_runtime(MisticaApp):
    """Complementa o patch da manutenção para o Dashboard zerar/recarregar na hora."""
    if getattr(MisticaApp, "_dashboard_runtime_patch_installed", False):
        return MisticaApp

    try:
        import ui.admin_maintenance_patch as admin_patch

        original_executar = admin_patch._executar_manutencao

        def executar_manutencao_com_dashboard(app, titulo, funcao):
            if str(titulo or "").lower().startswith("dashboard"):
                try:
                    resultado = funcao()
                    _forcar_recarregar_dashboard(app)
                    admin_patch._mostrar_resultado(app, titulo, resultado)
                except admin_patch.PermissaoNegada as exc:
                    messagebox.showerror("Acesso negado", str(exc))
                except Exception as exc:
                    messagebox.showerror(titulo, f"Erro ao executar manutenção: {exc}")
                return
            return original_executar(app, titulo, funcao)

        admin_patch._executar_manutencao = executar_manutencao_com_dashboard
    except Exception:
        pass

    def issis_admin_zerar_dashboard(self):
        if not self.current_user or self.current_user.get("perfil") != "adm":
            return "Apenas perfil adm pode reiniciar o Dashboard."
        try:
            from services.maintenance_service import reiniciar_dashboard

            reiniciar_dashboard(self.current_user)
            _forcar_recarregar_dashboard(self)
            return "Dashboard reiniciado e recarregado na tela. Nenhum dado real foi apagado."
        except Exception as exc:
            return f"Não consegui reiniciar o Dashboard. Detalhe: {exc}"

    MisticaApp.issis_admin_zerar_dashboard = issis_admin_zerar_dashboard
    MisticaApp._dashboard_runtime_patch_installed = True
    return MisticaApp
