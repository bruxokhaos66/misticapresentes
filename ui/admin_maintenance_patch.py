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


_TITULOS = {
    "ok": "Status",
    "area": "Área",
    "acao": "Ação",
    "removeu_mensagem_personalizada": "Mensagem personalizada removida",
    "mensagem": "Resultado",
    "caixas_abertos": "Caixas abertos",
    "fluxo_sem_caixa": "Lançamentos sem caixa vinculado",
    "produtos_sem_categoria": "Produtos sem categoria",
    "contas_pendentes": "Contas pendentes",
    "valor_pendente": "Valor pendente",
    "contas_pagas_sem_fluxo": "Contas pagas sem fluxo localizado",
    "vendas_sem_fluxo": "Vendas sem fluxo localizado",
    "backup": "Backup",
}

_VALORES = {
    True: "OK",
    False: "Não",
    "dashboard": "Dashboard",
    "caixa": "Caixa",
    "estoque": "Estoque",
    "financeiro": "Financeiro",
    "geral": "Geral",
    "reiniciar_visual": "Reinício visual",
}


def _valor_amigavel(valor):
    if valor in _VALORES:
        return _VALORES[valor]
    if isinstance(valor, float):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(valor)


def _formatar_resultado(dados):
    if isinstance(dados, dict):
        if dados.get("area") == "dashboard":
            return dados.get("mensagem") or "Dashboard reiniciado visualmente sem apagar dados reais."

        linhas = []
        ordem = [
            "ok",
            "area",
            "acao",
            "mensagem",
            "caixas_abertos",
            "fluxo_sem_caixa",
            "produtos_sem_categoria",
            "contas_pendentes",
            "valor_pendente",
            "contas_pagas_sem_fluxo",
            "vendas_sem_fluxo",
            "backup",
        ]
        ocultar = {
            "ultimos_caixas",
            "produtos_baixos",
            "produtos_negativos",
            "diagnostico_geral",
            "caixa",
            "estoque",
            "financeiro",
            "lancamento_removido",
        }
        for chave in ordem:
            if chave in dados and chave not in ocultar:
                linhas.append(f"{_TITULOS.get(chave, chave)}: {_valor_amigavel(dados[chave])}")
        for chave, valor in dados.items():
            if chave in ordem or chave in ocultar or chave == "problemas":
                continue
            linhas.append(f"{_TITULOS.get(chave, chave)}: {_valor_amigavel(valor)}")

        problemas = dados.get("problemas") or []
        if problemas:
            linhas.append("\nProblemas encontrados:")
            linhas.extend(f"- {p}" for p in problemas)
        elif dados.get("ok") is True:
            linhas.append("\nNenhum problema crítico encontrado.")
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
    win.geometry("980x600")
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
        text="Selecione um ou vários lançamentos com o mouse. Use Ctrl+clique para marcar itens separados e Shift+clique para marcar sequência. O sistema cria backup e registra log com o usuário.",
        font=getattr(app, "font_input", ("Arial", 13)),
        wraplength=900,
    ).pack(pady=(0, 12))

    tree = ttk.Treeview(
        win,
        columns=("id", "tipo", "descricao", "valor", "data", "caixa", "forma"),
        show="headings",
        height=14,
        selectmode="extended",
    )
    for col, titulo in zip(("id", "tipo", "descricao", "valor", "data", "caixa", "forma"), ("ID", "Tipo", "Descrição", "Valor", "Data", "Caixa", "Forma")):
        tree.heading(col, text=titulo)
    tree.column("id", width=60, anchor="center")
    tree.column("tipo", width=80, anchor="center")
    tree.column("descricao", width=360)
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

    def selecionar_todos():
        tree.selection_set(tree.get_children())

    def limpar_selecao():
        tree.selection_remove(tree.selection())

    def apagar():
        selecoes = list(tree.selection())
        if not selecoes:
            messagebox.showwarning("Caixa", "Selecione um ou mais lançamentos para apagar.")
            return

        itens = []
        total_estimado = 0.0
        for item in selecoes:
            valores = tree.item(item, "values")
            itens.append(valores)
            try:
                total_estimado += float(str(valores[3]).replace("R$", "").replace(".", "").replace(",", ".").strip())
            except Exception:
                pass

        motivo_txt = motivo.get().strip() or "Correção administrativa"
        preview = "\n".join(f"- ID {v[0]} | {v[1]} | {v[3]} | {v[2][:70]}" for v in itens[:8])
        if len(itens) > 8:
            preview += f"\n... e mais {len(itens) - 8} lançamento(s)."
        aviso = (
            f"Você selecionou {len(itens)} lançamento(s) para apagar.\n"
            f"Total aproximado selecionado: {_valor_amigavel(total_estimado)}\n\n"
            f"{preview}\n\n"
            f"Motivo: {motivo_txt}\n\n"
            "Antes de cada exclusão, o sistema fará backup e registrará log com seu usuário.\n"
            "Confirmar?"
        )
        if not messagebox.askyesno("Confirmar exclusão do caixa", aviso):
            return
        if not messagebox.askyesno("Confirmação final", "Esta ação altera o fluxo do caixa. Deseja realmente continuar?"):
            return
        removidos = 0
        erros = []
        for valores in itens:
            fluxo_id = valores[0]
            try:
                apagar_lancamento_caixa(app.current_user, fluxo_id, motivo_txt)
                removidos += 1
            except Exception as exc:
                erros.append(f"ID {fluxo_id}: {exc}")
        carregar()
        try:
            if hasattr(app, "refresh_audit"):
                app.refresh_audit(filtrar=False)
        except Exception:
            pass
        if erros:
            messagebox.showwarning("Caixa", f"{removidos} lançamento(s) apagado(s).\n\nErros:\n" + "\n".join(erros[:10]))
        else:
            messagebox.showinfo("Caixa", f"{removidos} lançamento(s) apagado(s) com backup e log administrativo.")

    botoes = ctk.CTkFrame(win, fg_color="transparent")
    botoes.pack(fill="x", padx=14, pady=10)
    ctk.CTkButton(botoes, text="RECARREGAR", height=38, command=carregar).pack(side="left", padx=4)
    ctk.CTkButton(botoes, text="SELECIONAR TODOS", height=38, fg_color="#5c5c5c", command=selecionar_todos).pack(side="left", padx=4)
    ctk.CTkButton(botoes, text="LIMPAR SELEÇÃO", height=38, fg_color="#5c5c5c", command=limpar_selecao).pack(side="left", padx=4)
    ctk.CTkButton(botoes, text="APAGAR SELECIONADOS", height=38, fg_color="#7f4c4c", command=apagar).pack(side="right", padx=4)

    carregar()


def _habilitar_selecao_multipla_treeviews(app):
    """Habilita Ctrl+clique/Shift+clique nos Treeviews já existentes da interface."""
    for nome, valor in vars(app).items():
        if isinstance(valor, ttk.Treeview):
            try:
                valor.configure(selectmode="extended")
            except Exception:
                pass


def patch_mistica_app(MisticaApp):
    if getattr(MisticaApp, "_maintenance_patch_installed", False):
        return MisticaApp

    original_montar_administracao = MisticaApp.montar_administracao
    original_executar_montagem_segura = getattr(MisticaApp, "executar_montagem_segura", None)

    def montar_administracao_com_manutencao(self, *args, **kwargs):
        original_montar_administracao(self, *args, **kwargs)
        if not self.current_user or self.current_user.get("perfil") != "adm":
            return

        painel = ctk.CTkFrame(self.tab_adm, fg_color=getattr(self, "cor_vinho", "#1a1621"), corner_radius=15)
        filhos = list(self.tab_adm.winfo_children())
        if filhos:
            painel.pack(fill="x", padx=20, pady=(10, 14), ipady=10, before=filhos[0])
        else:
            painel.pack(fill="x", padx=20, pady=(10, 14), ipady=10)
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
            text="APAGAR LANÇAMENTOS DO CAIXA",
            height=38,
            fg_color="#7f4c4c",
            font=getattr(self, "font_button", ("Arial", 13, "bold")),
            command=lambda: _janela_apagar_lancamento_caixa(self),
        ).grid(row=2, column=2, padx=8, pady=5, sticky="ew")

        _habilitar_selecao_multipla_treeviews(self)

    def executar_montagem_segura_com_multiselecao(self, *args, **kwargs):
        if original_executar_montagem_segura:
            retorno = original_executar_montagem_segura(self, *args, **kwargs)
        else:
            retorno = None
        _habilitar_selecao_multipla_treeviews(self)
        return retorno

    MisticaApp.montar_administracao = montar_administracao_com_manutencao
    if original_executar_montagem_segura:
        MisticaApp.executar_montagem_segura = executar_montagem_segura_com_multiselecao
    MisticaApp._maintenance_patch_installed = True
    return MisticaApp
