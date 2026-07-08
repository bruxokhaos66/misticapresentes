def aplicar_pagamento_misto_runtime(fonte: str) -> str:
    """Adiciona pagamento misto na tela de vendas sem reescrever o app inteiro."""

    antigo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))'''
    novo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x", "Misto"], command=lambda e: self.on_pagamento_venda_change(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))

        self.v_misto_frame = ctk.CTkFrame(corpo_checkout, fg_color="#241d2b", corner_radius=10)
        ctk.CTkLabel(self.v_misto_frame, text="Pagamento misto", font=self.font_label, text_color=self.cor_ouro).pack(pady=(6, 2))
        ctk.CTkLabel(self.v_misto_frame, text="Informe como o cliente vai dividir o valor da venda.", font=("Arial", 11, "bold"), text_color="#d8cbb6").pack(pady=(0, 4))
        linha_m1 = ctk.CTkFrame(self.v_misto_frame, fg_color="transparent")
        linha_m1.pack(fill="x", padx=8, pady=2)
        self.v_misto_forma1 = ctk.CTkOptionMenu(linha_m1, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), width=142, height=34, font=self.font_button, dropdown_font=self.font_input)
        self.v_misto_forma1.pack(side="left", padx=(0, 5))
        self.v_misto_valor1 = ctk.CTkEntry(linha_m1, placeholder_text="Valor 1", height=34, font=self.font_input)
        self.v_misto_valor1.pack(side="left", fill="x", expand=True)
        self.v_misto_valor1.bind("<KeyRelease>", lambda e: self.render_v_car())
        linha_m2 = ctk.CTkFrame(self.v_misto_frame, fg_color="transparent")
        linha_m2.pack(fill="x", padx=8, pady=2)
        self.v_misto_forma2 = ctk.CTkOptionMenu(linha_m2, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), width=142, height=34, font=self.font_button, dropdown_font=self.font_input)
        self.v_misto_forma2.set("Debito")
        self.v_misto_forma2.pack(side="left", padx=(0, 5))
        self.v_misto_valor2 = ctk.CTkEntry(linha_m2, placeholder_text="Valor 2 / restante", height=34, font=self.font_input)
        self.v_misto_valor2.pack(side="left", fill="x", expand=True)
        self.v_misto_valor2.bind("<KeyRelease>", lambda e: self.render_v_car())
        ctk.CTkButton(self.v_misto_frame, text="USAR RESTANTE NO VALOR 2", height=32, font=("Arial", 12, "bold"), fg_color="#5f7f4c", command=self.preencher_restante_pagamento_misto).pack(fill="x", padx=8, pady=(4, 8))
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
        valor1 = conv_float(self.v_misto_valor1.get())
        restante = max(0.0, base - valor1)
        self.v_misto_valor2.delete(0, 'end')
        self.v_misto_valor2.insert(0, f"{restante:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.render_v_car()

    def coletar_pagamentos_mistos(self, mostrar_erro=False):
        if not hasattr(self, "v_pag_cb") or self.v_pag_cb.get() != "Misto":
            return None
        base = self.base_venda_sem_taxa()
        forma1 = self.v_misto_forma1.get()
        forma2 = self.v_misto_forma2.get()
        valor1 = conv_float(self.v_misto_valor1.get())
        valor2 = conv_float(self.v_misto_valor2.get())
        if valor1 > 0 and valor2 <= 0:
            valor2 = max(0.0, base - valor1)
            self.v_misto_valor2.delete(0, 'end')
            self.v_misto_valor2.insert(0, f"{valor2:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        pagamentos = []
        if valor1 > 0:
            pagamentos.append({"forma": forma1, "valor": valor1})
        if valor2 > 0:
            pagamentos.append({"forma": forma2, "valor": valor2})
        total_pago = round(sum(p["valor"] for p in pagamentos), 2)
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
        for nome_ent in ["v_misto_valor1", "v_misto_valor2"]:
            ent = getattr(self, nome_ent, None)
            if ent is not None:
                try:
                    ent.delete(0, 'end')
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
