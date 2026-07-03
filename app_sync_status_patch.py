def aplicar_sync_status_runtime(fonte):
    """Injeta o status de sincronização online no dashboard do app."""
    if "def montar_status_sincronizacao(self" in fonte:
        return fonte

    alvo_dashboard = "        self.montar_painel_vendas_dia(f)"
    if alvo_dashboard in fonte:
        fonte = fonte.replace(
            alvo_dashboard,
            alvo_dashboard + "\n        self.montar_status_sincronizacao(f)",
            1,
        )
    else:
        botao = """ctk.CTkButton(f_info, text=\"RECARREGAR INFORMACOES DO PAINEL\", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)"""
        fonte = fonte.replace(
            botao,
            botao + "\n        self.montar_status_sincronizacao(f)",
            1,
        )

    marcador = "    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---"
    metodos = r'''
    def montar_status_sincronizacao(self, parent=None):
        if parent is None:
            parent = getattr(self, "tab_d", None)
        if parent is None:
            return

        if hasattr(self, "frame_sync_status"):
            try:
                self.frame_sync_status.destroy()
            except Exception:
                pass

        self.frame_sync_status = ctk.CTkFrame(parent, fg_color="#18121f", corner_radius=12)
        try:
            self.frame_sync_status.grid(row=3, column=0, columnspan=5, padx=10, pady=(0, 10), sticky="ew")
        except Exception:
            self.frame_sync_status.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_sync_status = ctk.CTkLabel(
            self.frame_sync_status,
            text="Sincronização: verificando... | Pendências: 0 | Última sincronização: --",
            font=("Arial", 14, "bold"),
            text_color=self.cor_ouro,
            anchor="w",
        )
        self.lbl_sync_status.pack(fill="x", padx=14, pady=10)

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
