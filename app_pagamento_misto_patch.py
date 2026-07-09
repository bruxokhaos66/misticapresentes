def aplicar_pagamento_misto_runtime(fonte: str) -> str:
    """Adiciona pagamento misto profissional, valor recebido e troco na tela de vendas."""
    try:
        from app_sync_pagamento_misto_payload_patch import aplicar_sync_pagamento_misto_payload_runtime
        fonte = aplicar_sync_pagamento_misto_payload_runtime(fonte)
    except Exception as exc:
        print(f"[Patch Pagamento Misto Sync] {exc}")

    antigo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))'''
    novo = '''        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x", "Misto"], command=lambda e: self.on_pagamento_venda_change(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))

        self.v_dinheiro_frame = ctk.CTkFrame(corpo_checkout, fg_color="#241d2b", corner_radius=10)
        ctk.CTkLabel(self.v_dinheiro_frame, text="Dinheiro recebido", font=self.font_label, text_color=self.cor_ouro).pack(pady=(6, 2))
        self.v_recebido_ent = ctk.CTkEntry(self.v_dinheiro_frame, placeholder_text="Valor recebido pelo cliente", height=34, font=self.font_input)
        self.v_recebido_ent.pack(fill="x", padx=8, pady=(2, 4))
        self.v_recebido_ent.bind("<KeyRelease>", lambda e: self.render_v_car())
        self.v_troco_lbl = ctk.CTkLabel(self.v_dinheiro_frame, text="Troco: R$ 0,00", font=("Arial", 12, "bold"), text_color="#b8d986", wraplength=290)
        self.v_troco_lbl.pack(padx=8, pady=(0, 8))

        self.v_misto_frame = ctk.CTkFrame(corpo_checkout, fg_color="#241d2b", corner_radius=10)
        ctk.CTkLabel(self.v_misto_frame, text="Pagamento misto", font=self.font_label, text_color=self.cor_ouro).pack(pady=(6, 2))
        ctk.CTkLabel(self.v_misto_frame, text="Informe o valor que o cliente vai pagar em cada forma. Cartão deve incluir a taxa.", font=("Arial", 11, "bold"), text_color="#d8cbb6", wraplength=290).pack(pady=(0, 4))

        self.v_misto_linhas = []
        formas_mistas = ["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"]
        sugestoes = ["Dinheiro", "Pix", "Debito", "Credito 1x"]
        for indice in range(4):
            linha = ctk.CTkFrame(self.v_misto_frame, fg_color="transparent")
            linha.pack(fill="x", padx=8, pady=2)
            forma = ctk.CTkOptionMenu(linha, values=formas_mistas, command=lambda e: self.render_v_car(), width=132, height=32, font=self.font_button, dropdown_font=self.font_input)
            forma.set(sugestoes[indice])
            forma.pack(side="left", padx=(0, 5))
            valor = ctk.CTkEntry(linha, placeholder_text=f"Valor pago {indice + 1}", height=32, font=self.font_input)
            valor.pack(side="left", fill="x", expand=True)
            valor.bind("<KeyRelease>", lambda e: self.render_v_car())
            self.v_misto_linhas.append({"forma": forma, "valor": valor})

        ctk.CTkButton(self.v_misto_frame, text="COMPLETAR RESTANTE", height=32, font=("Arial", 12, "bold"), fg_color="#5f7f4c", command=self.preencher_restante_pagamento_misto).pack(fill="x", padx=8, pady=(4, 8))
        self.v_misto_resumo_lbl = ctk.CTkLabel(self.v_misto_frame, text="", font=("Arial", 11, "bold"), text_color="#efe1c5", wraplength=290)
        self.v_misto_resumo_lbl.pack(padx=8, pady=(0, 8))
        self.on_pagamento_venda_change()'''
    fonte = fonte.replace(antigo, novo)

    helpers = r'''
    def base_venda_sem_taxa(self):
        subtotal = sum(float(item.get("t", 0) or 0) for item in self.carrinho)
        try:
            desconto_percentual = conv_float(self.v_desc_ent.get() or "0")
        except Exception:
            desconto_percentual = 0.0
        desconto_percentual = max(0.0, min(12.0, desconto_percentual))
        desconto = subtotal * (desconto_percentual / 100)
        return max(0.0, subtotal - desconto)

    def taxa_forma_misto(self, forma, valor=1):
        forma_txt = str(forma or "")
        valor = float(valor or 0)
        if valor <= 0:
            return 0.0
        if "Debito" in forma_txt or "Débito" in forma_txt:
            return 1.50
        if "Credito 1x" in forma_txt or "Crédito 1x" in forma_txt:
            return 1.50
        if "Credito 2x" in forma_txt or "Crédito 2x" in forma_txt:
            return 2.00
        if "Credito 3x" in forma_txt or "Crédito 3x" in forma_txt:
            return 2.50
        return 0.0

    def pagamentos_mistos_brutos(self):
        pagamentos = []
        for linha in getattr(self, "v_misto_linhas", []):
            forma = linha.get("forma").get()
            valor = conv_float(linha.get("valor").get())
            if valor > 0:
                pagamentos.append({"forma": forma, "valor": valor})
        return pagamentos

    def total_taxas_misto(self, pagamentos=None):
        pagamentos = pagamentos if pagamentos is not None else self.pagamentos_mistos_brutos()
        return round(sum(self.taxa_forma_misto(p["forma"], p["valor"]) for p in pagamentos), 2)

    def total_final_misto(self, pagamentos=None):
        base = self.base_venda_sem_taxa()
        taxas = self.total_taxas_misto(pagamentos)
        return round(base + taxas, 2)

    def on_pagamento_venda_change(self):
        try:
            forma = self.v_pag_cb.get()
            if forma == "Misto":
                self.v_misto_frame.pack(fill="x", padx=6, pady=(0, 8))
            else:
                self.v_misto_frame.pack_forget()
            if forma == "Dinheiro":
                self.v_dinheiro_frame.pack(fill="x", padx=6, pady=(0, 8))
            else:
                self.v_dinheiro_frame.pack_forget()
        except Exception:
            pass
        self.render_v_car()

    def valor_recebido_dinheiro(self):
        try:
            return max(0.0, conv_float(self.v_recebido_ent.get()))
        except Exception:
            return 0.0

    def troco_dinheiro(self):
        total = float(getattr(self, "v_calc", {}).get("tot", 0) or 0)
        recebido = self.valor_recebido_dinheiro()
        if recebido <= 0:
            return 0.0
        return round(recebido - total, 2)

    def atualizar_troco_dinheiro(self):
        try:
            if not hasattr(self, "v_troco_lbl"):
                return
            if self.v_pag_cb.get() != "Dinheiro":
                return
            recebido = self.valor_recebido_dinheiro()
            total = float(getattr(self, "v_calc", {}).get("tot", 0) or 0)
            if recebido <= 0:
                self.v_troco_lbl.configure(text="Troco: R$ 0,00", text_color="#b8d986")
            elif recebido < total:
                self.v_troco_lbl.configure(text=f"Falta receber: {format_moeda(total - recebido)}", text_color="#ff8a8a")
            else:
                self.v_troco_lbl.configure(text=f"Troco: {format_moeda(recebido - total)}", text_color="#b8d986")
        except Exception:
            pass

    def validar_troco_dinheiro(self):
        if not hasattr(self, "v_pag_cb") or self.v_pag_cb.get() != "Dinheiro":
            return True
        recebido = self.valor_recebido_dinheiro()
        if recebido <= 0:
            return True
        total = float(getattr(self, "v_calc", {}).get("tot", 0) or 0)
        if recebido + 0.01 < total:
            messagebox.showwarning("Dinheiro recebido", f"A venda não será finalizada. Ainda falta receber {format_moeda(total - recebido)}.")
            return False
        return True

    def preencher_restante_pagamento_misto(self):
        if self.v_pag_cb.get() != "Misto":
            return
        linhas = getattr(self, "v_misto_linhas", [])
        if not linhas:
            return
        alvo_indice = len(linhas) - 1
        for idx, linha in enumerate(linhas):
            valor_ent = linha.get("valor")
            if idx < len(linhas) - 1 and conv_float(valor_ent.get()) <= 0:
                alvo_indice = idx
                break
        outros = []
        soma_outros = 0.0
        for idx, linha in enumerate(linhas):
            if idx == alvo_indice:
                continue
            forma = linha.get("forma").get()
            valor_ent = linha.get("valor")
            valor = max(0.0, conv_float(valor_ent.get()))
            if valor > 0:
                outros.append({"forma": forma, "valor": valor})
                soma_outros += valor
        forma_alvo = linhas[alvo_indice].get("forma").get()
        taxa_alvo = self.taxa_forma_misto(forma_alvo, 1)
        taxas_outros = self.total_taxas_misto(outros)
        total_final_estimado = round(self.base_venda_sem_taxa() + taxas_outros + taxa_alvo, 2)
        restante = max(0.0, total_final_estimado - soma_outros)
        alvo = linhas[alvo_indice].get("valor")
        if alvo is not None:
            alvo.delete(0, 'end')
            alvo.insert(0, f"{restante:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.render_v_car()

    def coletar_pagamentos_mistos(self, mostrar_erro=False):
        if not hasattr(self, "v_pag_cb") or self.v_pag_cb.get() != "Misto":
            return None
        base = self.base_venda_sem_taxa()
        pagamentos = self.pagamentos_mistos_brutos()
        total_pago = round(sum(p["valor"] for p in pagamentos), 2)
        taxas = self.total_taxas_misto(pagamentos)
        total_final = round(base + taxas, 2)
        falta = round(total_final - total_pago, 2)
        try:
            if hasattr(self, "v_misto_resumo_lbl"):
                resumo_base = f"Compra: {format_moeda(base)} | Taxas: {format_moeda(taxas)} | Total final: {format_moeda(total_final)}"
                if not pagamentos:
                    self.v_misto_resumo_lbl.configure(text=resumo_base, text_color="#efe1c5")
                elif abs(falta) <= 0.01:
                    self.v_misto_resumo_lbl.configure(text=f"Pagamento fechado: {format_moeda(total_pago)}\n{resumo_base}", text_color="#b8d986")
                elif falta > 0:
                    self.v_misto_resumo_lbl.configure(text=f"Falta receber: {format_moeda(falta)}\n{resumo_base}", text_color="#ffd27f")
                else:
                    self.v_misto_resumo_lbl.configure(text=f"Valor acima do total: {format_moeda(abs(falta))}\n{resumo_base}", text_color="#ff8a8a")
        except Exception:
            pass
        if not pagamentos:
            if mostrar_erro:
                messagebox.showwarning("Pagamento misto", "Informe ao menos uma forma e valor do pagamento misto.")
            return []
        if abs(total_pago - total_final) > 0.01:
            if mostrar_erro:
                if falta > 0:
                    messagebox.showwarning("Pagamento misto", f"A venda não será finalizada. Ainda falta receber {format_moeda(falta)} incluindo as taxas do cartão.")
                else:
                    messagebox.showwarning("Pagamento misto", f"A venda não será finalizada. O pagamento está acima do total em {format_moeda(abs(falta))}.")
            return []
        return pagamentos

    def validar_pagamento_misto_fechado(self):
        if not hasattr(self, "v_pag_cb") or self.v_pag_cb.get() != "Misto":
            return True
        pagamentos = self.coletar_pagamentos_mistos(True) or []
        return bool(pagamentos)

    def descricao_pagamento_venda(self):
        if not hasattr(self, "v_pag_cb"):
            return "Dinheiro"
        if self.v_pag_cb.get() == "Dinheiro":
            recebido = self.valor_recebido_dinheiro() if hasattr(self, "valor_recebido_dinheiro") else 0.0
            troco = self.troco_dinheiro() if hasattr(self, "troco_dinheiro") else 0.0
            if recebido > 0 and troco >= 0:
                return f"Dinheiro | Recebido {format_moeda(recebido)} | Troco {format_moeda(troco)}"
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
        if hasattr(self, "v_recebido_ent"):
            try:
                self.v_recebido_ent.delete(0, 'end')
            except Exception:
                pass
        if hasattr(self, "v_troco_lbl"):
            try:
                self.v_troco_lbl.configure(text="Troco: R$ 0,00", text_color="#b8d986")
            except Exception:
                pass
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
                pass
        if hasattr(self, "v_dinheiro_frame") and hasattr(self, "v_pag_cb") and self.v_pag_cb.get() == "Dinheiro":
            try:
                self.v_dinheiro_frame.pack(fill="x", padx=6, pady=(0, 8))
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
                pagamentos = self.pagamentos_mistos_brutos() if hasattr(self, "pagamentos_mistos_brutos") else []
                self.v_calc = calcular_total_venda_misto(self.carrinho, self.v_desc_ent.get(), pagamentos)
                if hasattr(self, "coletar_pagamentos_mistos"):
                    self.coletar_pagamentos_mistos(False)
            except Exception:
                self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), "Dinheiro")
        else:
            self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), self.v_pag_cb.get())
        for it in self.carrinho:
            self.tree_v_car.insert("", "end", values=(it['n'], it['q'], format_moeda(it['t'])))
        self.v_total_lbl.configure(text=format_moeda(self.v_calc['tot']))
        if hasattr(self, "atualizar_troco_dinheiro"):
            self.atualizar_troco_dinheiro()'''
    fonte = fonte.replace(antigo_render, novo_render)

    fonte = fonte.replace("PAGAMENTO: {self.v_pag_cb.get()}", "PAGAMENTO: {self.descricao_pagamento_venda()}")

    fonte = fonte.replace('''        self.render_v_car()
        if validacao["avisos"]:''', '''        self.render_v_car()
        if hasattr(self, "validar_pagamento_misto_fechado") and not self.validar_pagamento_misto_fechado():
            return
        if hasattr(self, "validar_troco_dinheiro") and not self.validar_troco_dinheiro():
            return
        if validacao["avisos"]:''')

    fonte = fonte.replace('''        if not validacao:
            return
        data_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")''', '''        if not validacao:
            return
        if hasattr(self, "validar_pagamento_misto_fechado") and not self.validar_pagamento_misto_fechado():
            return
        if hasattr(self, "validar_troco_dinheiro") and not self.validar_troco_dinheiro():
            return
        data_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")''')

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
