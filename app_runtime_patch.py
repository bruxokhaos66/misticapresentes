def aplicar_patches_runtime(fonte):
    """Aplica painel simples e seguro de vendas/sincronização no dashboard."""

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

    if "def montar_barra_frajola(self" not in fonte:
        marcador_frajola = "    def adicionar_barra_rolagem_tree(self, tree):"
        metodo_frajola = r'''
    def montar_barra_frajola(self, parent=None):
        try:
            if parent is None:
                parent = getattr(self, "tab_d", None)
            if parent is None:
                return
            barra = ctk.CTkFrame(parent, fg_color="#120d18", corner_radius=14, border_width=1, border_color="#4f835f")
            barra.pack(fill="x", padx=22, pady=(4, 10))
            ctk.CTkLabel(barra, text="🐾 Frajola Online", font=("Arial", 15, "bold"), text_color=self.cor_ouro).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(barra, text="Humor: Feliz  •  Energia: 100%  •  Pet virtual da Mística", font=("Arial", 13, "bold"), text_color="#f0e6d2").pack(side="left", padx=8, pady=8)
            ctk.CTkButton(barra, text="Abrir Frajola", width=130, height=32, font=("Arial", 12, "bold"), fg_color="#4f835f", command=lambda: messagebox.showinfo("Frajola", "🐾 Miau! O Frajola está online e acompanhando a loja.")).pack(side="right", padx=12, pady=8)
        except Exception as exc:
            try:
                registrar_erro_sistema("montar_barra_frajola", exc)
            except Exception:
                pass

'''
        if marcador_frajola in fonte:
            fonte = fonte.replace(marcador_frajola, metodo_frajola + marcador_frajola, 1)

    if "self.montar_barra_frajola(f_info)" not in fonte:
        alvo_frajola = "        self.dashboard_msg_lbl.pack(pady=10)"
        fonte = fonte.replace(alvo_frajola, alvo_frajola + "\n        self.montar_barra_frajola(f_info)", 1)

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
    fonte = fonte.replace(pos_venda, pos_venda + '\n        try:\n            self.atualizar_painel_vendas_dia()\n        except Exception:\n            pass')

    marcador = '    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---'
    metodos = r'''
    def montar_painel_vendas_dia(self, parent=None):
        try:
            from services.vendedor_meta_service import resumo_meta_vendedores, vendas_dia_operacional_detalhadas, resumo_vendedor_atual
            from services.dia_operacional_service import intervalo_vendas_hoje
            from services.sync_service import estado_sincronizacao
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

        self.frame_vendas_dia = ctk.CTkFrame(parent, fg_color="#18121f", corner_radius=16)
        try:
            self.frame_vendas_dia.grid(row=2, column=0, columnspan=5, pady=8, sticky="nsew")
        except Exception:
            self.frame_vendas_dia.pack(fill="both", expand=True, padx=10, pady=8)

        inicio, fim, dia = intervalo_vendas_hoje()
        topo = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#120d18", corner_radius=12)
        topo.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(topo, text=f"Vendas em tempo real • {dia}", font=("Arial", 17, "bold"), text_color=self.cor_ouro).pack(side="left", padx=12, pady=8)

        self.lbl_sync_status = ctk.CTkLabel(topo, text="Sincronização: verificando...", font=("Arial", 12, "bold"), text_color=self.cor_ouro)
        self.lbl_sync_status.pack(side="right", padx=12, pady=8)

        nome_usuario = self.current_user.get("nome", "Sistema") if isinstance(self.current_user, dict) else "Sistema"
        resumo_user = resumo_vendedor_atual(nome_usuario)
        cards = ctk.CTkFrame(self.frame_vendas_dia, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(0, 6))

        for titulo, valor in [
            ("Vendido", format_moeda(resumo_user['total'])),
            ("Meta", format_moeda(resumo_user['meta'])),
            ("Falta", format_moeda(resumo_user['falta'])),
            ("Mês", format_moeda(resumo_user['total_mes'])),
            ("Bônus", format_moeda(resumo_user['bonus']) if resumo_user['bateu_meta'] else "Pendente"),
        ]:
            card = ctk.CTkFrame(cards, fg_color="#241d2b", corner_radius=10)
            card.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(card, text=titulo.upper(), font=("Arial", 10, "bold"), text_color="#cbbdce").pack(pady=(5, 0))
            ctk.CTkLabel(card, text=valor, font=("Arial", 13, "bold"), text_color=self.cor_ouro).pack(pady=(0, 5))

        bloco = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#120d18", corner_radius=12)
        bloco.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        ctk.CTkLabel(bloco, text="Histórico do dia por vendedor e produto • atualiza a cada 5 segundos", font=("Arial", 13, "bold"), text_color=self.cor_ouro).pack(anchor="w", padx=10, pady=(8, 4))

        area = ctk.CTkFrame(bloco, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree_vendas_dia = ttk.Treeview(area, columns=("hora", "usuario", "produto", "qtd", "valor", "venda"), show="headings", height=12)
        scroll_y = ttk.Scrollbar(area, orient="vertical", command=self.tree_vendas_dia.yview)
        self.tree_vendas_dia.configure(yscrollcommand=scroll_y.set)
        headers = {"hora":"Data/Hora", "usuario":"Usuário/Vendedor", "produto":"Produto", "qtd":"Qtd", "valor":"Valor", "venda":"Venda Nº"}
        widths = {"hora":150, "usuario":180, "produto":420, "qtd":60, "valor":120, "venda":80}
        for col in headers:
            self.tree_vendas_dia.heading(col, text=headers[col])
            self.tree_vendas_dia.column(col, width=widths[col], anchor="center" if col in ("qtd", "valor", "venda") else "w")
        self.tree_vendas_dia.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        self.atualizar_painel_vendas_dia()
        self.agendar_atualizacao_painel_vendas_dia()

    def atualizar_painel_vendas_dia(self):
        try:
            from services.vendedor_meta_service import vendas_dia_operacional_detalhadas
            from services.sync_service import estado_sincronizacao
            estado = estado_sincronizacao(tentar_enviar=True)
            pendencias = estado.get("pendencias", 0)
            ultima = estado.get("ultima_sincronizacao") or "Nunca"
            online = bool(estado.get("online"))
            txt = f"Sincronização: {'Online' if online else 'Offline'} | Pendências: {pendencias} | Última: {ultima}"
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=txt, text_color="#7CFC98" if online and int(pendencias or 0) == 0 else "#ffcc66")
            if hasattr(self, "tree_vendas_dia"):
                for item in self.tree_vendas_dia.get_children():
                    self.tree_vendas_dia.delete(item)
                for venda_id, data_venda, data_iso, vendedor, produto, qtd, valor_item, total_venda, forma, dia_op in vendas_dia_operacional_detalhadas():
                    self.tree_vendas_dia.insert("", "end", values=(data_venda or data_iso, vendedor, produto, qtd, format_moeda(valor_item), venda_id))
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
                self._painel_vendas_after_id = self.after(5000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))
        except Exception:
            pass

'''
    if marcador in fonte:
        fonte = fonte.replace(marcador, metodos + '\n' + marcador, 1)
    return fonte
