def aplicar_backup_painel_runtime(fonte):
    """Adiciona helpers de backup manual e status ao app sem reescrever a tela inteira."""
    helpers = r'''
    def backup_manual_sistema(self):
        try:
            from services.backup_service import criar_backup_local
            dados = criar_backup_local("manual")
            if dados.get("ok"):
                messagebox.showinfo("Backup", "Backup criado com sucesso.")
            else:
                messagebox.showwarning("Backup", dados.get("erro", "Não foi possível criar backup."))
        except Exception as exc:
            messagebox.showerror("Backup", f"Erro ao criar backup: {exc}")

    def status_backup_sistema(self):
        try:
            from services.backup_service import ler_status
            dados = ler_status()
            if not dados:
                messagebox.showinfo("Backup", "Nenhum backup registrado ainda.")
                return
            status = "OK" if dados.get("ok") else "ERRO"
            data = dados.get("data", "-")
            motivo = dados.get("motivo", "-")
            erro = dados.get("erro", "")
            arquivos = dados.get("arquivos", []) or []
            texto = f"Status: {status}\nData: {data}\nMotivo: {motivo}\nArquivos: {len(arquivos)}"
            if erro:
                texto += f"\nErro: {erro}"
            messagebox.showinfo("Último backup", texto)
        except Exception as exc:
            messagebox.showerror("Backup", f"Erro ao consultar backup: {exc}")

    def abrir_pasta_backups_sistema(self):
        try:
            import os
            from services.backup_service import BACKUP_DIR
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(BACKUP_DIR))
        except Exception as exc:
            messagebox.showerror("Backup", f"Erro ao abrir pasta de backups: {exc}")

'''
    if "def backup_manual_sistema(self):" not in fonte:
        fonte = fonte.replace("    def resetar_venda(self):\n", helpers + "    def resetar_venda(self):\n")
    return fonte
