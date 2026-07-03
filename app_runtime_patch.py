def aplicar_patches_runtime(fonte):
    """Aplica complementos de UI no app desktop sem alterar o arquivo principal gigante."""

    # --- PAINEL DE VENDAS DO DIA ---
    if "def montar_painel_vendas_dia(self):" not in fonte:
        chamada_dashboard = """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)"""
        fonte = fonte.replace(
            chamada_dashboard,
            chamada_dashboard + "\n        self.montar_painel_vendas_dia(f)",
        )

        chamada_pos_venda = """registrar_log(self.current_user['nome'], \"Venda\", f\"N {vid} - {format_moeda(self.v_calc['tot'])}\")"""
        fonte = fonte.replace(
            chamada_pos_venda,
            chamada_pos_venda + "\n        try:\n            self.atualizar_painel_vendas_dia()\n        except Exception:\n            pass",
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

        self.frame_vendas_dia = ctk.CTkFrame(parent, fg_color=self.cor_vinho, corner_radius=15)
        try:
            self.frame_vendas_dia.grid(row=2, column=0, columnspan=5, pady=10, sticky="nsew")
        except Exception:
            self.frame_vendas_dia.pack(fill="both", expand=True, padx=10, pady=10)

        inicio, fim, dia = intervalo_vendas_hoje()
        ctk.CTkLabel(
            self.frame_vendas_dia,
            text=f"ACOMPANHAMENTO DO DIA - vendas do período operacional {dia} | zera após 23:00",
            font=("Arial", 17, "bold"),
            text_color=self.cor_ouro,
        ).pack(pady=(10, 4))

        nome_usuario = self.current_user.get("nome", "Sistema") if isinstance(self.current_user, dict) else "Sistema"
        resumo_user = resumo_vendedor_atual(nome_usuario)
        texto_meta = (
            f"Seu período de meta: {resumo_user['inicio']} até {resumo_user['fim']} | "
            f"Vendido: {format_moeda(resumo_user['total'])} de {format_moeda(resumo_user['meta'])} | "
            f"Falta: {format_moeda(resumo_user['falta'])} | "
            f"Mês: {format_moeda(resumo_user['total_mes'])} | "
            f"Bônus: {format_moeda(resumo_user['bonus']) if resumo_user['bateu_meta'] else 'ainda não atingido'}"
        )
        ctk.CTkLabel(
            self.frame_vendas_dia,
            text=texto_meta,
            font=("Arial", 13, "bold"),
            text_color="#f0e6d2",
            wraplength=1100,
        ).pack(padx=12, pady=(0, 8))

        bloco = ctk.CTkFrame(self.frame_vendas_dia, fg_color="#18121f", corner_radius=12)
        bloco.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        topo = ctk.CTkFrame(bloco, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(topo, text="Vendas em tempo real por usuário", font=self.font_label, text_color=self.cor_ouro).pack(side="left")
        ctk.CTkButton(topo, text="ATUALIZAR", width=130, height=34, font=self.font_button, fg_color=self.cor_botao, command=self.atualizar_painel_vendas_dia).pack(side="right")

        self.tree_vendas_dia = ttk.Treeview(bloco, columns=("hora", "usuario", "produto", "qtd", "valor", "venda"), show="headings", height=8)
        cabecalhos = {
            "hora": "Data/Hora",
            "usuario": "Usuário/Vendedor",
            "produto": "Produto vendido",
            "qtd": "Qtd",
            "valor": "Valor do item",
            "venda": "Venda Nº",
        }
        larguras = {"hora": 140, "usuario": 170, "produto": 320, "qtd": 60, "valor": 110, "venda": 80}
        for col, titulo in cabecalhos.items():
            self.tree_vendas_dia.heading(col, text=titulo)
            self.tree_vendas_dia.column(col, width=larguras[col], anchor="center" if col in ("qtd", "valor", "venda") else "w")
        self.tree_vendas_dia.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree_meta_vendedores = ttk.Treeview(bloco, columns=("vendedor", "periodo", "vendido", "meta", "falta", "bonus"), show="headings", height=5)
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
        self.tree_meta_vendedores.pack(fill="x", padx=8, pady=(0, 8))

        self.atualizar_painel_vendas_dia()
        self.agendar_atualizacao_painel_vendas_dia()

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
                self.after(30000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))
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
