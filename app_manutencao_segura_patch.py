def aplicar_manutencao_segura_runtime(fonte):
    """Adiciona aba visual de Manutencao/Seguranca para administradores."""
    metodos = r'''
    def montar_manutencao(self):
        frame = ctk.CTkFrame(self.tab_manut, fg_color=self.cor_vinho, corner_radius=18)
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(frame, text="MANUTENÇÃO E SEGURANÇA", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(18, 6))
        ctk.CTkLabel(frame, text="Backups, sincronização e ferramentas de proteção do sistema.", font=self.font_label, text_color="#efe1c5").pack(pady=(0, 18))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=24, pady=8)

        ctk.CTkButton(grid, text="FAZER BACKUP AGORA", height=44, font=self.font_button, fg_color="#5f7f4c", command=self.backup_manual_sistema).grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="VER ÚLTIMO BACKUP", height=44, font=self.font_button, fg_color=self.cor_botao, command=self.status_backup_sistema).grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="ABRIR PASTA DE BACKUPS", height=44, font=self.font_button, fg_color="#4c647f", command=self.abrir_pasta_backups_sistema).grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        ctk.CTkButton(grid, text="VER STATUS DA SINCRONIZAÇÃO", height=44, font=self.font_button, fg_color="#6f5f91", command=self.status_sincronizacao_manutencao).grid(row=1, column=0, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="RODAR SINCRONIZAÇÃO", height=44, font=self.font_button, fg_color="#7f6a4c", command=self.rodar_sincronizacao_manutencao).grid(row=1, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="VERIFICAR ATUALIZADOR", height=44, font=self.font_button, fg_color="#4c4c4c", command=self.status_atualizador_manutencao).grid(row=1, column=2, padx=8, pady=8, sticky="ew")

        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

        self.manut_status_lbl = ctk.CTkLabel(frame, text="Sistema protegido. Use os botões acima para manutenção preventiva.", font=("Arial", 14, "bold"), text_color="#d8cbb6", wraplength=900)
        self.manut_status_lbl.pack(fill="x", padx=24, pady=(18, 8))

        info = ctk.CTkFrame(frame, fg_color="#211b29", corner_radius=14)
        info.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(info, text="Recomendação: faça backup manual antes de alterações grandes, fechamento mensal ou manutenção no computador.", font=("Arial", 13, "bold"), text_color="#efe1c5", wraplength=900).pack(padx=18, pady=16)

    def status_sincronizacao_manutencao(self):
        try:
            from services.sync_service import estado_sincronizacao
            dados = estado_sincronizacao(tentar_enviar=False)
            texto = f"Status: {dados.get('status')}\nPendências: {dados.get('pendencias')}\nÚltima sincronização: {dados.get('ultima_sincronizacao')}\nAPI: {dados.get('api_url')}"
            messagebox.showinfo("Sincronização", texto)
        except Exception as exc:
            messagebox.showerror("Sincronização", f"Erro ao consultar sincronização: {exc}")

    def rodar_sincronizacao_manutencao(self):
        try:
            from services.sync_service import sincronizar_pendencias
            res = sincronizar_pendencias(limite=20)
            messagebox.showinfo("Sincronização", f"Sincronizados: {res.get('sincronizados', 0)}\nErros: {res.get('erros', 0)}")
        except Exception as exc:
            messagebox.showerror("Sincronização", f"Erro ao sincronizar: {exc}")

    def status_atualizador_manutencao(self):
        try:
            from auto_updater import detectar_windows, versao_atual_ativa
            ambiente = detectar_windows()
            texto = f"Versão ativa: {versao_atual_ativa()}\nWindows: {ambiente.get('nome')}\nBits: {ambiente.get('bits')}\nCanal: {ambiente.get('canal')}\nManifest: {ambiente.get('manifest_url')}"
            messagebox.showinfo("Atualizador", texto)
        except Exception as exc:
            messagebox.showerror("Atualizador", f"Erro ao consultar atualizador: {exc}")

'''
    if "def montar_manutencao(self):" not in fonte:
        fonte = fonte.replace("    def montar_abas(self):\n", metodos + "    def montar_abas(self):\n")

    antigo = '''            self.tab_adm = self.tabs.add("Administração")
            self.executar_montagem_segura("tab_fin", self.montar_financeiro)
            self.executar_montagem_segura("tab_r", self.montar_relatorios)
            self.executar_montagem_segura("tab_f", self.montar_fornecedores)
            self.executar_montagem_segura("tab_adm", self.montar_administracao)'''
    novo = '''            self.tab_adm = self.tabs.add("Administração")
            self.tab_manut = self.tabs.add("Manutenção")
            self.executar_montagem_segura("tab_fin", self.montar_financeiro)
            self.executar_montagem_segura("tab_r", self.montar_relatorios)
            self.executar_montagem_segura("tab_f", self.montar_fornecedores)
            self.executar_montagem_segura("tab_adm", self.montar_administracao)
            self.executar_montagem_segura("tab_manut", self.montar_manutencao)'''
    fonte = fonte.replace(antigo, novo)
    return fonte
