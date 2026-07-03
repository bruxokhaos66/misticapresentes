def aplicar_sync_status_runtime(fonte):
    """Ajuste seguro do dashboard."""
    fonte = fonte.replace('text="Mistica Presentes", font=("Georgia", 28, "bold")', 'text="Bruxos", font=("Georgia", 28, "bold")')

    # Usa frases locais da Isis por blocos de 3 horas, sem busca online.
    fonte = fonte.replace('carregar_mensagem_dashboard()', 'mensagem_dashboard_isis_runtime()')
    fonte = fonte.replace('mensagem_dashboard_do_dia()', 'mensagem_dashboard_isis_runtime()')

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

    # Agenda a remontagem do dashboard a cada 3 horas para trocar a frase local.
    alvo = '        self.dashboard_msg_lbl.pack(pady=10)'
    novo = '        self.dashboard_msg_lbl.pack(pady=10)\n        try:\n            self.after(10800000, self.montar_dashboard)\n        except Exception:\n            pass'
    if alvo in fonte and '10800000, self.montar_dashboard' not in fonte:
        fonte = fonte.replace(alvo, novo, 1)

    return fonte
