import customtkinter as ctk
from tkinter import messagebox, ttk

from services.maintenance_service import (
    PermissaoNegada,
    apagar_lancamento_caixa,
    diagnosticar_caixa,
    diagnosticar_estoque,
    diagnosticar_financeiro,
    listar_lancamentos_caixa_para_manutencao,
    reiniciar_area_segura,
    reiniciar_dashboard,
)


def _formatar_resultado(dados):
    if isinstance(dados, dict):
        linhas = []
        for chave, valor in dados.items():
            if chave in {"ultimos_caixas", "produtos_baixos", "produtos_negativos", "diagnostico_geral", "caixa", "estoque", "financeiro"}:
                continue
            linhas.append(f"{chave}: {valor}")
        problemas = dados.get("problemas") or []
        if problemas:
            linhas.append("\nProblemas encontrados:")
            linhas.extend(f"- {p}" for p in problemas)
        return "\n".join(linhas) or str(dados)
    return str(dados)


def _mostrar_resultado(app, titulo, dados):
    texto = _formatar_resultado(dados)
    messagebox.showinfo(titulo, texto)
    try:
        if hasattr(app, "refresh_audit"):
            app.refresh_audit(filtrar=False)
    except Exception:
        pass


def _executar_manutencao(app, titulo, funcao):
    try:
        resultado = funcao()
        _mostrar_resultado(app, titulo, resultado)
        if titulo.lower().startswith("dashboard") and hasattr(app, "montar_dashboard"):
            app.montar_dashboard()
    except PermissaoNegada as exc:
        messagebox.showerror("Acesso negado", str(exc))
    except Exception as exc:
        messagebox.showerror(titulo, f"Erro ao executar manutenção: {exc}")


def _janela_apagar_lancamento_caixa(app):
    if not app.current_user or app.current_user.get("perfil") != "adm":
        messagebox.showerror("Acesso negado", "Apenas perfil adm pode apagar lançamento do caixa.")
        return

    win = ctk.CTkToplevel(app)
    win.title("Manutenção do Caixa")
    win.geometry("920x560")
    win.grab_set()

    topo = ctk.CTkFrame(win, fg_color=getattr(app, "cor_vinho", "#1a1621"), corner_radius=12)
    topo.pack(fill="x", padx=14, pady=12)
    ctk.CTkLabel(
        topo,
        text="APAGAR LANÇAMENTO DO CAIXA",
        font=getattr(app, "font_label", ("Arial", 14, "bold")),
        text_color=getattr(app, "cor_ouro", "#d8b56d"),
    ).pack(pady=(12, 4))
    ctk.CTkLabel(
        topo,
        text="Use somente para correção administrativa. O sistema cria backup e registra log com o usuário.",
        font=getattr(app, "font_input", ("Arial", 13)),
        wraplength=820,
    ).pack(pady=(0, 12))

    tree = ttk.Treeview(win, columns=("id", "tipo", "descricao", "valor", "data", "caixa", "forma"), show="headings", height=13)
    for col, titulo in zip(("id", "tipo", "descricao", "valor", "data", "caixa", "forma"), ("ID", "Tipo", "Descrição", "Valor", "Data", "Caixa", "Forma")):
        tree.heading(col, text=titulo)
    tree.column("id", width=60, anchor="center")
    tree.column("tipo", width=80, anchor="center")
    tree.column("descricao", width=330)
    tree.column("valor", width=90, anchor="center")
    tree.column("data", width=130, anchor="center")
    tree.column("caixa", width=70, anchor="center")
    tree.column("forma", width=100, anchor="center")
    tree.pack(fill="both", expand=True, padx=14, pady=8)

    motivo = ctk.CTkEntry(win, placeholder_text="Motivo da exclusão/correção", height=38, font=getattr(app, "font_input", ("Arial", 13)))
    motivo.pack(fill="x", padx=14, pady=6)

    def carregar():
        for item in tree.get_children():
            tree.delete(item)
        try:
            for row in listar_lancamentos_caixa_para_manutencao(app.current_user):
                valor = row[3]
                try:
                    valor_txt = app.format_moeda(valor) if hasattr(app, "format_moeda") else f"R$ {float(valor):.2f}"
                except Exception:
                    valor_txt = str(valor)
                tree.insert("", "end", values=(row[0], row[1], row[2], valor_txt, row[4], row[5], row[6] or ""))
        except Exception as exc:
            messagebox.showerror("Caixa", f"Erro ao listar lançamentos: {exc}")

    def apagar():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Caixa", "Selecione um lançamento para apagar.")
            return
        valores = tree.item(sel[0], "values")
        fluxo_id = valores[0]
        desc = valores[2]
        val = valores[3]
        motivo_txt = motivo.get().strip() or "Correção administrativa"
        aviso = (
            f"Você vai apagar o lançamento ID {fluxo_id}.\n\n"
            f"Descrição: {desc}\n"
            f"Valor: {val}\n"
            f"Motivo: {motivo_txt}\n\n"
            "Antes de apagar, o sistema fará backup e registrará log com seu usuário.\n"
            "Confirmar?"
        )
        if not messagebox.askyesno("Confirmar exclusão do caixa", aviso):
            return
        if not messagebox.askyesno("Confirmação final", "Esta ação altera o fluxo do caixa. Deseja realmente continuar?"):
            return
        try:
            resultado = apagar_lancamento_caixa(app.current_user, fluxo_id, motivo_txt)
            messagebox.showinfo("Caixa", resultado.get("mensagem", "Lançamento apagado."))
            carregar()
            try:
                if hasattr(app, "refresh_audit"):
                    app.refresh_audit(filtrar=False)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Caixa", f"Erro ao apagar lançamento: {exc}")

    botoes = ctk.CTkFrame(win, fg_color="transparent")
    botoes.pack(fill="x", padx=14, pady=10)
    ctk.CTkButton(botoes, text="RECARREGAR", height=38, command=carregar).pack(side="left", padx=4)
    ctk.CTkButton(botoes, text="APAGAR LANÇAMENTO SELECIONADO", height=38, fg_color="#7f4c4c", command=apagar).pack(side="right", padx=4)

    carregar()


def patch_mistica_app(MisticaApp):
    if getattr(MisticaApp, "_maintenance_patch_installed", False):
        return MisticaApp

    original_montar_administracao = MisticaApp.montar_administracao

    def montar_administracao_com_manutencao(self, *args, **kwargs):
        original_montar_administracao(self, *args, **kwargs)
        if not self.current_user or self.current_user.get("perfil") != "adm":
            return

        painel = ctk.CTkFrame(self.tab_adm, fg_color=getattr(self, "cor_vinho", "#1a1621"), corner_radius=15)
        painel.pack(fill="x", padx=20, pady=(0, 14), ipady=10)
        painel.columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            painel,
            text="MANUTENÇÃO SEGURA DO SISTEMA",
            font=getattr(self, "font_label", ("Arial", 14, "bold")),
            text_color=getattr(self, "cor_ouro", "#d8b56d"),
        ).grid(row=0, column=0, columnspan=3, pady=(10, 8))

        ctk.CTkButton(
            painel,
            text="REINICIAR DASHBOARD",
            height=38,
            fg_color="#3c7bb9",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _executar_manutencao(self, "Dashboard", lambda: reiniciar_dashboard(self.current_user)),
        ).grid(row=1, column=0, padx=8, pady=5, sticky="ew")

        ctk.CTkButton(
            painel,
            text="DIAGNOSTICAR CAIXA",
            height=38,
            fg_color="#b98a3c",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _executar_manutencao(self, "Caixa", lambda: diagnosticar_caixa(self.current_user)),
        ).grid(row=1, column=1, padx=8, pady=5, sticky="ew")

        ctk.CTkButton(
            painel,
            text="DIAGNOSTICAR ESTOQUE",
            height=38,
            fg_color="#5f7f4c",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _executar_manutencao(self, "Estoque", lambda: diagnosticar_estoque(self.current_user)),
        ).grid(row=1, column=2, padx=8, pady=5, sticky="ew")

        ctk.CTkButton(
            painel,
            text="DIAGNOSTICAR FINANCEIRO",
            height=38,
            fg_color="#7c3cb9",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _executar_manutencao(self, "Financeiro", lambda: diagnosticar_financeiro(self.current_user)),
        ).grid(row=2, column=0, padx=8, pady=5, sticky="ew")

        ctk.CTkButton(
            painel,
            text="DIAGNÓSTICO GERAL + BACKUP",
            height=38,
            fg_color="#5c5c5c",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _executar_manutencao(self, "Geral", lambda: reiniciar_area_segura("geral", self.current_user)),
        ).grid(row=2, column=1, padx=8, pady=5, sticky="ew")

        ctk.CTkButton(
            painel,
            text="APAGAR LANÇAMENTO DO CAIXA",
            height=38,
            fg_color="#7f4c4c",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _janela_apagar_lancamento_caixa(self),
        ).grid(row=2, column=2, padx=8, pady=5, sticky="ew")

    MisticaApp.montar_administracao = montar_administracao_com_manutencao
    MisticaApp._maintenance_patch_installed = True
    return MisticaApp
