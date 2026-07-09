def aplicar_manutencao_segura_runtime(fonte):
    """Adiciona aba visual de Manutencao/Seguranca para administradores."""
    metodos = r'''
    def montar_manutencao(self):
        frame = ctk.CTkFrame(self.tab_manut, fg_color=self.cor_vinho, corner_radius=18)
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(frame, text="MANUTENÇÃO E SEGURANÇA", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(18, 6))
        ctk.CTkLabel(frame, text="Backups, sincronização, atualizações, limpeza de testes e ferramentas de proteção do sistema.", font=self.font_label, text_color="#efe1c5").pack(pady=(0, 18))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=24, pady=8)

        ctk.CTkButton(grid, text="FAZER BACKUP AGORA", height=44, font=self.font_button, fg_color="#5f7f4c", command=self.backup_manual_sistema).grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="VER ÚLTIMO BACKUP", height=44, font=self.font_button, fg_color=self.cor_botao, command=self.status_backup_sistema).grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="ABRIR PASTA DE BACKUPS", height=44, font=self.font_button, fg_color="#4c647f", command=self.abrir_pasta_backups_sistema).grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        ctk.CTkButton(grid, text="VER STATUS DA SINCRONIZAÇÃO", height=44, font=self.font_button, fg_color="#6f5f91", command=self.status_sincronizacao_manutencao).grid(row=1, column=0, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="RODAR SINCRONIZAÇÃO", height=44, font=self.font_button, fg_color="#7f6a4c", command=self.rodar_sincronizacao_manutencao).grid(row=1, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(grid, text="VERSÃO E NOTAS DA ATUALIZAÇÃO", height=44, font=self.font_button, fg_color="#4c4c4c", command=self.status_atualizador_manutencao).grid(row=1, column=2, padx=8, pady=8, sticky="ew")

        ctk.CTkButton(grid, text="PREPARAR SISTEMA PARA PRODUÇÃO", height=48, font=self.font_button, fg_color="#8a3434", hover_color="#a94040", command=self.preparar_sistema_producao_manutencao).grid(row=2, column=0, columnspan=3, padx=8, pady=(14, 8), sticky="ew")

        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

        self.manut_status_lbl = ctk.CTkLabel(frame, text="Sistema protegido. Use os botões acima para manutenção preventiva.", font=("Arial", 14, "bold"), text_color="#d8cbb6", wraplength=900)
        self.manut_status_lbl.pack(fill="x", padx=24, pady=(18, 8))

        info = ctk.CTkFrame(frame, fg_color="#211b29", corner_radius=14)
        info.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(info, text="Produção: use 'Preparar Sistema para Produção' apenas uma vez, antes de começar os cadastros e vendas reais. O sistema cria backup antes de limpar os dados de teste.", font=("Arial", 13, "bold"), text_color="#efe1c5", wraplength=900).pack(padx=18, pady=16)

    def preparar_sistema_producao_manutencao(self):
        try:
            aviso = (
                "Esta ação prepara o sistema para uso real da loja.\n\n"
                "Ela vai criar um BACKUP automático e apagar dados de teste como vendas, caixa, fluxo, contas, clientes, fornecedores, logs e movimentações.\n\n"
                "Use somente se você já terminou os testes."
            )
            if not messagebox.askyesno("Preparar sistema para produção", aviso):
                return

            dialog = ctk.CTkInputDialog(text="Para confirmar a limpeza, digite exatamente: CONFIRMAR", title="Confirmação obrigatória")
            confirmacao = (dialog.get_input() or "").strip().upper()
            if confirmacao != "CONFIRMAR":
                messagebox.showinfo("Cancelado", "Limpeza cancelada. Nenhum dado foi apagado.")
                return

            remover_produtos = messagebox.askyesno(
                "Produtos de teste",
                "Deseja APAGAR também os produtos cadastrados para teste?\n\n"
                "Sim = apagar produtos fictícios e começar do zero.\n"
                "Não = manter produtos cadastrados e apenas zerar o estoque."
            )
            remover_clientes = messagebox.askyesno("Clientes de teste", "Deseja apagar os clientes cadastrados para teste?")
            remover_fornecedores = messagebox.askyesno("Fornecedores de teste", "Deseja apagar os fornecedores cadastrados para teste?")
            limpar_memoria_isis = messagebox.askyesno("Memória da Isis", "Deseja limpar também a memória/aprendizados de teste da Isis?\n\nSe estiver em dúvida, clique em Não.")

            operador = "Sistema"
            try:
                operador = self.current_user.get('nome') or self.current_user.get('login') or "Sistema"
            except Exception:
                pass

            from services.producao_service import preparar_sistema_para_producao
            res = preparar_sistema_para_producao(
                operador=operador,
                remover_produtos=remover_produtos,
                remover_clientes=remover_clientes,
                remover_fornecedores=remover_fornecedores,
                limpar_memoria_isis=limpar_memoria_isis,
            )

            resumo = (
                "Sistema preparado para produção com sucesso.\n\n"
                f"Backup criado:\n{res.get('backup')}\n\n"
                f"Relatório:\n{res.get('relatorio')}\n\n"
                f"Registros removidos: {res.get('total_removido')}\n\n"
                "Feche e abra o sistema novamente antes de cadastrar os dados reais."
            )
            try:
                self.manut_status_lbl.configure(text="Sistema preparado para produção. Reinicie antes de iniciar os cadastros reais.", text_color="#b8d986")
            except Exception:
                pass
            messagebox.showinfo("Preparação concluída", resumo)
            try:
                import os
                os.startfile(res.get('relatorio'))
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Preparar produção", f"Erro ao preparar sistema para produção: {exc}")

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

    def _release_notes_locais(self):
        dados = {}
        try:
            from auto_updater import CURRENT_PATH, STATUS_PATH, ler_json
            dados = ler_json(CURRENT_PATH) or {}
            if not dados:
                dados = ler_json(STATUS_PATH) or {}
        except Exception:
            dados = {}
        try:
            import release_notes
            if not dados.get("title"):
                dados["title"] = getattr(release_notes, "RELEASE_TITLE", "")
            if not dados.get("notes"):
                dados["notes"] = getattr(release_notes, "RELEASE_NOTES", "")
            if not dados.get("changes"):
                dados["changes"] = getattr(release_notes, "RELEASE_CHANGES", [])
        except Exception:
            pass
        return dados

    def status_atualizador_manutencao(self):
        try:
            from auto_updater import detectar_windows, versao_atual_ativa
            ambiente = detectar_windows()
            notas = self._release_notes_locais()
            titulo = notas.get("title") or "Atualização Mística Presentes"
            resumo = notas.get("notes") or "Nenhuma nota registrada para esta versão."
            mudancas = notas.get("changes") or []
            if isinstance(mudancas, str):
                mudancas = [mudancas]

            win = ctk.CTkToplevel(self)
            win.title("Versão e notas da atualização")
            win.geometry("760x620")
            win.grab_set()

            box = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=16)
            box.pack(fill="both", expand=True, padx=16, pady=16)
            ctk.CTkLabel(box, text="VERSÃO E NOTAS DA ATUALIZAÇÃO", font=("Georgia", 24, "bold"), text_color=self.cor_ouro).pack(pady=(14, 6))

            texto = ctk.CTkTextbox(box, font=("Arial", 14, "bold"), fg_color="#fff9e6", text_color="#111111")
            texto.pack(fill="both", expand=True, padx=14, pady=12)

            conteudo = ""
            conteudo += f"Versão ativa: {versao_atual_ativa()}\n"
            conteudo += f"Windows: {ambiente.get('nome')}\n"
            conteudo += f"Bits: {ambiente.get('bits')}\n"
            conteudo += f"Canal: {ambiente.get('canal')}\n"
            conteudo += f"Manifest: {ambiente.get('manifest_url')}\n"
            conteudo += f"Fallback: {ambiente.get('manifest_url_fallback')}\n"
            conteudo += "\n"
            conteudo += f"Título: {titulo}\n\n"
            conteudo += f"Resumo:\n{resumo}\n\n"
            conteudo += "O que foi atualizado:\n"
            if mudancas:
                for item in mudancas:
                    conteudo += f"- {item}\n"
            else:
                conteudo += "- Nenhuma alteração detalhada registrada.\n"

            texto.insert("0.0", conteudo)
            texto.configure(state="disabled")
            ctk.CTkButton(box, text="FECHAR", height=42, font=self.font_button, fg_color=self.cor_botao, command=win.destroy).pack(fill="x", padx=14, pady=(0, 14))
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
