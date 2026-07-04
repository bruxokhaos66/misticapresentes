def aplicar_painel_guard_runtime(fonte):
    """Protege o painel mobile quando a API online reinicia/zera."""
    if "def verificar_api_painel_mobile(self" in fonte:
        return fonte

    metodos = r'''
    def _painel_mobile_status_msg(self, texto, cor="#ffcc66"):
        try:
            self._painel_mobile_status_texto = texto
            self._painel_mobile_status_cor = cor
            if hasattr(self, "lbl_sync_status"):
                self.lbl_sync_status.configure(text=texto, text_color=cor)
        except Exception:
            pass

    def verificar_api_painel_mobile(self, contexto="automatico"):
        try:
            from datetime import datetime
            from services.painel_online_guard import INTERVALO_VERIFICACAO_SEG, proteger_api_zerada_async

            def finalizar(resultado):
                try:
                    diag = resultado.get("diagnostico") or resultado.get("diagnostico_inicial") or {}
                    motivo = str(diag.get("motivo") or "")
                    status = str(resultado.get("status") or "")
                    hora = datetime.now().strftime("%H:%M")
                    cor = "#ffcc66"
                    if status == "sincronizando":
                        if motivo == "api_zerada":
                            texto = f"Painel Mobile: API zerada - reparando automaticamente | Ultima verificacao: {hora}"
                        elif motivo == "api_incompleta":
                            texto = f"Painel Mobile: API incompleta - reparando automaticamente | Ultima verificacao: {hora}"
                        else:
                            texto = f"Painel Mobile: Sincronizando... | Ultima verificacao: {hora}"
                    elif status == "ok":
                        texto = f"Painel Mobile: OK | Ultima verificacao: {hora}"
                        cor = "#7CFC98"
                    elif status == "indisponivel" or motivo == "api_indisponivel":
                        texto = f"Painel Mobile: API indisponivel | Ultima verificacao: {hora}"
                    elif status == "parcial":
                        texto = f"Painel Mobile: API incompleta - nova tentativa em 10 min | Ultima verificacao: {hora}"
                    else:
                        texto = f"Painel Mobile: {status or 'verificacao concluida'} | Ultima verificacao: {hora}"
                    self.after(100, lambda: self._painel_mobile_status_msg(texto, cor))
                    self.after(200, self.atualizar_cards_dashboard_topo)
                except Exception:
                    pass

            iniciado = proteger_api_zerada_async(callback=finalizar, intervalo_minimo_seg=INTERVALO_VERIFICACAO_SEG, contexto=contexto)
            if iniciado:
                self._painel_mobile_status_msg("Painel Mobile: Verificando...", "#ffcc66")
        except Exception as exc:
            try:
                registrar_erro_sistema("verificar_api_painel_mobile", exc)
            except Exception:
                pass

    def agendar_verificacao_api_painel_mobile(self, primeira=False):
        try:
            if getattr(self, "_painel_mobile_auto_agendado", False) and not primeira:
                return
            self._painel_mobile_auto_agendado = True
            if primeira:
                self.verificar_api_painel_mobile("abertura")
            if getattr(self, "_painel_mobile_auto_after_id", None):
                try:
                    self.after_cancel(self._painel_mobile_auto_after_id)
                except Exception:
                    pass
            def rodada():
                try:
                    self.verificar_api_painel_mobile("periodico_10min")
                finally:
                    try:
                        self._painel_mobile_auto_after_id = self.after(600000, rodada)
                    except Exception:
                        pass
            self._painel_mobile_auto_after_id = self.after(600000, rodada)
        except Exception as exc:
            try:
                registrar_erro_sistema("agendar_verificacao_api_painel_mobile", exc)
            except Exception:
                pass

'''
    marcador = '    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---'
    if marcador in fonte:
        fonte = fonte.replace(marcador, metodos + "\n" + marcador, 1)

    alvo_abertura = '        self.sincronizar_usuarios_online("abertura")'
    if alvo_abertura in fonte and 'self.agendar_verificacao_api_painel_mobile(primeira=True)' not in fonte:
        fonte = fonte.replace(alvo_abertura, alvo_abertura + '\n        self.agendar_verificacao_api_painel_mobile(primeira=True)', 1)

    alvo_login = '            self.sincronizar_usuarios_online("login")'
    if alvo_login in fonte and 'self.agendar_verificacao_api_painel_mobile(primeira=True)' not in fonte:
        fonte = fonte.replace(alvo_login, alvo_login + '\n            self.agendar_verificacao_api_painel_mobile(primeira=True)', 1)

    alvo_venda = '            self.atualizar_painel_vendas_dia(apos_venda=True)'
    if alvo_venda in fonte and 'self.verificar_api_painel_mobile("apos_venda")' not in fonte:
        fonte = fonte.replace(alvo_venda, alvo_venda + '\n            self.verificar_api_painel_mobile("apos_venda")', 1)

    fonte = fonte.replace('text="SincronizaÃ§Ã£o: verificando..."', 'text="Painel Mobile: Verificando..."')

    alvo_status = 'self.lbl_sync_status.pack(side="right", padx=12, pady=8)'
    if alvo_status in fonte and 'self.lbl_sync_status.configure(text=self._painel_mobile_status_texto' not in fonte:
        fonte = fonte.replace(
            alvo_status,
            alvo_status + '\n        try:\n            if hasattr(self, "_painel_mobile_status_texto"):\n                self.lbl_sync_status.configure(text=self._painel_mobile_status_texto, text_color=getattr(self, "_painel_mobile_status_cor", "#ffcc66"))\n        except Exception:\n            pass',
            1,
        )

    return fonte
