def aplicar_pagamento_misto_runtime(fonte: str) -> str:
    """Adiciona pagamento misto profissional na tela de vendas sem reescrever o app inteiro."""
    try:
        from app_sync_pagamento_misto_payload_patch import aplicar_sync_pagamento_misto_payload_runtime
        fonte = aplicar_sync_pagamento_misto_payload_runtime(fonte)
    except Exception as exc:
        print(f"[Patch Pagamento Misto Sync] {exc}")

    antigo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))'''
    novo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x", "Misto"], command=lambda e: self.on_pagamento_venda_change(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))

        self.v_misto_frame = ctk.CTkFrame(corpo_checkout, fg_color="#241d2b", corner_radius=10)
        ctk.CTkLabel(self.v_misto_frame, text="Pagamento misto", font=self.font_label, text_color=self.cor_ouro).pack(pady=(6, 2))
        ctk.CTkLabel(self.v_misto_frame, text="Divida o valor em até 4 formas. Use o botão para completar o restante.", font=("Arial", 11, "bold"), text_color="#d8cbb6", wraplength=290).pack(pady=(0, 4))

        self.v_misto_linhas = []
        formas_mistas = ["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"]
        sugestoes = ["Dinheiro", "Pix", "Debito", "Credito 1x"]
        for indice in range(4):
            linha = ctk.CTkFrame(self.v_misto_frame, fg_color="transparent")
            linha.pack(fill="x", padx=8, pady=2)
            forma = ctk.CTkOptionMenu(linha, values=formas_mistas, command=lambda e: self.render_v_car(), width=132, height=32, font=self.font_button, dropdown_font=self.font_input)
            forma.set(sugestoes[indice])
            forma.pack(side="left", padx=(0, 5))
            valor = ctk.CTkEntry(linha, placeholder_text=f"Valor {indice + 1}", height=32, font=self.font_input)
            valor.pack(side="left", fill="x", expand=True)
            valor.bind("<KeyRelease>", lambda e: self.render_v_car())
            self.v_misto_linhas.append({"forma": forma, "valor": valor})

        ctk.CTkButton(self.v_misto_frame, text="COMPLETAR RESTANTE NO ÚLTIMO CAMPO", height=32, font=("Arial", 12, "bold"), fg_color="#5f7f4c", command=self.preencher_restante_pagamento_misto).pack(fill="x", padx=8, pady=(4, 8))
        self.v_misto_resumo_lbl = ctk.CTkLabel(self.v_misto_frame, text="", font=("Arial", 11, "bold"), text_color="#efe1c5", wraplength=290)
        self.v_misto_resumo_lbl.pack(padx=8, pady=(0, 8))
        self.on_pagamento_venda_change()'''
    fonte = fonte.replace(antigo, novo)

    helpers = r'''
    def base_venda_sem_taxa(self):
        subtotal = sum(float(item.get("t", 0) or 0) for item in self.carrinho)
        try:
            desconto_percentual = float(str(self.v_desc_ent.get() or "0").replace(",", "."))
        except Exception:
            desconto_percentual = 0.0
        desconto_percentual = max(0.0, min(12.0, desconto_percentual))
        desconto = subtotal * (desconto_percentual / 100)
        return max(0.0, subtotal - desconto)

    def on_pagamento_venda_change(self):
        try:
            if self.v_pag_cb.get() == "Misto":
                self.v_misto_frame.pack(fill="x", padx=6, pady=(0, 8))
            else:
                self.v_misto_frame.pack_forget()
        except Exception:
            pass
        self.render_v_car()

    def preencher_restante_pagamento_misto(self):
        if self.v_pag_cb.get() != "Misto":
            return
        base = self.base_venda_sem_taxa()
        linhas = getattr(self, "v_misto_linhas", [])
        if not linhas:
            return
        soma = 0.0
        ultimo = None
        for linha in linhas:
            valor_ent = linha.get("valor")
            valor = conv_float(valor_ent.get())
            if valor > 0:
                soma += valor
            ultimo = valor_ent
        restante = max(0.0, base - soma)
        if ultimo is not None:
            ultimo.delete(0, 'end')
            ultimo.insert(0, f"{restante:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.render_v_car()

    def coletar_pagamentos_mistos(self, mostrar_erro=False):
        if not hasattr(self, "v_pag_cb") or self.v_pag_cb.get() != "Misto":
            return None
        base = self.base_venda_sem_taxa()
        pagamentos = []
        for linha in getattr(self, "v_misto_linhas", []):
            forma = linha.get("forma").get()
            valor = conv_float(linha.get("valor").get())
            if valor > 0:
                pagamentos.append({"forma": forma, "valor": valor})
        total_pago = round(sum(p["valor"] for p in pagamentos), 2)
        falta = round(base - total_pago, 2)
        try:
            if hasattr(self, "v_misto_resumo_lbl"):
                if not pagamentos:
                    self.v_misto_resumo_lbl.configure(text=f"Total a dividir: {format_moeda(base)}")
                elif abs(falta) <= 0.01:
                    self.v_misto_resumo_lbl.configure(text=f"Pagamento fechado: {format_moeda(total_pago)}")
                elif falta > 0:
                    self.v_misto_resumo_lbl.configure(text=f"Falta dividir: {format_moeda(falta)}")
                else:
                    self.v_misto_resumo_lbl.configure(text=f"Valor acima do total: {format_moeda(abs(falta))}")
        except Exception:
            pass
        if not pagamentos:
            if mostrar_erro:
                messagebox.showwarning("Pagamento misto", "Informe ao menos uma forma e valor do pagamento misto.")
            return []
        if abs(total_pago - round(base, 2)) > 0.01:
            if mostrar_erro:
                messagebox.showwarning("Pagamento misto", f"Os valores do pagamento misto precisam somar {format_moeda(base)}. Soma atual: {format_moeda(total_pago)}.")
            return []
        return pagamentos

    def descricao_pagamento_venda(self):
        if not hasattr(self, "v_pag_cb"):
            return "Dinheiro"
        if self.v_pag_cb.get() != "Misto":
            return self.v_pag_cb.get()
        pagamentos = self.coletar_pagamentos_mistos(False) or []
        if not pagamentos:
            return "Misto"
        partes = [f"{p['forma']} {format_moeda(p['valor'])}" for p in pagamentos]
        return "Misto: " + " + ".join(partes)

'''
    fonte = fonte.replace("    def resetar_venda(self):\n", helpers + "    def resetar_venda(self):\n")

    antigo_reset = '''        if hasattr(self, "v_pag_cb"):
            self.v_pag_cb.set("Dinheiro")'''
    novo_reset = '''        if hasattr(self, "v_pag_cb"):
            self.v_pag_cb.set("Dinheiro")
        for linha in getattr(self, "v_misto_linhas", []):
            ent = linha.get("valor")
            if ent is not None:
                try:
                    ent.delete(0, 'end')
                except Exception:
                    pass
        if hasattr(self, "v_misto_resumo_lbl"):
            try:
                self.v_misto_resumo_lbl.configure(text="")
            except Exception:
                pass
        if hasattr(self, "v_misto_frame"):
            try:
                self.v_misto_frame.pack_forget()
            except Exception:
                pass'''
    fonte = fonte.replace(antigo_reset, novo_reset)

    antigo_render = '''    def render_v_car(self):
        for i in self.tree_v_car.get_children():
            self.tree_v_car.delete(i)
        self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), self.v_pag_cb.get())
        for it in self.carrinho:
            self.tree_v_car.insert("", "end", values=(it['n'], it['q'], format_moeda(it['t'])))
        self.v_total_lbl.configure(text=format_moeda(self.v_calc['tot']))'''
    novo_render = '''    def render_v_car(self):
        for i in self.tree_v_car.get_children():
            self.tree_v_car.delete(i)
        if hasattr(self, "v_pag_cb") and self.v_pag_cb.get() == "Misto":
            try:
                from services.venda_service import calcular_total_venda_misto
                pagamentos = self.coletar_pagamentos_mistos(False) or []
                self.v_calc = calcular_total_venda_misto(self.carrinho, self.v_desc_ent.get(), pagamentos)
            except Exception:
                self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), "Dinheiro")
        else:
            self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), self.v_pag_cb.get())
        for it in self.carrinho:
            self.tree_v_car.insert("", "end", values=(it['n'], it['q'], format_moeda(it['t'])))
        self.v_total_lbl.configure(text=format_moeda(self.v_calc['tot']))'''
    fonte = fonte.replace(antigo_render, novo_render)

    fonte = fonte.replace("PAGAMENTO: {self.v_pag_cb.get()}", "PAGAMENTO: {self.descricao_pagamento_venda()}")

    antigo_confirmar = '''                self.v_pag_cb.get(),
                self.current_user['nome'],
                cx_id,
            )'''
    novo_confirmar = '''                self.descricao_pagamento_venda(),
                self.current_user['nome'],
                cx_id,
                pagamentos_mistos=self.coletar_pagamentos_mistos(True),
            )'''
    fonte = fonte.replace(antigo_confirmar, novo_confirmar)

    return fonte
