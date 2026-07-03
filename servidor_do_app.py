"""Painel do App/Celular - Mística Presentes.

Mostra a configuração oficial do aplicativo de celular/site e da API em tempo real.
A conexão oficial usa:
- Site/app: https://misticaesotericos.com.br
- API: https://api.misticaesotericos.com.br
"""

import json
import urllib.request
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from config import DEFAULT_API_URL, DEFAULT_SERVER_URL, OFFICIAL_DOMAIN, SERVER_CONFIG_PATH
from services.servidor_service import (
    descricao_servidor,
    forcar_dominio_oficial,
    status_configuracao_servidor,
)


class ServidorDoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mística Painel - App Celular")
        self.geometry("860x640")
        self.minsize(780, 580)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.cor_fundo = "#0e0813"
        self.cor_card = "#1d1322"
        self.cor_ouro = "#e0bd6a"
        self.cor_texto = "#f3ead8"
        self.cor_verde = "#7CFC98"
        self.cor_alerta = "#ffcc66"
        self.cor_erro = "#ff6b6b"
        self.cor_botao = "#d9b66b"
        self.cor_botao_texto = "#1c1320"

        self.configure(fg_color=self.cor_fundo)
        self._montar_tela()
        self.atualizar_status()
        self.testar_api(silencioso=True)

    def _label(self, master, text, size=15, weight="normal", color=None, **kwargs):
        return ctk.CTkLabel(
            master,
            text=text,
            font=("Segoe UI", size, weight),
            text_color=color or self.cor_texto,
            anchor="w",
            justify="left",
            **kwargs,
        )

    def _montar_tela(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=24, pady=(22, 10))

        self._label(topo, "📱  Mística Painel - App Celular", 28, "bold", self.cor_texto).pack(anchor="w")
        self._label(
            topo,
            "Configuração do acesso em tempo real dos dados da loja pelo celular/site",
            15,
            "normal",
            "#cbbdce",
        ).pack(anchor="w", pady=(4, 0))

        self.card_status = ctk.CTkFrame(self, fg_color=self.cor_card, corner_radius=10)
        self.card_status.pack(fill="x", padx=24, pady=12)

        self.lbl_status = self._label(self.card_status, "", 17, "bold", self.cor_ouro)
        self.lbl_status.pack(fill="x", padx=18, pady=(14, 4))

        self.lbl_api_status = self._label(self.card_status, "API: verificando...", 15, "bold", self.cor_alerta)
        self.lbl_api_status.pack(fill="x", padx=18, pady=(0, 14))

        card = ctk.CTkFrame(self, fg_color=self.cor_card, corner_radius=10)
        card.pack(fill="x", padx=24, pady=8)

        self._label(card, "URL do app/celular", 16, "bold", "#d7c6df").pack(anchor="w", padx=18, pady=(16, 4))
        self.entry_url = ctk.CTkEntry(card, height=38, font=("Consolas", 15), text_color=self.cor_texto)
        self.entry_url.pack(fill="x", padx=18, pady=(0, 12))

        self._label(card, "API de dados em tempo real", 16, "bold", "#d7c6df").pack(anchor="w", padx=18, pady=(4, 4))
        self.entry_api = ctk.CTkEntry(card, height=38, font=("Consolas", 15), text_color=self.cor_texto)
        self.entry_api.pack(fill="x", padx=18, pady=(0, 12))

        self._label(
            card,
            "O app/celular atualiza produtos, estoque, vendas e clientes pela API oficial a cada 5 segundos.",
            14,
            "bold",
            self.cor_ouro,
        ).pack(anchor="w", padx=18, pady=(0, 16))

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=14)

        self._botao(botoes, "Usar domínio oficial", self.forcar_dominio).pack(side="left", padx=(0, 8))
        self._botao(botoes, "Copiar URL", self.copiar_url).pack(side="left", padx=8)
        self._botao(botoes, "Copiar API", self.copiar_api).pack(side="left", padx=8)
        self._botao(botoes, "Abrir app celular", self.abrir_site).pack(side="left", padx=8)
        self._botao(botoes, "Testar API", self.testar_api).pack(side="left", padx=8)

        info = ctk.CTkFrame(self, fg_color=self.cor_card, corner_radius=10)
        info.pack(fill="both", expand=True, padx=24, pady=(8, 24))

        self.txt_info = ctk.CTkTextbox(info, font=("Consolas", 14), text_color=self.cor_texto, fg_color="#120b17")
        self.txt_info.pack(fill="both", expand=True, padx=14, pady=14)

    def _botao(self, master, text, command):
        return ctk.CTkButton(
            master,
            text=text,
            command=command,
            height=42,
            fg_color=self.cor_botao,
            hover_color="#caa65e",
            text_color=self.cor_botao_texto,
            font=("Segoe UI", 14, "bold"),
        )

    def _set_entry(self, entry, valor):
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, valor)
        entry.configure(state="readonly")

    def atualizar_status(self):
        cfg = status_configuracao_servidor()
        server_url = cfg.get("server_url") or DEFAULT_SERVER_URL
        api_url = cfg.get("api_url") or DEFAULT_API_URL

        self.lbl_status.configure(text=f"App/celular configurado no domínio: {server_url}")
        self._set_entry(self.entry_url, server_url)
        self._set_entry(self.entry_api, api_url)

        texto = descricao_servidor()
        texto += "\n\nMÍSTICA PAINEL / APP CELULAR - TEMPO REAL\n"
        texto += "- O celular deve acessar: https://misticaesotericos.com.br\n"
        texto += "- A API usada pelo celular é: https://api.misticaesotericos.com.br\n"
        texto += "- Produtos, estoque, vendas e clientes são buscados na API.\n"
        texto += "- Atualização automática no site/celular: a cada 5 segundos.\n"
        texto += "- Se a API ficar offline, o app/celular usa os dados locais do navegador até voltar.\n"
        texto += "- Vendas feitas pelo celular tentam sincronizar com a API automaticamente.\n"
        texto += "\nArquivo local de configuração:\n"
        texto += str(SERVER_CONFIG_PATH)
        texto += "\n\nStatus esperado:\n"
        texto += f"- Domínio: {OFFICIAL_DOMAIN}\n"
        texto += f"- URL app/celular: {server_url}\n"
        texto += f"- API tempo real: {api_url}\n"
        texto += f"- Autenticação: {cfg.get('auth_mode')}\n"
        texto += f"- Usa token antigo: {'sim' if cfg.get('use_token_access') else 'não'}\n"
        texto += f"- Armazenamento desktop: {cfg.get('storage_mode')}\n"
        texto += "\nEndpoints usados pelo celular:\n"
        texto += "- GET /api/status\n"
        texto += "- GET /api/produtos?limite=500\n"
        texto += "- GET /api/vendas?limite=50\n"
        texto += "- GET /api/clientes?limite=50\n"
        texto += "- POST /api/vendas\n"

        self.txt_info.configure(state="normal")
        self.txt_info.delete("1.0", "end")
        self.txt_info.insert("1.0", texto)
        self.txt_info.configure(state="disabled")

    def forcar_dominio(self):
        forcar_dominio_oficial()
        self.atualizar_status()
        messagebox.showinfo(
            "Domínio configurado",
            "O app/celular foi configurado para usar o domínio oficial e a API em tempo real.\n\n"
            "Site/app: https://misticaesotericos.com.br\n"
            "API: https://api.misticaesotericos.com.br",
        )

    def copiar_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.entry_url.get())
        messagebox.showinfo("Copiado", "URL do app/celular copiada.")

    def copiar_api(self):
        self.clipboard_clear()
        self.clipboard_append(self.entry_api.get())
        messagebox.showinfo("Copiado", "API oficial copiada.")

    def abrir_site(self):
        webbrowser.open(DEFAULT_SERVER_URL)

    def testar_api(self, silencioso=False):
        api_url = self.entry_api.get() if hasattr(self, "entry_api") else DEFAULT_API_URL
        try:
            req = urllib.request.Request(api_url.rstrip("/") + "/api/status", headers={"User-Agent": "MisticaPainel/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                dados = json.loads(resp.read().decode("utf-8", errors="ignore"))
            texto = (
                f"API: Online • Produtos: {dados.get('produtos', 0)} • "
                f"Clientes: {dados.get('clientes', 0)} • Vendas: {dados.get('vendas', 0)}"
            )
            self.lbl_api_status.configure(text=texto, text_color=self.cor_verde)
            if not silencioso:
                messagebox.showinfo("API Online", texto)
        except Exception as exc:
            texto = f"API: Offline ou indisponível • {exc}"
            self.lbl_api_status.configure(text=texto, text_color=self.cor_erro)
            if not silencioso:
                messagebox.showwarning("API Offline", texto)

    def mostrar_status(self):
        self.atualizar_status()
        self.testar_api(silencioso=True)
        messagebox.showinfo("Status do app/celular", descricao_servidor())


if __name__ == "__main__":
    app = ServidorDoApp()
    app.mainloop()
