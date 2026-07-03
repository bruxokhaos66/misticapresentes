def aplicar_patches_runtime(fonte):
    """Aplica complementos de UI no app desktop sem alterar o arquivo principal gigante."""

    # Remove o botão manual antigo do dashboard. O painel passa a atualizar sozinho.
    chamada_dashboard = """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)"""
    fonte = fonte.replace(chamada_dashboard, "")

    # --- PAINEL DE VENDAS DO DIA ---
    if "def montar_painel_vendas_dia(self):" not in fonte:
        alvo_alertas = """ctk.CTkLabel(f_info, text=\"Painel de alertas da Isis\", font=self.font_label, text_color=self.cor_ouro).pack(pady=4)"""
        fonte = fonte.replace(
            alvo_alertas,
            alvo_alertas,
        )
        # Insere o painel logo após o card principal do dashboard, sem botão manual.
        marcador_inserir = """        self.montar_painel_vendas_dia(f)"""
        if marcador_inserir not in fonte:
            fonte = fonte.replace(
                """        # KPIs""",
                """        # KPIs""",
                1,
            )
            fonte = fonte.replace(
                """        f_info.pack(fill=\"x\", padx=20, pady=15)""",
                """        f_info.pack(fill=\"x\", padx=20, pady=(10, 8))""",
                1,
            )
            # Usa o antigo botão como ponto de inserção quando ainda existir em alguma versão local.
            fonte = fonte.replace(
                """ctk.CTkLabel(f_info, text=\"Painel atualizado automaticamente.\", font=(\"Arial\", 12, \"bold\"), text_color=self.cor_ouro).pack(pady=8)""",
                """self.montar_painel_vendas_dia(f)""",
                1,
            )
            # Fallback seguro: se o texto acima não existir, encaixa após o bloco de alertas.
            if "self.montar_painel_vendas_dia(f)" not in fonte:
                fonte = fonte.replace(
                    """alerta_txt = \"Alertas da Isis agora:\\n\" + \"\\n\".join(alertas[:5]) if alertas else \"Sem alertas críticos no momento.\""",
                    """alerta_txt = \"Alertas da Isis agora:\\n\" + \"\\n\".join(alertas[:5]) if alertas else \"Sem alertas críticos no momento.\""",
                    1,
                )

        chamada_pos_venda = """registrar_log(self.current_user['nome'], \"Venda\", f\"N {vid} - {format_moeda(self.v_calc['tot'])}\")"""
        fonte = fonte.replace(
            chamada_pos_venda,
            chamada_pos_venda + "\n        try:\n            self.atualizar_painel_vendas_dia()\n            self.atualizar_status_sincronizacao()\n        except Exception:\n            pass",
        )

        # Caso a inserção automática acima não tenha encontrado o ponto, usa o fechamento do dashboard.
        if "self.montar_painel_vendas_dia(f)" not in fonte:
            fonte = fonte.replace(
                """        self.avisos_dashboard(f_info)""",
                """        self.avisos_dashboard(f_info)\n        self.montar_painel_vendas_dia(f)""",
                1,
            )

        marcador = "    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---"
        metodos = r'''
    def montar_painel_vendas_dia(self, parent=None):
        try:
            from services.vendedor_meta_service import resumo_meta_vendedores, vendas_dia_operacional_detalhadas, resumo_vendedor_atual
            from services.dia_operacional_service import intervalo_vendas_hoje
        except Exception as exc:
            registrar_erro_sistema("painel_vendas_dia_import", exc)
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

        self.frame_vendas_dia = ctk.CTkFrame(parent, fg_color="#120d18", corner_radius=18)
        try:
            self.frame_vendas_dia.grid(row=2, column=0, columnspan=5, pady=(6, 10), sticky="nsew")
        except Exception:
            self.frame_vendas_dia.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        inicio, fim, dia = intervalo_vendas_hoje()

        header = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#1b1322", corner_radius=14)
        header.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(
            header,
            text=f"Vendas em tempo real • Dia operacional {dia} • zera após 23:00",
            font=("Arial", 17, "bold"),
            text_color=self.cor_ouro,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=12, pady=8)

        self.montar_status_sincronizacao(header)

        nome_usuario = self.current_user.get("nome", "Sistema") if isinstance(self.current_user, dict) else "Sistema"
        resumo_user = resumo_vendedor_atual(nome_usuario)

        cards = ctk.CTkFrame(self.frame_vendas_dia, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(0, 6))

        def mini_card(titulo, valor, cor="#f0e6d2"):
            card = ctk.CTkFrame(cards, fg_color="#18121f", corner_radius=12)
            card.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(card, text=titulo, font=("Arial", 11, "bold"), text_color="#bba7c7").pack(pady=(6, 0))
            ctk.CTkLabel(card, text=valor, font=("Arial", 14, "bold"), text_color=cor).pack(pady=(0, 6))

        mini_card("VENDIDO", format_moeda(resumo_user['total']), self.cor_ouro)
        mini_card("META", format_moeda(resumo_user['meta']))
        mini_card("FALTA", format_moeda(resumo_user['falta']), "#ffcc66")
        mini_card("MÊS", format_moeda(resumo_user['total_mes']))
        mini_card("BÔNUS", format_moeda(resumo_user['bonus']) if resumo_user['bateu_meta'] else "Pendente", "#7CFC98" if resumo_user['bateu_meta'] else "#ffcc66")

        bloco = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#18121f", corner_radius=14)
        bloco.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        topo = ctk.CTkFrame(bloco, fg_color="transparent")
        topo.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(topo, text="Histórico do dia por vendedor e produto", font=("Arial", 15, "bold"), text_color=self.cor_ouro).pack(side="left")
        ctk.CTkLabel(topo, text="Atualiza automaticamente a cada 5 segundos", font=("Arial", 11, "bold"), text_color="#bba7c7").pack(side="right")

        frame_tree_vendas = ctk.CTkFrame(bloco, fg_color="transparent")
        frame_tree_vendas.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree_vendas_dia = ttk.Treeview(frame_tree_vendas, columns=("hora", "usuario", "produto", "qtd", "valor", "venda"), show="headings", height=14)
        scroll_vendas_y = ttk.Scrollbar(frame_tree_vendas, orient="vertical", command=self.tree_vendas_dia.yview)
        self.tree_vendas_dia.configure(yscrollcommand=scroll_vendas_y.set)
        cabecalhos = {
            "hora": "Data/Hora",
            "usuario": "Usuário/Vendedor",
            "produto": "Produto vendido",
            "qtd": "Qtd",
            "valor": "Valor do item",
            "venda": "Venda Nº",
        }
        larguras = {"hora": 150, "usuario": 180, "produto": 420, "qtd": 70, "valor": 130, "venda": 90}
        for col, titulo in cabecalhos.items():
            self.tree_vendas_dia.heading(col, text=titulo)
            self.tree_vendas_dia.column(col, width=larguras[col], anchor="center" if col in ("qtd", "valor", "venda") else "w")
        self.tree_vendas_dia.pack(side="left", fill="both", expand=True)
        scroll_vendas_y.pack(side="right", fill="y")

        self.tree_meta_vendedores = ttk.Treeview(bloco, columns=("vendedor", "periodo", "vendido", "meta", "falta", "bonus"), show="headings", height=2)
        meta_heads = {
            "vendedor": "Vendedor",
            "periodo": "Período",
            "vendido": "Vendido",
            "meta": "Meta",
            "falta": "Falta",
            "bonus": "Bônus salarial",
        }
        for col, titulo in meta_heads.items():
            self.tree_meta_vendedores.heading(col, text=titulo)
            self.tree_meta_vendedores.column(col, width=150, anchor="center" if col != "vendedor" else "w")
        self.tree_meta_vendedores.pack(fill="x", padx=10, pady=(0, 8))

        self.atualizar_painel_vendas_dia()
        self.agendar_atualizacao_painel_vendas_dia()

    def montar_status_sincronizacao(self, parent=None):
        if parent is None:
            parent = getattr(self, "frame_vendas_dia", None) or getattr(self, "tab_d", None)
        if parent is None:
            return

        if hasattr(self, "frame_sync_status"):
            try:
                self.frame_sync_status.destroy()
            except Exception:
                pass

        self.frame_sync_status = ctk.CTkFrame(parent, fg_color="#101820", corner_radius=10)
        self.frame_sync_status.pack(side="right", padx=10, pady=6)
        self.lbl_sync_status = ctk.CTkLabel(
            self.frame_sync_status,
            text="Sincronização: verificando... | Pendências: 0 | Última sincronização: --",
            font=("Arial", 12, "bold"),
            text_color=self.cor_ouro,
            anchor="center",
        )
        self.lbl_sync_status.pack(padx=10, pady=6)
        self.atualizar_status_sincronizacao()
        self.agendar_status_sincronizacao()

    def atualizar_status_sincronizacao(self):
        try:
            from services.sync_service import estado_sincronizacao
            estado = estado_sincronizacao(tentar_enviar=True)
            status = estado.get("status", "Offline")
            pendencias = estado.get("pendencias", 0)
            ultima = estado.get("ultima_sincronizacao") or "Nunca"
            cor = "#7CFC98" if estado.get("online") and int(pendencias or 0) == 0 else "#ffcc66"
            if not estado.get("online"):
                cor = "#ff6b6b"
            texto = f"Sincronização: {status} | Pendências: {pendencias} | Última: {ultima}"
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=texto, text_color=cor)
        except Exception as exc:
            try:
                if hasattr(self, "lbl_sync_status"):
                    self.lbl_sync_status.configure(
                        text="Sincronização: Offline | Pendências: verificar | Última: indisponível",
                        text_color="#ff6b6b",
                    )
            except Exception:
                pass
            try:
                registrar_erro_sistema("status_sincronizacao", exc)
            except Exception:
                pass

    def atualizar_painel_vendas_dia(self):
        try:
            from services.vendedor_meta_service import resumo_meta_vendedores, vendas_dia_operacional_detalhadas
        except Exception as exc:
            registrar_erro_sistema("painel_vendas_dia_update_import", exc)
            return

        if hasattr(self, "tree_vendas_dia"):
            try:
                for item in self.tree_vendas_dia.get_children():
                    self.tree_vendas_dia.delete(item)
                for venda_id, data_venda, data_iso, vendedor, produto, qtd, valor_item, total_venda, forma, dia_op in vendas_dia_operacional_detalhadas():
                    hora = data_venda or data_iso
                    self.tree_vendas_dia.insert("", "end", values=(hora, vendedor, produto, qtd, format_moeda(valor_item), venda_id))
            except Exception as exc:
                registrar_erro_sistema("painel_vendas_dia_tree", exc)

        if hasattr(self, "tree_meta_vendedores"):
            try:
                for item in self.tree_meta_vendedores.get_children():
                    self.tree_meta_vendedores.delete(item)
                metas = resumo_meta_vendedores()
                if not metas:
                    self.tree_meta_vendedores.insert("", "end", values=("Sem vendas no período", "segunda até sábado 12:00", format_moeda(0), format_moeda(1500), format_moeda(1500), format_moeda(0)))
                for m in metas:
                    periodo = f"{m['inicio']} até {m['fim']}"
                    bonus = format_moeda(m['bonus']) if m['bateu_meta'] else "Sem bônus ainda"
                    self.tree_meta_vendedores.insert("", "end", values=(m['vendedor'], periodo, format_moeda(m['total']), format_moeda(m['meta']), format_moeda(m['falta']), bonus))
            except Exception as exc:
                registrar_erro_sistema("painel_meta_vendedores_tree", exc)

    def agendar_atualizacao_painel_vendas_dia(self):
        try:
            if hasattr(self, "frame_vendas_dia") and self.frame_vendas_dia.winfo_exists():
                if getattr(self, "_painel_vendas_after_id", None):
                    try:
                        self.after_cancel(self._painel_vendas_after_id)
                    except Exception:
                        pass
                self._painel_vendas_after_id = self.after(5000, lambda: (self.atualizar_painel_vendas_dia(), self.atualizar_status_sincronizacao(), self.agendar_atualizacao_painel_vendas_dia()))
        except Exception:
            pass

    def agendar_status_sincronizacao(self):
        try:
            if hasattr(self, "frame_sync_status") and self.frame_sync_status.winfo_exists():
                if getattr(self, "_sync_status_after_id", None):
                    try:
                        self.after_cancel(self._sync_status_after_id)
                    except Exception:
                        pass
                self._sync_status_after_id = self.after(5000, lambda: (self.atualizar_status_sincronizacao(), self.agendar_status_sincronizacao()))
        except Exception:
            pass

'''
        fonte = fonte.replace(marcador, metodos + "\n" + marcador)

    # --- FRAJOLA PET VIRTUAL: somente no aplicativo desktop ---
    if "self.tab_frajola = self.tabs.add(\"Frajola" not in fonte:
        fonte = fonte.replace(
            "        self.tab_ia = self.tabs.add(\"Isis a Bruxinha\")",
            "        self.tab_ia = self.tabs.add(\"Isis a Bruxinha\")\n        self.tab_frajola = self.tabs.add(\"Frajola 🐾\")",
        )
        fonte = fonte.replace(
            "        self.executar_montagem_segura(\"tab_ia\", self.montar_ia)",
            "        self.executar_montagem_segura(\"tab_ia\", self.montar_ia)\n        self.executar_montagem_segura(\"tab_frajola\", self.montar_frajola)",
        )

    marcador_frajola = "    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---"
    if marcador_frajola in fonte and "def montar_frajola(self):" not in fonte:
        metodos_frajola = r'''
    def montar_frajola(self):
        try:
            from services.frajola_service import carregar_estado, executar_acao, sprite_atual, status_resumo
            self._frajola_service = (carregar_estado, executar_acao, sprite_atual, status_resumo)

            for w in self.tab_frajola.winfo_children():
                w.destroy()

            base = ctk.CTkFrame(self.tab_frajola, fg_color=self.cor_vinho, corner_radius=18)
            base.pack(fill="both", expand=True, padx=20, pady=20)

            ctk.CTkLabel(base, text="Frajola - Pet Virtual da Mística", font=("Arial", 28, "bold"), text_color=self.cor_ouro).pack(pady=(18, 4))
            ctk.CTkLabel(base, text="Cuide do Frajola durante o dia para manter a loja mais divertida.", font=("Arial", 15), text_color="#f0e6d2").pack(pady=(0, 14))

            corpo = ctk.CTkFrame(base, fg_color="#18121f", corner_radius=15)
            corpo.pack(fill="both", expand=True, padx=18, pady=10)

            esquerda = ctk.CTkFrame(corpo, fg_color="transparent")
            esquerda.pack(side="left", fill="both", expand=True, padx=18, pady=18)

            direita = ctk.CTkFrame(corpo, fg_color="transparent")
            direita.pack(side="right", fill="both", expand=True, padx=18, pady=18)

            self.frajola_sprite_label = ctk.CTkLabel(esquerda, text="", font=("Consolas", 34, "bold"), text_color="#ffffff", justify="center")
            self.frajola_sprite_label.pack(pady=10)

            self.frajola_status_label = ctk.CTkLabel(esquerda, text="", font=("Arial", 16, "bold"), text_color=self.cor_ouro, wraplength=460, justify="center")
            self.frajola_status_label.pack(pady=8)

            self.frajola_evento_label = ctk.CTkLabel(esquerda, text="", font=("Arial", 14), text_color="#f0e6d2", wraplength=480, justify="center")
            self.frajola_evento_label.pack(pady=8)

            self.frajola_barras = {}
            for nome in ["fome", "felicidade", "saude", "limpeza", "energia", "disciplina", "xp"]:
                linha = ctk.CTkFrame(direita, fg_color="transparent")
                linha.pack(fill="x", pady=5)
                ctk.CTkLabel(linha, text=nome.capitalize(), width=100, anchor="w", font=self.font_label, text_color="#f0e6d2").pack(side="left")
                barra = ctk.CTkProgressBar(linha)
                barra.pack(side="left", fill="x", expand=True, padx=8)
                valor = ctk.CTkLabel(linha, text="0", width=45, font=self.font_label, text_color=self.cor_ouro)
                valor.pack(side="left")
                self.frajola_barras[nome] = (barra, valor)

            botoes = ctk.CTkFrame(base, fg_color="transparent")
            botoes.pack(fill="x", padx=18, pady=(4, 16))

            acoes = [
                ("Alimentar", "alimentar"), ("Lanche", "lanche"), ("Brincar", "brincar"),
                ("Cuidar", "cuidar"), ("Limpar", "limpar"), ("Dormir/Acordar", "dormir"),
                ("Disciplinar", "disciplinar"), ("Atender chamado", "atender"), ("Reiniciar", "reiniciar"),
            ]

            for texto, acao in acoes:
                ctk.CTkButton(botoes, text=texto, height=38, width=145, font=self.font_button, fg_color=self.cor_botao, command=lambda a=acao: self.executar_acao_frajola(a)).pack(side="left", padx=5, pady=5)

            self.atualizar_frajola()
            self.agendar_atualizacao_frajola()
        except Exception as exc:
            registrar_erro_sistema("montar_frajola", exc)

    def executar_acao_frajola(self, acao):
        try:
            carregar_estado, executar_acao, sprite_atual, status_resumo = self._frajola_service
            executar_acao(acao)
            self.atualizar_frajola()
        except Exception as exc:
            registrar_erro_sistema("executar_acao_frajola", exc)

    def atualizar_frajola(self):
        try:
            carregar_estado, executar_acao, sprite_atual, status_resumo = self._frajola_service
            estado = carregar_estado()

            self.frajola_sprite_label.configure(text=sprite_atual(estado))
            chamado = estado.get("chamado") or "Nenhum chamado no momento."
            self.frajola_status_label.configure(
                text=f"Fase: {estado.get('fase')} | Idade: {estado.get('idade_dias')} dia(s) | Humor: {status_resumo(estado)}\nChamado: {chamado}"
            )
            self.frajola_evento_label.configure(text=estado.get("ultimo_evento", ""))

            for nome, (barra, valor) in self.frajola_barras.items():
                v = int(estado.get(nome, 0))
                barra.set(max(0, min(100, v)) / 100)
                valor.configure(text=str(v))
        except Exception as exc:
            registrar_erro_sistema("atualizar_frajola", exc)

    def agendar_atualizacao_frajola(self):
        try:
            if hasattr(self, "tab_frajola") and self.tab_frajola.winfo_exists():
                self.after(30000, lambda: (self.atualizar_frajola(), self.agendar_atualizacao_frajola()))
        except Exception:
            pass

'''
        fonte = fonte.replace(marcador_frajola, metodos_frajola + "\n" + marcador_frajola)

    return fonte
