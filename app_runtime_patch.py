def aplicar_patches_runtime(fonte):
    """Aplica painel simples e seguro de vendas/sincronização no dashboard."""

    # Venda deve registrar direto: sem popup extra e sem backup travando a tela.
    fonte = fonte.replace(
        '        realizar_backup()\n        registrar_log(self.current_user[\'nome\'], "Venda", f"N {vid} - {format_moeda(self.v_calc[\'tot\'])}")',
        '        try:\n            import threading\n            threading.Thread(target=realizar_backup, daemon=True).start()\n        except Exception:\n            pass\n        registrar_log(self.current_user[\'nome\'], "Venda", f"N {vid} - {format_moeda(self.v_calc[\'tot\'])}")',
        1,
    )
    fonte = fonte.replace(
        '        messagebox.showinfo("Venda salva", f"Venda no {vid} salva com sucesso.")\n',
        '',
        1,
    )

    # Icone unico do app: janela, barra de tarefas e janelas filhas do Tk.
    if "def aplicar_icone_mistica(self" not in fonte:
        marcador_icone = "    def adicionar_barra_rolagem_tree(self, tree):"
        metodo_icone = r'''
    def aplicar_icone_mistica(self):
        try:
            import ctypes
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BruxoBR.MisticaPresentes.App")
            except Exception:
                pass

            bases = []
            try:
                bases.append(Path(getattr(sys, "_MEIPASS", PROJECT_DIR)))
            except Exception:
                pass
            try:
                bases.append(Path(PROJECT_DIR))
            except Exception:
                pass
            try:
                bases.append(Path(sys.executable).resolve().parent)
            except Exception:
                pass

            ico = None
            png = None
            for base in bases:
                cand_ico = base / "assets" / "mistica_xamanico_moderno.ico"
                cand_png = base / "assets" / "mistica_xamanico_moderno.png"
                if ico is None and cand_ico.exists():
                    ico = cand_ico
                if png is None and cand_png.exists():
                    png = cand_png

            if ico is not None:
                try:
                    self.iconbitmap(str(ico))
                    self.wm_iconbitmap(str(ico))
                except Exception:
                    pass

            if png is not None:
                try:
                    self._icone_mistica_img = PhotoImage(file=str(png))
                    self.iconphoto(True, self._icone_mistica_img)
                except Exception:
                    pass
        except Exception as exc:
            try:
                registrar_erro_sistema("icone_mistica", exc)
            except Exception:
                pass

'''
        if marcador_icone in fonte:
            fonte = fonte.replace(marcador_icone, metodo_icone + marcador_icone, 1)

    if "self.aplicar_icone_mistica()" not in fonte:
        fonte = fonte.replace(
            '        self.title("Mística Presentes - Gestão v23")',
            '        self.title("Mística Presentes - Gestão v23")\n        self.aplicar_icone_mistica()',
            1,
        )

    # Guarda os cards principais do dashboard para atualizar sem reconstruir a tela.
    fonte = fonte.replace(
        '        f.columnconfigure((0, 1, 2, 3, 4), weight=1)',
        '        f.columnconfigure((0, 1, 2, 3, 4), weight=1)\n        f.rowconfigure(2, weight=1)',
        1,
    )
    fonte = fonte.replace(
        '            card = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15, border_width=2, border_color=cor)',
        '            card = ctk.CTkFrame(f, fg_color="#211728", corner_radius=14, border_width=1, border_color=cor)',
        1,
    )
    fonte = fonte.replace(
        '            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")',
        '            card.grid(row=0, column=idx, padx=6, pady=(4, 10), sticky="ew")',
        1,
    )
    fonte = fonte.replace(
        '            ctk.CTkLabel(card, text=titulo, font=("Arial", 11, "bold"), text_color=cor).pack(pady=(12, 2))',
        '            ctk.CTkLabel(card, text=titulo, font=("Arial", 12, "bold"), text_color="#f1e1b0").pack(pady=(12, 1))',
        1,
    )
    fonte = fonte.replace(
        '            ctk.CTkLabel(card, text=val, font=("Arial", 22, "bold"), text_color="#ffffff").pack(pady=(2, 12))',
        '            if not hasattr(self, "cards_dashboard_topo"):\n                self.cards_dashboard_topo = {}\n            lbl_kpi = ctk.CTkLabel(card, text=val, font=("Arial", 24, "bold"), text_color="#ffffff")\n            lbl_kpi.pack(pady=(2, 12))\n            self.cards_dashboard_topo[titulo] = lbl_kpi',
        1,
    )
    fonte = fonte.replace(
        '        f_info = ctk.CTkFrame(f, fg_color="#18121f", corner_radius=15)\n        f_info.grid(row=1, column=0, columnspan=5, pady=20, sticky="nsew")',
        '        f_info = ctk.CTkFrame(f, fg_color="#1b1422", corner_radius=14, border_width=1, border_color="#3d3048")\n        f_info.grid(row=1, column=0, columnspan=5, pady=(2, 10), sticky="ew")',
        1,
    )
    fonte = fonte.replace(
        '        ctk.CTkLabel(f_info, text="Mistica Presentes", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(15, 5))',
        '        ctk.CTkLabel(f_info, text="Mistica Presentes", font=("Georgia", 26, "bold"), text_color=self.cor_ouro).pack(pady=(12, 3))',
        1,
    )
    fonte = fonte.replace(
        '            font=("Arial", 14, "italic"),\n            wraplength=720,\n            text_color="#cccccc"',
        '            font=("Arial", 15, "italic"),\n            wraplength=860,\n            text_color="#f4ead7"',
        1,
    )
    fonte = fonte.replace(
        '        ctk.CTkLabel(f_info, text="Painel de alertas da Isis", font=self.font_label, text_color=self.cor_ouro).pack(pady=(10, 3))',
        '        ctk.CTkLabel(f_info, text="Painel de alertas da Isis", font=("Arial", 14, "bold"), text_color=self.cor_ouro).pack(pady=(4, 2))',
        1,
    )
    fonte = fonte.replace(
        '        ctk.CTkLabel(f_info, text=alertas_txt, font=("Arial", 13, "bold"), wraplength=900, justify="left", text_color="#f0e6d2").pack(padx=25, pady=(0, 10))',
        '        ctk.CTkLabel(f_info, text=alertas_txt, font=("Arial", 13, "bold"), wraplength=980, justify="left", text_color="#fff7e8").pack(padx=24, pady=(0, 10))',
        1,
    )

    # Sincronizacao automatica de usuarios com a API, sem travar a tela.
    if "def sincronizar_usuarios_online(self" not in fonte:
        marcador_sync = "    def adicionar_barra_rolagem_tree(self, tree):"
        metodos_sync = r'''
    def sincronizar_usuarios_online(self, contexto="automatico"):
        try:
            import threading
            def executar():
                try:
                    from services.usuario_sync_service import sincronizar_usuarios_com_api
                    retorno = sincronizar_usuarios_com_api(timeout=4)
                    try:
                        registrar_log("Sistema", "Sync usuarios", f"{contexto}: {retorno}")
                    except Exception:
                        pass
                except Exception as exc:
                    try:
                        registrar_erro_sistema(f"sync_usuarios_{contexto}", exc)
                    except Exception:
                        pass
            threading.Thread(target=executar, daemon=True).start()
        except Exception as exc:
            try:
                registrar_erro_sistema("sync_usuarios_agendar", exc)
            except Exception:
                pass

'''
        if marcador_sync in fonte:
            fonte = fonte.replace(marcador_sync, metodos_sync + marcador_sync, 1)

    if "self.sincronizar_usuarios_online(\"abertura\")" not in fonte:
        fonte = fonte.replace("        self.configurar_tabelas()\n        self.tela_login()", "        self.configurar_tabelas()\n        self.sincronizar_usuarios_online(\"abertura\")\n        self.tela_login()", 1)

    if "self.sincronizar_usuarios_online(\"login\")" not in fonte:
        fonte = fonte.replace("            self.montar_abas()", "            self.montar_abas()\n            self.sincronizar_usuarios_online(\"login\")", 1)

    if "self.sincronizar_usuarios_online(\"usuario_atualizado\")" not in fonte:
        fonte = fonte.replace("        messagebox.showinfo(\"Sucesso\", \"Usuário atualizado!\")", "        self.sincronizar_usuarios_online(\"usuario_atualizado\")\n        messagebox.showinfo(\"Sucesso\", \"Usuário atualizado!\")", 1)

    if "self.sincronizar_usuarios_online(\"usuario_desativado\")" not in fonte:
        fonte = fonte.replace("                atualizar_lista()\n        \n        ctk.CTkButton(f_btns, text=\"SALVAR ALTERAÇÕES\"", "                atualizar_lista()\n                self.sincronizar_usuarios_online(\"usuario_desativado\")\n        \n        ctk.CTkButton(f_btns, text=\"SALVAR ALTERAÇÕES\"", 1)

    if "self.sincronizar_usuarios_online(\"usuario_criado\")" not in fonte:
        fonte = fonte.replace("            self.up_u.delete(0, 'end')", "            self.up_u.delete(0, 'end')\n            self.sincronizar_usuarios_online(\"usuario_criado\")", 1)

    if "def montar_painel_vendas_dia(self" in fonte:
        return fonte

    botao = '        ctk.CTkButton(f_info, text="RECARREGAR INFORMACOES DO PAINEL", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)'
    fonte = fonte.replace(botao, '        self.montar_painel_vendas_dia(f)')

    pos_venda = 'registrar_log(self.current_user[\'nome\'], "Venda", f"N {vid} - {format_moeda(self.v_calc[\'tot\'])}")'
    fonte = fonte.replace(pos_venda, pos_venda + '\n        try:\n            self.atualizar_cards_dashboard_topo()\n            self.atualizar_painel_vendas_dia(apos_venda=True)\n        except Exception:\n            pass')

    marcador = '    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---'
    metodos = r'''
    def atualizar_cards_dashboard_topo(self):
        try:
            dados_dash = obter_kpis_dashboard()
            valores = {
                "VENDAS HOJE": format_moeda(dados_dash["tot_hoje"]),
                "VENDAS MES": format_moeda(dados_dash["tot_mes"]),
                "PRODUTOS": str(dados_dash["qtd_prod"]),
                "CLIENTES": str(dados_dash["qtd_cli"]),
                "PECAS ESTOQUE": str(dados_dash["tot_estoque"]),
            }
            if hasattr(self, "cards_dashboard_topo"):
                for titulo, valor in valores.items():
                    lbl = self.cards_dashboard_topo.get(titulo)
                    if lbl:
                        lbl.configure(text=valor)
        except Exception as exc:
            try:
                registrar_erro_sistema("dashboard_topo_update", exc)
            except Exception:
                pass

    def montar_painel_vendas_dia(self, parent=None):
        try:
            from services.vendedor_meta_service import resumo_vendedor_atual
            from services.dia_operacional_service import intervalo_vendas_hoje
        except Exception as exc:
            registrar_erro_sistema("painel_vendas_import", exc)
            return

        if parent is None:
            parent = getattr(self, "tab_d", None)
        if parent is None:
            return

        if hasattr(self, "frame_vendas_dia"):
            try:
                self.frame_vendas_dia.destroy()
            except Exception:
                pass

        try:
            parent.grid_rowconfigure(2, weight=1)
        except Exception:
            pass

        self.frame_vendas_dia = ctk.CTkFrame(parent, fg_color="#151019", corner_radius=14, border_width=1, border_color="#3b2d43")
        try:
            self.frame_vendas_dia.grid(row=2, column=0, columnspan=5, pady=(0, 4), sticky="nsew")
        except Exception:
            self.frame_vendas_dia.pack(fill="both", expand=True, padx=10, pady=8)

        inicio, fim, dia = intervalo_vendas_hoje()
        topo = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#211728", corner_radius=12)
        topo.pack(fill="x", padx=10, pady=(10, 8))
        titulo_topo = ctk.CTkFrame(topo, fg_color="transparent")
        titulo_topo.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        ctk.CTkLabel(titulo_topo, text=f"Vendas em tempo real - {dia}", font=("Arial", 18, "bold"), text_color=self.cor_ouro).pack(anchor="w")
        ctk.CTkLabel(titulo_topo, text="Vendido, meta, falta, mes, bonus e historico do dia.", font=("Arial", 12), text_color="#d9cde2").pack(anchor="w")

        status_box = ctk.CTkFrame(topo, fg_color="#0f1c16", corner_radius=10, border_width=1, border_color="#31533d")
        status_box.pack(side="right", padx=10, pady=8)
        self.lbl_sync_status = ctk.CTkLabel(status_box, text="API: verificando...", font=("Arial", 12, "bold"), text_color="#ffcc66", justify="right")
        self.lbl_sync_status.pack(padx=12, pady=7)

        cards = ctk.CTkFrame(self.frame_vendas_dia, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(0, 8))
        self.cards_painel_vendas = {}
        for titulo in ["Vendido", "Meta", "Falta", "Mês", "Bônus"]:
            card = ctk.CTkFrame(cards, fg_color="#241a2d", corner_radius=10, border_width=1, border_color="#3d3048")
            card.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(card, text=titulo.upper(), font=("Arial", 11, "bold"), text_color="#d8cada").pack(pady=(7, 0))
            lbl = ctk.CTkLabel(card, text="...", font=("Arial", 15, "bold"), text_color=self.cor_ouro)
            lbl.pack(pady=(1, 8))
            self.cards_painel_vendas[titulo] = lbl

        bloco = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#110d16", corner_radius=12, border_width=1, border_color="#34293c")
        bloco.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cab_hist = ctk.CTkFrame(bloco, fg_color="transparent")
        cab_hist.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(cab_hist, text="Historico do dia por vendedor e produto", font=("Arial", 14, "bold"), text_color=self.cor_ouro).pack(side="left")
        ctk.CTkLabel(cab_hist, text="Role para ver todas as vendas", font=("Arial", 12), text_color="#cfc3d5").pack(side="right")

        area = ctk.CTkFrame(bloco, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        try:
            area.configure(height=275)
            area.pack_propagate(False)
            area.grid_rowconfigure(0, weight=1)
            area.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        try:
            style = ttk.Style()
            style.configure("MisticaDashboard.Treeview", font=("Arial", 12), rowheight=30, background="#fbf7ef", fieldbackground="#fbf7ef", foreground="#1d1522", borderwidth=0)
            style.configure("MisticaDashboard.Treeview.Heading", font=("Arial", 12, "bold"), background="#3a2a44", foreground="#ffffff")
            style.map("MisticaDashboard.Treeview", background=[("selected", "#b98a3c")], foreground=[("selected", "#111111")])
        except Exception:
            pass

        self.tree_vendas_dia = ttk.Treeview(area, columns=("hora", "usuario", "produto", "qtd", "valor", "venda"), show="headings", height=9, style="MisticaDashboard.Treeview")
        scroll_y = ttk.Scrollbar(area, orient="vertical", command=self.tree_vendas_dia.yview)
        scroll_x = ttk.Scrollbar(area, orient="horizontal", command=self.tree_vendas_dia.xview)
        self.tree_vendas_dia.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        headers = {"hora":"Data/Hora", "usuario":"Usuario/Vendedor", "produto":"Produto", "qtd":"Qtd", "valor":"Valor", "venda":"Venda No"}
        widths = {"hora":155, "usuario":185, "produto":430, "qtd":70, "valor":125, "venda":85}
        for col in headers:
            self.tree_vendas_dia.heading(col, text=headers[col])
            self.tree_vendas_dia.column(col, width=widths[col], minwidth=widths[col], stretch=col == "produto", anchor="center" if col in ("qtd", "valor", "venda") else "w")
        self.tree_vendas_dia.tag_configure("par", background="#fffaf0")
        self.tree_vendas_dia.tag_configure("impar", background="#efe7db")
        self.tree_vendas_dia.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        def rolar_vendas(event):
            try:
                if getattr(event, "num", None) == 4:
                    self.tree_vendas_dia.yview_scroll(-3, "units")
                elif getattr(event, "num", None) == 5:
                    self.tree_vendas_dia.yview_scroll(3, "units")
                else:
                    delta = int(-1 * (event.delta / 120))
                    self.tree_vendas_dia.yview_scroll(delta, "units")
                return "break"
            except Exception:
                return None

        self.tree_vendas_dia.bind("<Enter>", lambda event: self.tree_vendas_dia.focus_set())
        self.tree_vendas_dia.bind("<MouseWheel>", rolar_vendas)
        self.tree_vendas_dia.bind("<Button-4>", rolar_vendas)
        self.tree_vendas_dia.bind("<Button-5>", rolar_vendas)

        self.atualizar_painel_vendas_dia()
        self.agendar_atualizacao_painel_vendas_dia()

    def _atualizar_status_sync_leve(self):
        try:
            from services.sync_service import estado_sincronizacao
            estado = estado_sincronizacao(tentar_enviar=False)
            pendencias = estado.get("pendencias", 0)
            ultima = estado.get("ultima_sincronizacao") or "Nunca"
            online = bool(estado.get("online"))
            painel = str(getattr(self, "_painel_mobile_status_texto", "") or "").strip()
            txt = f"API: {'Online' if online else 'Offline'} | Pendencias: {pendencias} | Ultima: {ultima}"
            if painel:
                txt = txt + " | " + painel
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=txt, text_color="#7CFC98" if online and int(pendencias or 0) == 0 else "#ffcc66")
        except Exception as exc:
            try:
                registrar_erro_sistema("painel_sync_status_leve", exc)
            except Exception:
                pass

    def _sincronizar_pendencias_em_segundo_plano(self):
        try:
            import threading
            if getattr(self, "_sync_painel_rodando", False):
                return
            self._sync_painel_rodando = True
            def executar():
                try:
                    from services.sync_service import sincronizar_pendencias
                    sincronizar_pendencias(limite=5)
                except Exception as exc:
                    try:
                        registrar_erro_sistema("painel_sync_background", exc)
                    except Exception:
                        pass
                finally:
                    try:
                        self._sync_painel_rodando = False
                    except Exception:
                        pass
                    try:
                        self.after(100, self._atualizar_status_sync_leve)
                    except Exception:
                        pass
            threading.Thread(target=executar, daemon=True).start()
        except Exception:
            pass

    def atualizar_painel_vendas_dia(self, apos_venda=False):
        try:
            from services.vendedor_meta_service import vendas_dia_operacional_detalhadas, resumo_vendedor_atual
            self.atualizar_cards_dashboard_topo()
            nome_usuario = self.current_user.get("nome", "Sistema") if isinstance(self.current_user, dict) else "Sistema"
            resumo_user = resumo_vendedor_atual(nome_usuario)
            if hasattr(self, "cards_painel_vendas"):
                valores = {
                    "Vendido": format_moeda(resumo_user['total']),
                    "Meta": format_moeda(resumo_user['meta']),
                    "Falta": format_moeda(resumo_user['falta']),
                    "Mês": format_moeda(resumo_user['total_mes']),
                    "Bônus": format_moeda(resumo_user['bonus']) if resumo_user['bateu_meta'] else "Pendente",
                }
                for titulo, valor in valores.items():
                    lbl = self.cards_painel_vendas.get(titulo)
                    if lbl:
                        lbl.configure(text=valor)
            if hasattr(self, "tree_vendas_dia"):
                for item in self.tree_vendas_dia.get_children():
                    self.tree_vendas_dia.delete(item)
                for idx, (venda_id, data_venda, data_iso, vendedor, produto, qtd, valor_item, total_venda, forma, dia_op) in enumerate(vendas_dia_operacional_detalhadas()):
                    self.tree_vendas_dia.insert("", "end", values=(data_venda or data_iso, vendedor, produto, qtd, format_moeda(valor_item), venda_id), tags=("par" if idx % 2 == 0 else "impar",))
            self._atualizar_status_sync_leve()
            if apos_venda:
                self._sincronizar_pendencias_em_segundo_plano()
        except Exception as exc:
            registrar_erro_sistema("painel_vendas_update", exc)

    def agendar_atualizacao_painel_vendas_dia(self):
        try:
            if hasattr(self, "frame_vendas_dia") and self.frame_vendas_dia.winfo_exists():
                if getattr(self, "_painel_vendas_after_id", None):
                    try:
                        self.after_cancel(self._painel_vendas_after_id)
                    except Exception:
                        pass
                self._painel_vendas_after_id = self.after(15000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))
        except Exception:
            pass

'''
    if marcador in fonte:
        fonte = fonte.replace(marcador, metodos + '\n' + marcador, 1)
    return fonte
