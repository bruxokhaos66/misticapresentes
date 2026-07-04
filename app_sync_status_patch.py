def aplicar_sync_status_runtime(fonte):
    """Ajuste seguro do dashboard."""
    fonte = fonte.replace('text="Mistica Presentes", font=("Georgia", 28, "bold")', 'text="Bruxos", font=("Georgia", 28, "bold")')

    # Usa frases da Isis por blocos de 3 horas.
    # A frase local aparece imediatamente. A busca online roda em segundo plano.
    fonte = fonte.replace('carregar_mensagem_dashboard()', 'mensagem_dashboard_isis_runtime()')
    fonte = fonte.replace('text=f\'"{mensagem_dashboard_do_dia()}"\'', 'text=f\'"{mensagem_dashboard_isis_runtime()}"\'')
    fonte = fonte.replace('text=f"{mensagem_dashboard_do_dia()}"', 'text=f"{mensagem_dashboard_isis_runtime()}"')

    if 'def mensagem_dashboard_isis_runtime():' not in fonte:
        helper = '''
def mensagem_dashboard_isis_runtime():
    try:
        from services.dashboard_message_service import mensagem_atual
        return mensagem_atual()
    except Exception:
        return "Atenda com presença, organize com cuidado e venda com verdade."

'''
        marcador = '# VERSÃO AUDITADA'
        if marcador in fonte:
            fonte = fonte.replace(marcador, helper + marcador, 1)

    # Atualiza a frase a cada 3 horas e deixa a Isis buscar uma opção online sem travar a tela.
    alvo = '        self.dashboard_msg_lbl.pack(pady=10)'
    novo = '''        self.dashboard_msg_lbl.pack(pady=10)
        try:
            from services.dashboard_message_service import buscar_online_em_background
            def aplicar_frase_online(msg):
                try:
                    self.after(0, lambda: self.dashboard_msg_lbl.configure(text='"' + str(msg) + '"'))
                except Exception:
                    pass
            buscar_online_em_background(aplicar_frase_online)
            if not getattr(self, "_frase_dashboard_3h_agendada", False):
                self._frase_dashboard_3h_agendada = True
                self.after(10800000, self.montar_dashboard)
        except Exception:
            pass'''
    if alvo in fonte and 'buscar_online_em_background' not in fonte:
        fonte = fonte.replace(alvo, novo, 1)

    try:
        from app_painel_guard_patch import aplicar_painel_guard_runtime
        fonte = aplicar_painel_guard_runtime(fonte)
    except Exception:
        pass

    return fonte
