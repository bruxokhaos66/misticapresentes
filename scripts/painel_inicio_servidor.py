"""Janela de inicio do servidor do app Mística Presentes.

Uso recomendado no começo do dia:
    python scripts\painel_inicio_servidor.py

A janela inicia a API local, mostra o endereço para o celular/app e permite
copiar o token salvo localmente. O token nunca é salvo no GitHub; ele fica em:
    Documents\Mistica_Servidor_Dedicado\api_token.txt
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path.home() / "Documents" / "Mistica_Servidor_Dedicado"
TOKEN_FILE = CONFIG_DIR / "api_token.txt"
PORT = os.getenv("MISTICA_SERVER_PORT", "8000")
HOST = os.getenv("MISTICA_SERVER_HOST", "0.0.0.0")


class PainelServidor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mística Presentes - Servidor do App")
        self.geometry("720x500")
        self.minsize(680, 460)
        self.configure(bg="#151018")
        self.processo: subprocess.Popen | None = None
        self.token = gerar_ou_ler_token()
        self.ip = ip_local()
        self.url_local = f"http://127.0.0.1:{PORT}"
        self.url_rede = f"http://{self.ip}:{PORT}"
        self._montar_tela()
        self.after(500, self.iniciar_servidor)
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

    def _label(self, texto, tamanho=11, cor="#f6f0df", negrito=False):
        fonte = ("Segoe UI", tamanho, "bold" if negrito else "normal")
        return tk.Label(self, text=texto, bg="#151018", fg=cor, font=fonte, anchor="w", justify="left")

    def _entry_readonly(self, valor):
        var = tk.StringVar(value=valor)
        entrada = tk.Entry(self, textvariable=var, font=("Consolas", 11), relief="flat", bg="#231a29", fg="#f6f0df", insertbackground="#f6f0df")
        entrada.configure(state="readonly", readonlybackground="#231a29")
        return entrada

    def _botao(self, texto, comando, cor="#d8b56d"):
        return tk.Button(
            self,
            text=texto,
            command=comando,
            bg=cor,
            fg="#151018",
            activebackground="#f1d38b",
            activeforeground="#151018",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            cursor="hand2",
        )

    def _montar_tela(self):
        topo = tk.Frame(self, bg="#151018")
        topo.pack(fill="x", padx=24, pady=(22, 12))
        tk.Label(topo, text="🌙", bg="#151018", fg="#d8b56d", font=("Segoe UI", 28)).pack(side="left")
        tk.Label(
            topo,
            text="Mística Presentes - Servidor do App",
            bg="#151018",
            fg="#f6f0df",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left", padx=12)

        self.status_var = tk.StringVar(value="Iniciando servidor...")
        self.status_label = tk.Label(self, textvariable=self.status_var, bg="#151018", fg="#f1d38b", font=("Segoe UI", 12, "bold"), anchor="w")
        self.status_label.pack(fill="x", padx=28, pady=(0, 14))

        quadro = tk.Frame(self, bg="#201724", padx=18, pady=16)
        quadro.pack(fill="x", padx=24, pady=8)

        tk.Label(quadro, text="Endereço para usar no APP / celular:", bg="#201724", fg="#f6f0df", font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        self.url_rede_entry = self._entry_readonly(self.url_rede)
        self.url_rede_entry.pack(fill="x", pady=(6, 12))

        tk.Label(quadro, text="Endereço neste computador:", bg="#201724", fg="#f6f0df", font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        self.url_local_entry = self._entry_readonly(self.url_local)
        self.url_local_entry.pack(fill="x", pady=(6, 12))

        tk.Label(quadro, text="Token do app:", bg="#201724", fg="#f6f0df", font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        self.token_entry = self._entry_readonly(self.token)
        self.token_entry.pack(fill="x", pady=(6, 8))

        aviso = "Não envie print com o token. Use o botão Copiar token para configurar o app."
        tk.Label(quadro, text=aviso, bg="#201724", fg="#e8b86d", font=("Segoe UI", 9), anchor="w").pack(fill="x")

        botoes = tk.Frame(self, bg="#151018")
        botoes.pack(fill="x", padx=24, pady=18)
        self._botao("Iniciar servidor", self.iniciar_servidor).pack(side="left", padx=(0, 8))
        self._botao("Parar", self.parar_servidor, cor="#c96c6c").pack(side="left", padx=8)
        self._botao("Copiar URL do app", lambda: self.copiar(self.url_rede)).pack(side="left", padx=8)
        self._botao("Copiar token", lambda: self.copiar(self.token)).pack(side="left", padx=8)

        botoes2 = tk.Frame(self, bg="#151018")
        botoes2.pack(fill="x", padx=24, pady=(0, 10))
        self._botao("Abrir status", lambda: webbrowser.open(f"{self.url_rede}/api/server/status")).pack(side="left", padx=(0, 8))
        self._botao("Abrir docs", lambda: webbrowser.open(f"{self.url_rede}/docs")).pack(side="left", padx=8)
        self._botao("Abrir painel", lambda: webbrowser.open(self.url_rede)).pack(side="left", padx=8)

        instrucoes = (
            "Para começar o dia:\n"
            "1. Deixe esta janela aberta.\n"
            "2. No app, use o endereço e token acima.\n"
            "3. O celular precisa estar no mesmo Wi-Fi ou acessar por VPN/Tailscale/Cloudflare.\n"
            "4. Se trocar de Wi-Fi, o IP pode mudar; copie a nova URL mostrada aqui."
        )
        tk.Label(self, text=instrucoes, bg="#151018", fg="#bfb7c8", font=("Segoe UI", 10), justify="left", anchor="w").pack(fill="x", padx=28, pady=(8, 0))

    def copiar(self, texto: str):
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.status_var.set("Copiado para a área de transferência.")

    def iniciar_servidor(self):
        if self.processo and self.processo.poll() is None:
            self.status_var.set(f"Servidor online: {self.url_rede}")
            return

        env = os.environ.copy()
        env["MISTICA_API_TOKEN"] = self.token
        env.setdefault("MISTICA_SERVER_HOST", HOST)
        env.setdefault("MISTICA_SERVER_PORT", str(PORT))

        comando = [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
        ]
        try:
            self.processo = subprocess.Popen(
                comando,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.status_var.set("Servidor iniciando...")
            threading.Thread(target=self._monitorar_inicio, daemon=True).start()
        except Exception as exc:
            self.status_var.set("Falha ao iniciar servidor.")
            messagebox.showerror("Erro", f"Não foi possível iniciar o servidor:\n{exc}")

    def _monitorar_inicio(self):
        for _ in range(20):
            if self.processo and self.processo.poll() is not None:
                self.status_var.set("Servidor parou inesperadamente.")
                return
            time.sleep(0.5)
        self.status_var.set(f"Servidor online: {self.url_rede}")

    def parar_servidor(self):
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            self.status_var.set("Servidor parado.")
        else:
            self.status_var.set("Servidor já está parado.")

    def ao_fechar(self):
        if self.processo and self.processo.poll() is None:
            if not messagebox.askyesno("Fechar", "Fechar esta janela também para o servidor. Deseja parar o servidor?"):
                return
            self.parar_servidor()
        self.destroy()


def gerar_ou_ler_token() -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token and token != "mistica-local" and len(token) >= 12:
            return token
    token = "Mistica-" + secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def ip_local() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    os.chdir(ROOT)
    app = PainelServidor()
    app.mainloop()


if __name__ == "__main__":
    main()
