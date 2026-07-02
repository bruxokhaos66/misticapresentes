r"""Painel compacto para iniciar o servidor do app Mística Presentes.

Uso recomendado no começo do dia:
    python scripts\painel_inicio_servidor.py

A janela inicia a API local, mostra o endereço para o celular/app e permite
copiar ou enviar por WhatsApp o endereço e token salvo localmente.
O token nunca é salvo no GitHub; ele fica em:
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
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path.home() / "Documents" / "Mistica_Servidor_Dedicado"
TOKEN_FILE = CONFIG_DIR / "api_token.txt"
PORT = os.getenv("MISTICA_SERVER_PORT", "8000")
HOST = os.getenv("MISTICA_SERVER_HOST", "0.0.0.0")

COR_FUNDO = "#120d16"
COR_CARD = "#201724"
COR_CARD_2 = "#2b2031"
COR_TEXTO = "#f6f0df"
COR_MUTED = "#bfb7c8"
COR_DOURADO = "#d8b56d"
COR_VERDE = "#6fbf9b"
COR_VERMELHO = "#c96c6c"


class PainelServidor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mística - Servidor do App")
        self.geometry("560x390")
        self.minsize(520, 360)
        self.configure(bg=COR_FUNDO)
        self.processo: subprocess.Popen | None = None
        self.token = gerar_ou_ler_token()
        self.ip = ip_local()
        self.url_local = f"http://127.0.0.1:{PORT}"
        self.url_rede = f"http://{self.ip}:{PORT}"
        self._montar_tela()
        self.after(500, self.iniciar_servidor)
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

    def _entry_readonly(self, valor: str):
        var = tk.StringVar(value=valor)
        entrada = tk.Entry(
            self,
            textvariable=var,
            font=("Consolas", 10),
            relief="flat",
            bg=COR_CARD_2,
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
        )
        entrada.configure(state="readonly", readonlybackground=COR_CARD_2)
        return entrada

    def _botao(self, texto, comando, cor=COR_DOURADO, largura=None):
        return tk.Button(
            self,
            text=texto,
            command=comando,
            bg=cor,
            fg=COR_FUNDO,
            activebackground="#f1d38b" if cor == COR_DOURADO else cor,
            activeforeground=COR_FUNDO,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
            width=largura,
            cursor="hand2",
        )

    def _card_label(self, parent, texto, cor=COR_MUTED):
        return tk.Label(parent, text=texto, bg=COR_CARD, fg=cor, font=("Segoe UI", 9, "bold"), anchor="w")

    def _montar_tela(self):
        topo = tk.Frame(self, bg=COR_FUNDO)
        topo.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(topo, text="🌙", bg=COR_FUNDO, fg=COR_DOURADO, font=("Segoe UI", 22)).pack(side="left")
        bloco_titulo = tk.Frame(topo, bg=COR_FUNDO)
        bloco_titulo.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(
            bloco_titulo,
            text="Servidor do App",
            bg=COR_FUNDO,
            fg=COR_TEXTO,
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            bloco_titulo,
            text="Mística Presentes • painel de início do dia",
            bg=COR_FUNDO,
            fg=COR_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x")

        self.status_var = tk.StringVar(value="Iniciando servidor...")
        self.status_label = tk.Label(
            self,
            textvariable=self.status_var,
            bg=COR_CARD,
            fg=COR_DOURADO,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            padx=12,
            pady=8,
        )
        self.status_label.pack(fill="x", padx=18, pady=(0, 10))

        quadro = tk.Frame(self, bg=COR_CARD, padx=14, pady=12)
        quadro.pack(fill="x", padx=18, pady=4)

        self._card_label(quadro, "URL para o app / celular").pack(fill="x")
        self.url_rede_entry = self._entry_readonly(self.url_rede)
        self.url_rede_entry.pack(fill="x", pady=(4, 8))

        self._card_label(quadro, "Token do app").pack(fill="x")
        self.token_entry = self._entry_readonly(self.token)
        self.token_entry.pack(fill="x", pady=(4, 6))

        aviso = "Envie o token apenas para pessoas autorizadas. Evite prints."
        tk.Label(quadro, text=aviso, bg=COR_CARD, fg="#e8b86d", font=("Segoe UI", 8), anchor="w").pack(fill="x")

        botoes = tk.Frame(self, bg=COR_FUNDO)
        botoes.pack(fill="x", padx=18, pady=(12, 6))
        self._botao("Iniciar", self.iniciar_servidor, largura=10).pack(side="left", padx=(0, 6))
        self._botao("Parar", self.parar_servidor, cor=COR_VERMELHO, largura=8).pack(side="left", padx=6)
        self._botao("Copiar URL", lambda: self.copiar(self.url_rede), largura=11).pack(side="left", padx=6)
        self._botao("Copiar token", lambda: self.copiar(self.token), largura=12).pack(side="left", padx=6)

        botoes2 = tk.Frame(self, bg=COR_FUNDO)
        botoes2.pack(fill="x", padx=18, pady=(2, 8))
        self._botao("Status", lambda: webbrowser.open(f"{self.url_rede}/api/server/status"), largura=9).pack(side="left", padx=(0, 6))
        self._botao("Docs", lambda: webbrowser.open(f"{self.url_rede}/docs"), largura=8).pack(side="left", padx=6)
        self._botao("WhatsApp", self.enviar_whatsapp, cor=COR_VERDE, largura=11).pack(side="left", padx=6)
        self._botao("Copiar mensagem", lambda: self.copiar(self.mensagem_whatsapp()), cor="#b7d8a8", largura=16).pack(side="left", padx=6)

        rodape = (
            "Começo do dia: deixe esta janela aberta e use a URL acima no app. "
            "Se mudar de Wi-Fi, o IP pode mudar."
        )
        tk.Label(
            self,
            text=rodape,
            bg=COR_FUNDO,
            fg=COR_MUTED,
            font=("Segoe UI", 9),
            wraplength=510,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 0))

    def copiar(self, texto: str):
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.status_var.set("Copiado para a área de transferência.")

    def mensagem_whatsapp(self) -> str:
        return (
            "🌙 Mística Presentes - acesso ao app\n\n"
            f"Servidor: {self.url_rede}\n"
            f"Status: {self.url_rede}/api/server/status\n"
            f"Token: {self.token}\n\n"
            "Use estes dados somente no app Mística Painel.\n"
            "Não encaminhe este token para pessoas não autorizadas."
        )

    def enviar_whatsapp(self):
        confirmar = messagebox.askyesno(
            "Enviar para WhatsApp",
            "A mensagem contém o token do app. Envie somente para pessoas autorizadas. Deseja abrir o WhatsApp?",
        )
        if not confirmar:
            return
        texto = urllib.parse.quote(self.mensagem_whatsapp())
        webbrowser.open(f"https://wa.me/?text={texto}")
        self.status_var.set("WhatsApp aberto com a mensagem pronta para enviar.")

    def iniciar_servidor(self):
        if self.processo and self.processo.poll() is None:
            self.status_var.set(f"Servidor online: {self.url_rede}")
            return
        if porta_em_uso(PORT):
            self.status_var.set(f"Servidor já está ativo na porta {PORT}: {self.url_rede}")
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
        for _ in range(14):
            if self.processo and self.processo.poll() is not None:
                if porta_em_uso(PORT):
                    self.status_var.set(f"Servidor já estava ativo: {self.url_rede}")
                else:
                    self.status_var.set("Servidor parou inesperadamente. Verifique se a porta 8000 está livre.")
                return
            time.sleep(0.5)
        self.status_var.set(f"Servidor online: {self.url_rede}")

    def parar_servidor(self):
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            self.status_var.set("Servidor parado.")
        elif porta_em_uso(PORT):
            self.status_var.set("Servidor ativo por outro processo. Feche pelo terminal se precisar parar.")
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


def porta_em_uso(porta: str | int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.35)
            return s.connect_ex(("127.0.0.1", int(porta))) == 0
    except Exception:
        return False


def main():
    os.chdir(ROOT)
    app = PainelServidor()
    app.mainloop()


if __name__ == "__main__":
    main()
