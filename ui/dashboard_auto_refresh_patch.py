import customtkinter as ctk


_DASHBOARD_REFRESH_MS = 30_000


def _remover_botao_recarregar_dashboard(app):
    try:
        if not hasattr(app, "tab_d"):
            return
        pilha = list(app.tab_d.winfo_children())
        while pilha:
            widget = pilha.pop()
            try:
                texto = str(widget.cget("text") or "").strip().upper()
            except Exception:
                texto = ""
            if texto == "RECARREGAR INFORMACOES DO PAINEL" or texto == "RECARREGAR INFORMAÇÕES DO PAINEL":
                try:
                    widget.destroy()
                except Exception:
                    pass
                continue
            try:
                pilha.extend(list(widget.winfo_children()))
            except Exception:
                pass
    except Exception:
        pass


def _agendar_auto_refresh_dashboard(app):
    try:
        if getattr(app, "_dashboard_auto_refresh_after_id", None):
            try:
                app.after_cancel(app._dashboard_auto_refresh_after_id)
            except Exception:
                pass
        app._dashboard_auto_refresh_after_id = app.after(_DASHBOARD_REFRESH_MS, lambda: _auto_refresh_dashboard(app))
    except Exception:
        pass


def _auto_refresh_dashboard(app):
    try:
        if not getattr(app, "current_user", None):
            return
        aba_atual = ""
        try:
            aba_atual = app.tabs.get() if hasattr(app, "tabs") else ""
        except Exception:
            aba_atual = ""
        if aba_atual == "Dashboard" and hasattr(app, "montar_dashboard"):
            app.montar_dashboard()
            _remover_botao_recarregar_dashboard(app)
        _agendar_auto_refresh_dashboard(app)
    except Exception:
        _agendar_auto_refresh_dashboard(app)


def patch_dashboard_auto_refresh(MisticaApp):
    if getattr(MisticaApp, "_dashboard_auto_refresh_patch_installed", False):
        return MisticaApp

    original_montar_dashboard = MisticaApp.montar_dashboard
    original_montar_abas = MisticaApp.montar_abas
    original_logout = getattr(MisticaApp, "logout", None)
    original_encerrar = getattr(MisticaApp, "encerrar_sistema", None)

    def montar_dashboard_sem_botao(self, *args, **kwargs):
        retorno = original_montar_dashboard(self, *args, **kwargs)
        _remover_botao_recarregar_dashboard(self)
        _agendar_auto_refresh_dashboard(self)
        return retorno

    def montar_abas_com_auto_refresh(self, *args, **kwargs):
        retorno = original_montar_abas(self, *args, **kwargs)
        _remover_botao_recarregar_dashboard(self)
        _agendar_auto_refresh_dashboard(self)
        return retorno

    def logout_cancelando_auto_refresh(self, *args, **kwargs):
        try:
            if getattr(self, "_dashboard_auto_refresh_after_id", None):
                self.after_cancel(self._dashboard_auto_refresh_after_id)
                self._dashboard_auto_refresh_after_id = None
        except Exception:
            pass
        if original_logout:
            return original_logout(self, *args, **kwargs)

    def encerrar_cancelando_auto_refresh(self, *args, **kwargs):
        try:
            if getattr(self, "_dashboard_auto_refresh_after_id", None):
                self.after_cancel(self._dashboard_auto_refresh_after_id)
                self._dashboard_auto_refresh_after_id = None
        except Exception:
            pass
        if original_encerrar:
            return original_encerrar(self, *args, **kwargs)

    MisticaApp.montar_dashboard = montar_dashboard_sem_botao
    MisticaApp.montar_abas = montar_abas_com_auto_refresh
    if original_logout:
        MisticaApp.logout = logout_cancelando_auto_refresh
    if original_encerrar:
        MisticaApp.encerrar_sistema = encerrar_cancelando_auto_refresh
    MisticaApp._dashboard_auto_refresh_patch_installed = True
    return MisticaApp
