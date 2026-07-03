def aplicar_sync_status_runtime(fonte):
    """Ajusta o dashboard para exibir o painel automático de vendas e sincronização."""

    # Garante que o painel de vendas seja chamado no dashboard, mesmo quando
    # outros patches removem ou alteram o botão antigo de recarregar.
    if "self.montar_painel_vendas_dia(f)" not in fonte:
        botao_antigo = """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)"""
        if botao_antigo in fonte:
            fonte = fonte.replace(botao_antigo, "        self.montar_painel_vendas_dia(f)", 1)
        else:
            alvo = """        ctk.CTkLabel(f_info, text=alertas_txt, font=(\"Arial\", 13, \"bold\"), wraplength=900, justify=\"left\", text_color=\"#f0e6d2\").pack(padx=25, pady=(0, 10))"""
            fonte = fonte.replace(alvo, alvo + "\n        self.montar_painel_vendas_dia(f)", 1)

    # Remove botão manual do painel principal quando ainda existir.
    fonte = fonte.replace(
        """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)""",
        """""",
    )

    # Remove botão manual da tabela de vendas em tempo real quando ainda existir.
    fonte = fonte.replace(
        """        ctk.CTkButton(topo, text=\"ATUALIZAR\", width=130, height=34, font=self.font_button, fg_color=self.cor_botao, command=self.atualizar_painel_vendas_dia).pack(side=\"right\")\n""",
        """""",
    )

    # Ajusta atualização automática para 5 segundos, caso algum patch antigo use 30 segundos.
    fonte = fonte.replace(
        """self.after(30000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))""",
        """self.after(5000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))""",
    )

    return fonte
