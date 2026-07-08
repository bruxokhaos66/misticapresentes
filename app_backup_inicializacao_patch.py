def aplicar_backup_inicializacao_runtime(fonte):
    """Executa backup diario ao iniciar o sistema, sem travar a tela principal."""
    trecho = '''
try:
    import threading
    from services.backup_service import backup_ao_iniciar
    threading.Thread(target=backup_ao_iniciar, daemon=True).start()
except Exception as exc:
    print(f"[Backup Inicializacao] {exc}")
'''
    if "[Backup Inicializacao]" in fonte:
        return fonte
    return trecho + "\n" + fonte
