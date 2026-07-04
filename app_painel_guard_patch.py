def aplicar_painel_guard_runtime(fonte):
    """Protege o painel mobile quando a API online reinicia/zera."""
    if "def verificar_api_painel_mobile(self" in fonte:
        return fonte

    metodos = r'''
    def _painel_mobile_status_msg(self, texto, cor="#ffcc66"):
        try:
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=texto, text_color=cor)
        except Exception:
            pass

    def verificar_api_painel_mobile(self, contexto="manual", forcar=False):
        try:
            from services.painel_online_guard import proteger_api_zerada_async, resultado_resumido, sincronizar_painel_completo
            import threading

            def finalizar(resultado):
                try:
                    resumo = resultado_resumido(resultado)
                    cor = "#7CFC98" if str(resultado.get("status")) == "ok" else "#ffcc66"
                    self.after(100, lambda: self._painel_mobile_status_msg("Painel mobile: " + resumo, cor))
                    self.after(200, self.atualizar_cards_dashboard_topo)
                except Exception:
                    pass

            if forcar:
                self._painel_mobile_status_msg("Painel mobile: sincronizando tudo agora...", "#ffcc66")
                def executar_forcado():
                    resultado = sincronizar_painel_completo()
                    finalizar(resultado)
                threading.Thread(target=executar_forcado, daemon=True).start()
                return

            iniciado = proteger_api_zerada_async(callback=finalizar, intervalo_minimo_seg=60)
            if iniciado:
                self._painel_mobile_status_msg("Painel mobile: conferindo API online...", "#ffcc66")
        except Exception as exc:
            try:
                registrar_erro_sistema("verificar_api_painel_mobile", exc)
            except Exception:
                pass

'''
    marcador = '    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---'
    if marcador in fonte:
        fonte = fonte.replace(marcador, metodos + "\n" + marcador, 1)

    alvo_login = '            self.sincronizar_usuarios_online("login")'
    if alvo_login in fonte and 'self.verificar_api_painel_mobile("login")' not in fonte:
        fonte = fonte.replace(alvo_login, alvo_login + '\n            self.verificar_api_painel_mobile("login")', 1)

    alvo_venda = '            self.atualizar_painel_vendas_dia(apos_venda=True)'
    if alvo_venda in fonte and 'self.verificar_api_painel_mobile("apos_venda")' not in fonte:
        fonte = fonte.replace(alvo_venda, alvo_venda + '\n            self.verificar_api_painel_mobile("apos_venda")', 1)

    alvo_status = 'self.lbl_sync_status.pack(side="right", padx=12, pady=8)'
    if alvo_status in fonte and 'Reparar API / Painel Mobile' not in fonte:
        fonte = fonte.replace(
            alvo_status,
            alvo_status + '\n        ctk.CTkButton(topo, text="Reparar API / Painel Mobile", height=30, font=("Arial", 11, "bold"), fg_color="#4f835f", command=lambda: self.verificar_api_painel_mobile("botao", forcar=True)).pack(side="right", padx=8, pady=6)',
            1,
        )

    return fonte
