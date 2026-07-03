def aplicar_sync_status_runtime(fonte):
    """Ajusta o dashboard para sincronização automática sem botões manuais."""

    # Remove botão manual do painel principal. O dashboard passa a atualizar sozinho.
    fonte = fonte.replace(
        """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)""",
        """ctk.CTkLabel(f_info, text=\"Painel atualizado automaticamente.\", font=(\"Arial\", 12, \"bold\"), text_color=self.cor_ouro).pack(pady=8)""",
    )

    # Remove botão manual da tabela de vendas em tempo real.
    fonte = fonte.replace(
        """        ctk.CTkButton(topo, text=\"ATUALIZAR\", width=130, height=34, font=self.font_button, fg_color=self.cor_botao, command=self.atualizar_painel_vendas_dia).pack(side=\"right\")\n""",
        """""",
    )

    # Atualiza o painel de vendas automaticamente a cada 5 segundos.
    fonte = fonte.replace(
        """self.after(30000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))""",
        """self.after(5000, lambda: (self.atualizar_painel_vendas_dia(), self.agendar_atualizacao_painel_vendas_dia()))""",
    )

    # Garante barra de rolagem vertical na tabela de vendas em tempo real.
    fonte = fonte.replace(
        """        self.tree_vendas_dia = ttk.Treeview(bloco, columns=(\"hora\", \"usuario\", \"produto\", \"qtd\", \"valor\", \"venda\"), show=\"headings\", height=8)""",
        """        frame_tree_vendas = ctk.CTkFrame(bloco, fg_color=\"transparent\")
        frame_tree_vendas.pack(fill=\"both\", expand=True, padx=8, pady=(0, 8))
        self.tree_vendas_dia = ttk.Treeview(frame_tree_vendas, columns=(\"hora\", \"usuario\", \"produto\", \"qtd\", \"valor\", \"venda\"), show=\"headings\", height=8)
        scroll_vendas_y = ttk.Scrollbar(frame_tree_vendas, orient=\"vertical\", command=self.tree_vendas_dia.yview)
        self.tree_vendas_dia.configure(yscrollcommand=scroll_vendas_y.set)""",
    )
    fonte = fonte.replace(
        """        self.tree_vendas_dia.pack(fill=\"both\", expand=True, padx=8, pady=(0, 8))""",
        """        self.tree_vendas_dia.pack(side=\"left\", fill=\"both\", expand=True)
        scroll_vendas_y.pack(side=\"right\", fill=\"y\")""",
    )

    # Insere o status de sincronização dentro do painel de vendas, logo no topo.
    if "def montar_status_sincronizacao(self" not in fonte:
        alvo_topo_painel = """        nome_usuario = self.current_user.get(\"nome\", \"Sistema\") if isinstance(self.current_user, dict) else \"Sistema\""" 
        fonte = fonte.replace(
            alvo_topo_painel,
            """        self.montar_status_sincronizacao(self.frame_vendas_dia)\n\n""" + alvo_topo_painel,
            1,
        )

        marcador = "    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---"
        metodos = r'''
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
        self.frame_sync_status.pack(fill="x", padx=10, pady=(2, 8))

        self.lbl_sync_status = ctk.CTkLabel(
            self.frame_sync_status,
            text="Sincronização: verificando... | Pendências: 0 | Última sincronização: --",
            font=("Arial", 14, "bold"),
            text_color=self.cor_ouro,
            anchor="center",
        )
        self.lbl_sync_status.pack(fill="x", padx=14, pady=8)

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
            texto = f"Sincronização: {status} | Pendências: {pendencias} | Última sincronização: {ultima}"
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=texto, text_color=cor)
        except Exception as exc:
            try:
                if hasattr(self, "lbl_sync_status"):
                    self.lbl_sync_status.configure(
                        text="Sincronização: Offline | Pendências: verificar | Última sincronização: indisponível",
                        text_color="#ff6b6b",
                    )
            except Exception:
                pass
            try:
                registrar_erro_sistema("status_sincronizacao", exc)
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
                self._sync_status_after_id = self.after(
                    5000,
                    lambda: (self.atualizar_status_sincronizacao(), self.agendar_status_sincronizacao())
                )
        except Exception:
            pass

'''
        if marcador in fonte:
            fonte = fonte.replace(marcador, metodos + marcador, 1)
    return fonte
