import customtkinter as ctk
from tkinter import ttk


def _texto_widget(widget):
    try:
        return str(widget.cget("text") or "")
    except Exception:
        return ""


def _remover_bloco_auditoria_antigo(container):
    """Remove o bloco antigo AUDITORIA (LOGS) da aba Administração.

    O bloco novo fica na aba dedicada Auditoria Logs.
    """
    try:
        filhos = list(container.winfo_children())
    except Exception:
        return False

    for idx, child in enumerate(filhos):
        texto = _texto_widget(child).strip().upper()
        if texto == "AUDITORIA (LOGS)":
            for w in filhos[idx:]:
                try:
                    w.destroy()
                except Exception:
                    pass
            return True

    for child in filhos:
        if _remover_bloco_auditoria_antigo(child):
            return True
    return False


def patch_admin_audit_cleanup(MisticaApp):
    if getattr(MisticaApp, "_admin_audit_cleanup_patch_installed", False):
        return MisticaApp

    original_montar_administracao = MisticaApp.montar_administracao
    original_refresh_audit = getattr(MisticaApp, "refresh_audit", None)

    def montar_administracao_sem_logs_antigos(self, *args, **kwargs):
        original_montar_administracao(self, *args, **kwargs)
        try:
            if hasattr(self, "tab_adm"):
                _remover_bloco_auditoria_antigo(self.tab_adm)
        except Exception:
            pass

    def refresh_audit_seguro(self, *args, **kwargs):
        """Compatibilidade: logs agora ficam na aba Auditoria Logs."""
        try:
            tree = getattr(self, "tree_logs", None)
            if tree is None or not isinstance(tree, ttk.Treeview) or not tree.winfo_exists():
                return
            if original_refresh_audit:
                return original_refresh_audit(self, *args, **kwargs)
        except Exception:
            return

    MisticaApp.montar_administracao = montar_administracao_sem_logs_antigos
    MisticaApp.refresh_audit = refresh_audit_seguro
    MisticaApp._admin_audit_cleanup_patch_installed = True
    return MisticaApp
