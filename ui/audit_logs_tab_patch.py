import customtkinter as ctk
from tkinter import messagebox, ttk
from datetime import datetime

from services.audit_log_service import (
    listar_acoes_logs,
    listar_logs_auditoria,
    listar_usuarios_logs,
    registrar_log_auditoria,
    resumo_logs_auditoria,
)


def _montar_auditoria_logs(app):
    if not hasattr(app, "tab_audit_logs"):
        return
    for widget in app.tab_audit_logs.winfo_children():
        widget.destroy()

    root = ctk.CTkFrame(app.tab_audit_logs, fg_color="transparent")
    root.pack(fill="both", expand=True, padx=16, pady=14)

    header = ctk.CTkFrame(root, fg_color=getattr(app, "cor_vinho", "#1a1621"), corner_radius=15)
    header.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(
        header,
        text="AUDITORIA DE LOGS DO SISTEMA",
        font=("Arial", 20, "bold"),
        text_color=getattr(app, "cor_ouro", "#d8b56d"),
    ).pack(pady=(14, 4))
    ctk.CTkLabel(
        header,
        text="Consulte ações de todos os usuários, vendedores e administradores, com filtros por pessoa, ação e período.",
        font=("Arial", 13),
        wraplength=1100,
    ).pack(pady=(0, 12))

    cards = ctk.CTkFrame(root, fg_color="transparent")
    cards.pack(fill="x", pady=(0, 10))
    cards.columnconfigure((0, 1, 2), weight=1)
    lbl_total = ctk.CTkLabel(cards, text="Total logs: --", font=("Arial", 15, "bold"), text_color="#ffffff")
    lbl_usuarios = ctk.CTkLabel(cards, text="Usuários: --", font=("Arial", 15, "bold"), text_color="#ffffff")
    lbl_hoje = ctk.CTkLabel(cards, text="Hoje: --", font=("Arial", 15, "bold"), text_color="#ffffff")
    for idx, lbl in enumerate((lbl_total, lbl_usuarios, lbl_hoje)):
        card = ctk.CTkFrame(cards, fg_color=getattr(app, "cor_vinho", "#1a1621"), corner_radius=12)
        card.grid(row=0, column=idx, sticky="ew", padx=6)
        lbl.pack(in_=card, pady=12)

    filtros = ctk.CTkFrame(root, fg_color=getattr(app, "cor_vinho", "#1a1621"), corner_radius=14)
    filtros.pack(fill="x", pady=(0, 10))

    usuarios = ["Todos"]
    acoes = ["Todas"]
    try:
        usuarios += listar_usuarios_logs(app.current_user)
        acoes += listar_acoes_logs(app.current_user)
    except Exception:
        pass

    ctk.CTkLabel(filtros, text="Usuário", font=("Arial", 12, "bold"), text_color=getattr(app, "cor_ouro", "#d8b56d")).grid(row=0, column=0, padx=8, pady=(10, 2), sticky="w")
    cb_usuario = ctk.CTkComboBox(filtros, values=usuarios, width=190)
    cb_usuario.set("Todos")
    cb_usuario.grid(row=1, column=0, padx=8, pady=(0, 10), sticky="ew")

    ctk.CTkLabel(filtros, text="Ação", font=("Arial", 12, "bold"), text_color=getattr(app, "cor_ouro", "#d8b56d")).grid(row=0, column=1, padx=8, pady=(10, 2), sticky="w")
    cb_acao = ctk.CTkComboBox(filtros, values=acoes, width=230)
    cb_acao.set("Todas")
    cb_acao.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="ew")

    hoje = datetime.now()
    ctk.CTkLabel(filtros, text="Mês", font=("Arial", 12, "bold"), text_color=getattr(app, "cor_ouro", "#d8b56d")).grid(row=0, column=2, padx=8, pady=(10, 2), sticky="w")
    ent_mes = ctk.CTkEntry(filtros, width=70)
    ent_mes.insert(0, f"{hoje.month:02d}")
    ent_mes.grid(row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

    ctk.CTkLabel(filtros, text="Ano", font=("Arial", 12, "bold"), text_color=getattr(app, "cor_ouro", "#d8b56d")).grid(row=0, column=3, padx=8, pady=(10, 2), sticky="w")
    ent_ano = ctk.CTkEntry(filtros, width=90)
    ent_ano.insert(0, str(hoje.year))
    ent_ano.grid(row=1, column=3, padx=8, pady=(0, 10), sticky="ew")

    ctk.CTkLabel(filtros, text="Busca livre", font=("Arial", 12, "bold"), text_color=getattr(app, "cor_ouro", "#d8b56d")).grid(row=0, column=4, padx=8, pady=(10, 2), sticky="w")
    ent_busca = ctk.CTkEntry(filtros, placeholder_text="Usuário, ação, detalhe ou data")
    ent_busca.grid(row=1, column=4, padx=8, pady=(0, 10), sticky="ew")
    filtros.columnconfigure(4, weight=1)

    tabela_frame = ctk.CTkFrame(root, fg_color="#18121f", corner_radius=12)
    tabela_frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        tabela_frame,
        columns=("usuario", "acao", "detalhes", "data"),
        show="headings",
        selectmode="extended",
        height=18,
    )
    vsb = ttk.Scrollbar(tabela_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(tabela_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.heading("usuario", text="Usuário")
    tree.heading("acao", text="Ação")
    tree.heading("detalhes", text="Detalhes")
    tree.heading("data", text="Data/Hora")
    tree.column("usuario", width=170)
    tree.column("acao", width=220)
    tree.column("detalhes", width=720)
    tree.column("data", width=160, anchor="center")
    tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
    vsb.grid(row=0, column=1, sticky="ns", pady=(10, 0), padx=(0, 10))
    hsb.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
    tabela_frame.rowconfigure(0, weight=1)
    tabela_frame.columnconfigure(0, weight=1)

    def carregar():
        for item in tree.get_children():
            tree.delete(item)
        try:
            mes = ent_mes.get().strip() or None
            ano = ent_ano.get().strip() or None
            dados = resumo_logs_auditoria(app.current_user, mes, ano)
            lbl_total.configure(text=f"Total logs: {dados['total']}")
            lbl_usuarios.configure(text=f"Usuários: {dados['usuarios']}")
            lbl_hoje.configure(text=f"Hoje: {dados['hoje']}")
            rows = listar_logs_auditoria(
                app.current_user,
                termo=ent_busca.get().strip(),
                usuario_filtro=cb_usuario.get(),
                acao_filtro=cb_acao.get(),
                mes=mes,
                ano=ano,
                limite=800,
            )
            for r in rows:
                tree.insert("", "end", values=r)
        except Exception as exc:
            messagebox.showerror("Auditoria Logs", f"Erro ao carregar logs: {exc}")

    def limpar_filtros():
        cb_usuario.set("Todos")
        cb_acao.set("Todas")
        ent_busca.delete(0, "end")
        ent_mes.delete(0, "end")
        ent_mes.insert(0, f"{hoje.month:02d}")
        ent_ano.delete(0, "end")
        ent_ano.insert(0, str(hoje.year))
        carregar()

    botoes = ctk.CTkFrame(root, fg_color="transparent")
    botoes.pack(fill="x", pady=10)
    ctk.CTkButton(botoes, text="CARREGAR LOGS", height=38, fg_color="#3c7bb9", command=carregar).pack(side="left", padx=5)
    ctk.CTkButton(botoes, text="LIMPAR FILTROS", height=38, fg_color="#5c5c5c", command=limpar_filtros).pack(side="left", padx=5)
    ctk.CTkButton(botoes, text="SELECIONAR TODOS", height=38, fg_color="#5c5c5c", command=lambda: tree.selection_set(tree.get_children())).pack(side="right", padx=5)

    try:
        registrar_log_auditoria(app.current_user.get("nome"), "Auditoria", "Aba Auditoria Logs aberta")
    except Exception:
        pass
    carregar()


def patch_audit_logs_tab(MisticaApp):
    if getattr(MisticaApp, "_audit_logs_tab_patch_installed", False):
        return MisticaApp

    original_montar_abas = MisticaApp.montar_abas

    def montar_abas_com_auditoria(self, *args, **kwargs):
        original_montar_abas(self, *args, **kwargs)
        if not self.current_user or self.current_user.get("perfil") != "adm":
            return
        try:
            self.tab_audit_logs = self.tabs.add("Auditoria Logs")
            self.executar_montagem_segura("tab_audit_logs", lambda: _montar_auditoria_logs(self))
        except Exception as exc:
            messagebox.showerror("Auditoria Logs", f"Erro ao montar aba de auditoria: {exc}")

    MisticaApp.montar_abas = montar_abas_com_auditoria
    MisticaApp._audit_logs_tab_patch_installed = True
    return MisticaApp
