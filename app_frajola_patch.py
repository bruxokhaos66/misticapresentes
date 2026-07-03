def aplicar_frajola_runtime(fonte):
    """Reaplica a aba completa do Frajola no app desktop."""

    if "self.tab_frajola = self.tabs.add(\"Frajola" not in fonte:
        fonte = fonte.replace(
            "        self.tab_ia = self.tabs.add(\"Isis a Bruxinha\")",
            "        self.tab_ia = self.tabs.add(\"Isis a Bruxinha\")\n        self.tab_frajola = self.tabs.add(\"Frajola 🐾\")",
            1,
        )
        fonte = fonte.replace(
            "        self.executar_montagem_segura(\"tab_ia\", self.montar_ia)",
            "        self.executar_montagem_segura(\"tab_ia\", self.montar_ia)\n        self.executar_montagem_segura(\"tab_frajola\", self.montar_frajola)",
            1,
        )

    marcador = "    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---"
    if marcador in fonte and "def montar_frajola(self):" not in fonte:
        metodos = r'''
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
            for texto, acao in [
                ("Alimentar", "alimentar"), ("Lanche", "lanche"), ("Brincar", "brincar"),
                ("Cuidar", "cuidar"), ("Limpar", "limpar"), ("Dormir/Acordar", "dormir"),
                ("Disciplinar", "disciplinar"), ("Atender chamado", "atender"), ("Reiniciar", "reiniciar"),
            ]:
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
            self.frajola_status_label.configure(text=f"Fase: {estado.get('fase')} | Idade: {estado.get('idade_dias')} dia(s) | Humor: {status_resumo(estado)}\nChamado: {chamado}")
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
        fonte = fonte.replace(marcador, metodos + "\n" + marcador, 1)

    return fonte
