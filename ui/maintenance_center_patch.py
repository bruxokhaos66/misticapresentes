import customtkinter as ctk
from tkinter import messagebox, ttk
from datetime import datetime

from services.period_maintenance_service import (
    listar_lancamentos_caixa_periodo,
    listar_vendas_periodo,
    zerar_vendas_e_caixa_periodo,
)
from database import query_db


def _fmt_moeda(valor):
    try:
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(valor)


def _periodo_widgets(parent):
    box = ctk.CTkFrame(parent, fg_color="#18121f", corner_radius=12)
    box.pack(fill="x", padx=12, pady=10)
    tipo = ctk.CTkOptionMenu(box, values=["dia", "mes"], width=110)
    tipo.set("dia")
    dia = ctk.CTkEntry(box, placeholder_text="Dia", width=70)
    mes = ctk.CTkEntry(box, placeholder_text="Mês", width=70)
    ano = ctk.CTkEntry(box, placeholder_text="Ano", width=90)
    hoje = datetime.now()
    dia.insert(0, f"{hoje.day:02d}")
    mes.insert(0, f"{hoje.month:02d}")
    ano.insert(0, str(hoje.year))
    ctk.CTkLabel(box, text="Período", font=("Arial", 13, "bold"), text_color="#d8b56d").pack(side="left", padx=(12, 6), pady=12)
    tipo.pack(side="left", padx=5, pady=12)
    dia.pack(side="left", padx=5, pady=12)
    mes.pack(side="left", padx=5, pady=12)
    ano.pack(side="left", padx=5, pady=12)
    return tipo, dia, mes, ano


def _valores_periodo(tipo, dia, mes, ano):
    return tipo.get(), dia.get().strip() or None, mes.get().strip() or None, ano.get().strip() or None


def _criar_tree(parent, columns, headings, widths):
    frame = ctk.CTkFrame(parent, fg_color="#18121f", corner_radius=10)
    frame.pack(fill="both", expand=True, padx=12, pady=8)
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", height=12)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    for c, h, w in zip(columns, headings, widths):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor="center" if w <= 120 else "w")
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return tree


def abrir_central_manutencao(app):
    if not app.current_user or app.current_user.get("perfil") != "adm":
        messagebox.showerror("Acesso negado", "Apenas perfil adm pode acessar a Central de Manutenção.")
        return

    win = ctk.CTkToplevel(app)
    win.title("Central de Manutenção - Mística Presentes")
    win.geometry("1120x720")
    win.grab_set()

    header = ctk.CTkFrame(win, fg_color="#1a1621", corner_radius=14)
    header.pack(fill="x", padx=14, pady=12)
    ctk.CTkLabel(header, text="CENTRAL DE MANUTENÇÃO", font=("Arial", 22, "bold"), text_color="#d8b56d").pack(pady=(14, 4))
    ctk.CTkLabel(header, text="Ferramentas administrativas com filtro por dia, mês e ano. Ações críticas geram backup e log.", font=("Arial", 13), wraplength=980).pack(pady=(0, 14))

    tabs = ctk.CTkTabview(win)
    tabs.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    tab_periodo = tabs.add("Vendas e Caixa por Período")
    tab_logs = tabs.add("Auditoria / Logs")

    tipo, dia, mes, ano = _periodo_widgets(tab_periodo)
    resumo_lbl = ctk.CTkLabel(tab_periodo, text="Selecione o período e clique em Carregar.", font=("Arial", 14, "bold"), text_color="#f0e6d2")
    resumo_lbl.pack(fill="x", padx=12, pady=(0, 6))

    grid = ctk.CTkFrame(tab_periodo, fg_color="transparent")
    grid.pack(fill="both", expand=True, padx=4, pady=4)
    grid.columnconfigure((0, 1), weight=1)
    grid.rowconfigure(0, weight=1)

    box_vendas = ctk.CTkFrame(grid, fg_color="#120d19", corner_radius=12)
    box_vendas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
    ctk.CTkLabel(box_vendas, text="VENDAS DO PERÍODO", font=("Arial", 14, "bold"), text_color="#d8b56d").pack(pady=8)
    tree_vendas = _criar_tree(box_vendas, ("id", "data", "cliente", "total", "pag", "status"), ("ID", "Data", "Cliente", "Total", "Pag.", "Status"), (60, 135, 180, 100, 100, 100))

    box_caixa = ctk.CTkFrame(grid, fg_color="#120d19", corner_radius=12)
    box_caixa.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
    ctk.CTkLabel(box_caixa, text="LANÇAMENTOS DO CAIXA", font=("Arial", 14, "bold"), text_color="#d8b56d").pack(pady=8)
    tree_caixa = _criar_tree(box_caixa, ("id", "tipo", "desc", "valor", "data", "caixa"), ("ID", "Tipo", "Descrição", "Valor", "Data", "Caixa"), (60, 75, 230, 100, 135, 70))

    def carregar_periodo():
        for t in (tree_vendas, tree_caixa):
            for item in t.get_children():
                t.delete(item)
        try:
            tp, d, m, a = _valores_periodo(tipo, dia, mes, ano)
            vendas = listar_vendas_periodo(app.current_user, tp, d, m, a)
            caixa = listar_lancamentos_caixa_periodo(app.current_user, tp, d, m, a)
            for v in vendas["vendas"]:
                tree_vendas.insert("", "end", values=(v[0], v[1], v[2], _fmt_moeda(v[3]), v[4], v[6]))
            for c in caixa["lancamentos"]:
                tree_caixa.insert("", "end", values=(c[0], c[1], c[2], _fmt_moeda(c[3]), c[4], c[5]))
            resumo_lbl.configure(text=f"Período {vendas['periodo']} | Vendas ativas: {_fmt_moeda(vendas['total_ativas'])} | Caixa listado: {_fmt_moeda(caixa['total'])}")
        except Exception as exc:
            messagebox.showerror("Central de Manutenção", f"Erro ao carregar período: {exc}")

    def zerar_periodo():
        tp, d, m, a = _valores_periodo(tipo, dia, mes, ano)
        alvo = f"{d or '--'}/{m or '--'}/{a or '--'}" if tp == "dia" else f"{m or '--'}/{a or '--'}"
        aviso = (
            f"Você vai ZERAR o período {alvo}.\n\n"
            "Isso irá:\n"
            "- cancelar vendas do período para saírem do Dashboard;\n"
            "- remover lançamentos do caixa dentro do período;\n"
            "- criar backup antes;\n"
            "- registrar log com seu usuário.\n\n"
            "Produtos e estoque não serão apagados. Confirmar?"
        )
        if not messagebox.askyesno("Confirmar zerar período", aviso):
            return
        if not messagebox.askyesno("Confirmação final", "Esta ação altera vendas e caixa do período. Deseja realmente continuar?"):
            return
        try:
            res = zerar_vendas_e_caixa_periodo(app.current_user, tp, d, m, a, "Zerar período pela Central de Manutenção")
            messagebox.showinfo("Período zerado", res.get("mensagem", "Período zerado."))
            carregar_periodo()
            try:
                if hasattr(app, "montar_dashboard"):
                    app.montar_dashboard()
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Central de Manutenção", f"Erro ao zerar período: {exc}")

    botoes = ctk.CTkFrame(tab_periodo, fg_color="transparent")
    botoes.pack(fill="x", padx=12, pady=8)
    ctk.CTkButton(botoes, text="CARREGAR PERÍODO", height=40, fg_color="#3c7bb9", command=carregar_periodo).pack(side="left", padx=5)
    ctk.CTkButton(botoes, text="ZERAR VENDAS E CAIXA DO PERÍODO", height=40, fg_color="#8a4c4c", command=zerar_periodo).pack(side="right", padx=5)

    # Logs com barras de rolagem
    log_bar = ctk.CTkFrame(tab_logs, fg_color="#18121f", corner_radius=12)
    log_bar.pack(fill="x", padx=12, pady=10)
    ctk.CTkLabel(log_bar, text="Auditoria administrativa", font=("Arial", 14, "bold"), text_color="#d8b56d").pack(side="left", padx=12, pady=10)
    tree_logs = _criar_tree(tab_logs, ("usuario", "acao", "detalhes", "data"), ("Usuário", "Ação", "Detalhes", "Data/Hora"), (150, 220, 560, 150))

    def carregar_logs():
        for item in tree_logs.get_children():
            tree_logs.delete(item)
        try:
            rows = query_db("SELECT usuario, acao, detalhes, data_hora FROM logs ORDER BY id DESC LIMIT 300")
            for r in rows:
                tree_logs.insert("", "end", values=r)
        except Exception as exc:
            messagebox.showerror("Logs", f"Erro ao carregar logs: {exc}")

    ctk.CTkButton(log_bar, text="RECARREGAR LOGS", height=34, command=carregar_logs).pack(side="right", padx=12, pady=10)
    carregar_periodo()
    carregar_logs()


def patch_maintenance_center(MisticaApp):
    if getattr(MisticaApp, "_maintenance_center_patch_installed", False):
        return MisticaApp

    original_montar_administracao = MisticaApp.montar_administracao

    def montar_administracao_com_central(self, *args, **kwargs):
        original_montar_administracao(self, *args, **kwargs)
        if not self.current_user or self.current_user.get("perfil") != "adm":
            return
        try:
            painel = ctk.CTkFrame(self.tab_adm, fg_color="#18121f", corner_radius=15)
            filhos = list(self.tab_adm.winfo_children())
            if filhos:
                painel.pack(fill="x", padx=20, pady=(8, 8), before=filhos[0])
            else:
                painel.pack(fill="x", padx=20, pady=(8, 8))
            painel.columnconfigure(0, weight=1)
            ctk.CTkButton(
                painel,
                text="ABRIR CENTRAL DE MANUTENÇÃO ORGANIZADA",
                height=46,
                fg_color="#b98a3c",
                font=("Arial", 15, "bold"),
                command=lambda: abrir_central_manutencao(self),
            ).grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        except Exception:
            pass

    MisticaApp.montar_administracao = montar_administracao_com_central
    MisticaApp._maintenance_center_patch_installed = True
    return MisticaApp
