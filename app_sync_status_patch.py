def aplicar_sync_status_runtime(fonte):
    """Ajuste seguro do dashboard."""
    fonte = fonte.replace('text="Mistica Presentes", font=("Georgia", 28, "bold")', 'text="Bruxos", font=("Georgia", 28, "bold")')
    return fonte
