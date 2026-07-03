def aplicar_sync_status_runtime(fonte):
    """Ajustes leves do dashboard."""
    fonte = fonte.replace('text="Mistica Presentes", font=("Georgia", 28, "bold")', 'text="Bruxos", font=("Georgia", 28, "bold")')
    fonte = fonte.replace('carregar_mensagem_dashboard()', '__mensagem_dashboard_isis()')
    fonte = fonte.replace('mensagem_dashboard_do_dia()', '__mensagem_dashboard_isis()')
    if 'def __mensagem_dashboard_isis():' not in fonte:
        helper = '''
def __mensagem_dashboard_isis():
    try:
        from services.dashboard_message_service import mensagem_atual
        return mensagem_atual()
    except Exception:
        try:
            return mensagem_dashboard_do_dia()
        except Exception:
            return "Atenda com presença, organize com cuidado e venda com verdade."

'''
        marcador = '# VERSÃO AUDITADA'
        if marcador in fonte:
            fonte = fonte.replace(marcador, helper + marcador, 1)
    return fonte
