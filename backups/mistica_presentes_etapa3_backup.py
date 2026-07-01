import os
import hashlib
import sqlite3
import shutil
import webbrowser
import urllib.parse
import urllib.request
import urllib.request
import socket
import secrets
import sys
import calendar
import random
import json
import re
import traceback
from pathlib import Path
import ast
from datetime import datetime, timedelta
import customtkinter as ctk
from tkinter import messagebox, ttk, PhotoImage, Label

# VERSÃO AUDITADA - correções de estabilidade, abas, SQL e validações

# --- CONFIGURAÇÃO, BANCO E BACKUP (Arquitetura 2.0 - Etapa 1) ---
PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "mistica_presentes")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from config import (
    BACKUP_DIR,
    CONFIG_REDE_PATH,
    DASHBOARD_DAILY_MSGS,
    DASHBOARD_MSG_PATH,
    DB_PATH,
    DEFAULT_DASHBOARD_MSG,
    DOCS_PATH,
    ERROR_LOG_DIR,
    ERROR_LOG_PATH,
    ISSIS_HISTORY_PATH,
    ISSIS_IMG_ALERTA_PATH,
    ISSIS_IMG_DESCOBERTA_PATH,
    ISSIS_IMG_FELIZ_PATH,
    ISSIS_IMG_PATH,
    ISSIS_IMG_PENSANDO_PATH,
    ISSIS_IMG_RAIVA_PATH,
    ISSIS_IMG_SONO_PATH,
    ISSIS_LEARNING_PATH,
    ensure_directories,
    hash_password_pbkdf2,
    mensagem_dashboard_do_dia,
)
from database import init_db, limpar_backups_antigos, query_db, realizar_backup

ensure_directories()

APP_LOCK_SOCKET = None
def garantir_instancia_unica():
    global APP_LOCK_SOCKET
    APP_LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    APP_LOCK_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        APP_LOCK_SOCKET.bind(("127.0.0.1", 49663))
        APP_LOCK_SOCKET.listen(1)
        return True
    except OSError:
        try:
            APP_LOCK_SOCKET.close()
        except Exception:
            pass
        return False

# --- FORMATADORES ---
def format_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def conv_float(texto):
    if not texto:
        return 0.0
    limpo = "".join(filter(str.isdigit, str(texto)))
    return float(limpo) / 100 if limpo else 0.0

def carregar_mensagem_dashboard():
    """Carrega a mensagem motivacional do Dashboard.
    Por padrao, a mensagem muda automaticamente todos os dias para motivar a equipe.
    Se a Isis salvar uma mensagem personalizada, ela usa a personalizada.
    """
    try:
        if os.path.exists(DASHBOARD_MSG_PATH):
            with open(DASHBOARD_MSG_PATH, "r", encoding="utf-8") as f:
                texto = f.read().strip()
            if texto:
                return texto
    except Exception:
        pass
    return mensagem_dashboard_do_dia()

def salvar_mensagem_dashboard(texto):
    """Salva uma nova mensagem motivacional para o Dashboard."""
    texto = str(texto or "").strip()
    if not texto:
        return False
    with open(DASHBOARD_MSG_PATH, "w", encoding="utf-8") as f:
        f.write(texto)
    return True

def registrar_log(usuario, acao, detalhes):
    query_db("INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)", (usuario, acao, detalhes, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)


def registrar_movimentacao_estoque(codigo_p, produto, quantidade, tipo, motivo, usuario, estoque_anterior, estoque_posterior, venda_id=None):
    try:
        query_db(
            "INSERT INTO movimentacao_estoque (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (codigo_p, produto, int(quantidade or 0), tipo, motivo, usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), int(estoque_anterior or 0), int(estoque_posterior or 0), venda_id),
            commit=True
        )
    except Exception:
        pass


def registrar_erro_sistema(contexto, erro):
    try:
        if not os.path.exists(ERROR_LOG_DIR):
            os.makedirs(ERROR_LOG_DIR)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as arq:
            arq.write("\n" + "="*80 + "\n")
            arq.write(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            arq.write(f"Contexto: {contexto}\n")
            arq.write(f"Erro: {erro}\n")
            arq.write("Traceback:\n")
            arq.write(traceback.format_exc())
            arq.write("\n")
    except Exception:
        pass


# --- INTERFACE ---
class MisticaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mística Presentes - Gestão v23")
        self.after(0, lambda: self.state('zoomed'))
        self.withdraw()
        self.current_user = None
        self.login_tentativas = {}
        self.login_bloqueios = {}
        self.carrinho = []
        self.v_calc = {"s": 0.0, "d": 0.0, "tx": 0.0, "tot": 0.0}
        self._issis_imagens = []
        ctk.set_appearance_mode("dark")
        self.cor_ouro = "#d8b56d"
        self.cor_vinho = "#1a1621"
        self.cor_botao = "#b98a3c"
        self.font_input = ("Arial", 15)
        self.font_button = ("Arial", 15, "bold")
        self.font_label = ("Arial", 14, "bold")
        self.font_table = ("Arial", 13)
        self.font_table_head = ("Arial", 13, "bold")
        self.configurar_tabelas()
        self.tela_login()

    def configurar_tabelas(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", font=self.font_table, rowheight=30, background="#f7f3ea", fieldbackground="#f7f3ea", foreground="#111111")
        style.configure("Treeview.Heading", font=self.font_table_head, rowheight=32, background="#d8b56d", foreground="#111111")
        style.map("Treeview", background=[("selected", "#b98a3c")], foreground=[("selected", "#ffffff")])
        
    def logo(self, master, tam=35):
        f = ctk.CTkFrame(master, fg_color="transparent")
        f.pack(pady=10)
        ctk.CTkLabel(f, text="MÍSTICA PRESENTES", font=("Georgia", tam, "bold"), text_color=self.cor_ouro).pack()

    def mascara_moeda(self, event):
        campo = event.widget
        val = "".join(filter(str.isdigit, campo.get()))
        if val:
            v_f = float(val)/100
            campo.delete(0, 'end')
            campo.insert(0, f"{v_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    def mascara_cpf(self, event):
        campo = event.widget
        nums = "".join(filter(str.isdigit, campo.get()))[:11]
        texto = nums
        if len(nums) > 3:
            texto = nums[:3] + "." + nums[3:]
        if len(nums) > 6:
            texto = nums[:3] + "." + nums[3:6] + "." + nums[6:]
        if len(nums) > 9:
            texto = nums[:3] + "." + nums[3:6] + "." + nums[6:9] + "-" + nums[9:]
        campo.delete(0, 'end')
        campo.insert(0, texto)

    def mascara_telefone(self, event):
        campo = event.widget
        nums = "".join(filter(str.isdigit, campo.get()))[:11]
        texto = nums
        if len(nums) > 10:
            texto = f"({nums[:2]}) {nums[2:7]}-{nums[7:]}"
        elif len(nums) > 6:
            texto = f"({nums[:2]}) {nums[2:6]}-{nums[6:]}"
        elif len(nums) > 2:
            texto = f"({nums[:2]}) {nums[2:]}"
        campo.delete(0, 'end')
        campo.insert(0, texto)

    def mascara_data_curta(self, event):
        campo = event.widget
        nums = "".join(filter(str.isdigit, campo.get()))[:8]
        if len(nums) <= 2:
            texto = nums
        elif len(nums) <= 4:
            texto = f"{nums[:2]}/{nums[2:]}"
        else:
            texto = f"{nums[:2]}/{nums[2:4]}/{nums[4:]}"
        campo.delete(0, 'end')
        campo.insert(0, texto)

    def mascara_percentual_12(self, event):
        campo = event.widget
        txt = campo.get().replace(",", ".")
        txt = re.sub(r"[^0-9.]", "", txt)
        if txt.count(".") > 1:
            partes = txt.split(".")
            txt = partes[0] + "." + "".join(partes[1:])
        try:
            valor = float(txt) if txt else 0.0
        except Exception:
            valor = 0.0
        if valor > 12:
            valor = 12.0
        campo.delete(0, 'end')
        campo.insert(0, str(valor).replace(".", ",").rstrip("0").rstrip(",") if valor else "0")
        self.render_v_car()

    def tela_login(self):
        self.login_win = ctk.CTkToplevel(self)
        self.login_win.geometry("400x500")
        self.login_win.grab_set()
        self.login_win.protocol("WM_DELETE_WINDOW", self.encerrar_sistema)
        self.logo(self.login_win, 24)
        caixa = ctk.CTkFrame(self.login_win, fg_color=self.cor_vinho, corner_radius=20)
        caixa.pack(fill="both", expand=True, padx=30, pady=20)
        self.u_ent = ctk.CTkEntry(caixa, placeholder_text="Usuario", height=44, font=self.font_input)
        self.u_ent.pack(pady=10, padx=20, fill="x")
        self.p_ent = ctk.CTkEntry(caixa, placeholder_text="Senha", show="*", height=44, font=self.font_input)
        self.p_ent.pack(pady=10, padx=20, fill="x")
        self.p_ent.bind("<Return>", lambda e: self.autenticar())
        ctk.CTkButton(caixa, text="ENTRAR NO SISTEMA", command=self.autenticar, fg_color=self.cor_botao, height=44, font=self.font_button).pack(pady=30)

    def autenticar(self):
        u = self.u_ent.get().lower().strip()
        senha_plana = self.p_ent.get()
        agora = datetime.now()
        bloqueio = self.login_bloqueios.get(u)
        if bloqueio and agora < bloqueio:
            restante = int((bloqueio - agora).total_seconds() // 60) + 1
            messagebox.showerror("Login bloqueado", f"Muitas tentativas incorretas. Tente novamente em {restante} minuto(s).")
            return
        if u == "admin" and senha_plana == "admin":
            self.login_tentativas[u] = self.login_tentativas.get(u, 0) + 1
            messagebox.showerror("Senha bloqueada", "A senha padrao admin/admin foi desativada por seguranca. Use a senha cadastrada pelo administrador.")
            return
        senha_segura = hash_password_pbkdf2(senha_plana)
        res = query_db("SELECT nome, perfil, login, senha_hash FROM usuarios WHERE login=? AND COALESCE(ativo,1)=1", (u,))
        if res and res[0][3] == senha_segura:
            self.login_tentativas[u] = 0
            self.login_bloqueios.pop(u, None)
            self.current_user = {"nome": res[0][0], "perfil": res[0][1], "login": res[0][2]}
            registrar_log(self.current_user['nome'], "Acesso", "Login realizado")
            self.login_win.destroy()
            self.deiconify()
            self.montar_abas()
        else:
            tentativas = self.login_tentativas.get(u, 0) + 1
            self.login_tentativas[u] = tentativas
            if tentativas >= 5:
                self.login_bloqueios[u] = agora + timedelta(minutes=5)
                registrar_log(u or "desconhecido", "Seguranca", "Login bloqueado por tentativas incorretas")
                messagebox.showerror("Login bloqueado", "Muitas tentativas incorretas. Aguarde 5 minutos.")
            else:
                messagebox.showerror("Erro", "Usuario ou senha incorretos.")

    def forcar_troca_senha_inicial(self, login_usuario):
        win_troca = ctk.CTkToplevel(self)
        win_troca.title("Segurança")
        win_troca.geometry("380x300")
        win_troca.grab_set()
        ctk.CTkLabel(win_troca, text="ALTERAÇÃO OBRIGATÓRIA DE SENHA", font=self.font_label, text_color="#ff4d4d").pack(pady=15)
        nova_s = ctk.CTkEntry(win_troca, placeholder_text="Nova Senha", show="*", height=40, font=self.font_input)
        nova_s.pack(padx=20, pady=10, fill="x")
        def salvar_senha():
            senha_txt = nova_s.get().strip()
            if len(senha_txt) < 4:
                messagebox.showerror("Erro", "A senha precisa ter pelo menos 4 caracteres.")
                return
            query_db("UPDATE usuarios SET senha_hash=? WHERE login=?", (hash_password_pbkdf2(senha_txt), login_usuario), commit=True)
            messagebox.showinfo("Sucesso", "Senhá atualizada! Prossiga com o login.")
            win_troca.destroy()
        ctk.CTkButton(win_troca, text="SALVAR NOVA SENHA", height=42, fg_color=self.cor_botao, font=self.font_button, command=salvar_senha).pack(pady=15)

    def montar_abas(self):
        self.logo(self)
        barra_usuario = ctk.CTkFrame(self, fg_color="transparent")
        barra_usuario.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(barra_usuario, text=f"Usuario: {self.current_user['nome']} ({self.current_user['perfil']})", font=self.font_label, text_color=self.cor_ouro).pack(side="left", padx=8)
        self.label_relogio_sistema = ctk.CTkLabel(barra_usuario, text="", font=("Arial", 16, "bold"), text_color="#f1e1b0")
        self.label_relogio_sistema.pack(side="left", padx=18)
        ctk.CTkButton(barra_usuario, text="LOGOUT", width=120, height=36, font=self.font_button, fg_color="#7f4c4c", command=self.logout).pack(side="right", padx=6)
        ctk.CTkButton(barra_usuario, text="FECHAR", width=120, height=36, font=self.font_button, fg_color="#4c4c4c", command=self.encerrar_sistema).pack(side="right", padx=6)
        self.atualizar_relogio_sistema()
        self.tabs = ctk.CTkTabview(self, segmented_button_selected_color=self.cor_botao)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_d = self.tabs.add("Dashboard")
        self.tab_v = self.tabs.add("Vendas")
        self.tab_e = self.tabs.add("Estoque")
        self.tab_c = self.tabs.add("Clientes")
        self.tab_m = self.tabs.add("Marketing")
        self.tab_ia = self.tabs.add("Isis a Bruxinha")
        
        if self.current_user['perfil'] == 'adm':
            self.tab_fin = self.tabs.add("Financeiro")
            self.tab_r = self.tabs.add("Relatórios")
            self.tab_f = self.tabs.add("Fornecedores")
            self.tab_adm = self.tabs.add("Administração")
            self.executar_montagem_segura("tab_fin", self.montar_financeiro)
            self.executar_montagem_segura("tab_r", self.montar_relatorios)
            self.executar_montagem_segura("tab_f", self.montar_fornecedores)
            self.executar_montagem_segura("tab_adm", self.montar_administracao)
        
        self.executar_montagem_segura("tab_d", self.montar_dashboard)
        self.executar_montagem_segura("tab_e", self.montar_estoque)
        self.executar_montagem_segura("tab_c", self.montar_clientes)
        self.executar_montagem_segura("tab_v", self.montar_vendas)
        self.executar_montagem_segura("tab_m", self.montar_marketing)
        self.executar_montagem_segura("tab_ia", self.montar_ia)
        try:
            self.agendar_baloes_issis()
        except Exception:
            pass

    def logout(self):
        registrar_log(self.current_user['nome'] if self.current_user else "Sistema", "Logout", "Usuario saiu")
        self.carrinho = []
        self.current_user = None
        for widget in self.winfo_children():
            widget.destroy()
        self.withdraw()
        self.tela_login()

    def encerrar_sistema(self):
        try:
            if self.current_user:
                registrar_log(self.current_user['nome'], "Saida", "Sistema fechado")
            realizar_backup()
        except Exception:
            pass
        self.destroy()

    def atualizar_relogio_sistema(self):
        try:
            if hasattr(self, "label_relogio_sistema") and self.label_relogio_sistema.winfo_exists():
                self.label_relogio_sistema.configure(text=datetime.now().strftime("Data e hora: %d/%m/%Y %H:%M:%S"))
                self.after(1000, self.atualizar_relogio_sistema)
        except Exception:
            pass

    def executar_montagem_segura(self, nome_aba, funcao):
        try:
            funcao()
        except Exception as e:
            registrar_erro_sistema(f"Abertura de aba: {nome_aba}", e)
            try:
                tab = getattr(self, nome_aba, None)
                if tab is not None:
                    for w in tab.winfo_children():
                        w.destroy()
                    aviso = ctk.CTkFrame(tab, fg_color=self.cor_vinho, corner_radius=15)
                    aviso.pack(fill="both", expand=True, padx=20, pady=20)
                    ctk.CTkLabel(
                        aviso,
                        text="Esta área encontrou um erro ao abrir.",
                        font=("Arial", 20, "bold"),
                        text_color="#ffcc00"
                    ).pack(pady=(30, 10))
                    ctk.CTkLabel(
                        aviso,
                        text=str(e),
                        font=("Arial", 14),
                        text_color="#ffffff",
                        wraplength=900
                    ).pack(padx=20, pady=10)
            except Exception:
                pass
            messagebox.showerror("Erro ao abrir aba", f"Erro em {nome_aba}: {e}")

    # --- ABA DASHBOARD ---
    def montar_dashboard(self):
        for w in self.tab_d.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_d, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=15, pady=15)
        f.columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        hoje = datetime.now().strftime("%d/%m/%Y")
        mes = datetime.now().strftime("/%m/%Y")
        tot_hoje = query_db("SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{hoje}%",))[0][0] or 0.0
        tot_mes = query_db("SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{mes}%",))[0][0] or 0.0
        qtd_prod = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1")[0][0] or 0
        qtd_cli = query_db("SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1")[0][0] or 0
        tot_estoque = query_db("SELECT SUM(quantidade) FROM produtos WHERE COALESCE(ativo,1)=1")[0][0] or 0
        
        kpis = [
            ("VENDAS HOJE", format_moeda(tot_hoje), "#5f7f4c"),
            ("VENDAS MÊS", format_moeda(tot_mes), "#b98a3c"),
            ("PRODUTOS", str(qtd_prod), "#3c7bb9"),
            ("CLIENTES", str(qtd_cli), "#7c3cb9"),
            ("PEÇAS ESTOQUE", str(tot_estoque), "#3cb9b1")
        ]
        for idx, (titulo, val, cor) in enumerate(kpis):
            card = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15, border_width=2, border_color=cor)
            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(card, text=titulo, font=("Arial", 11, "bold"), text_color=cor).pack(pady=(12, 2))
            ctk.CTkLabel(card, text=val, font=("Arial", 22, "bold"), text_color="#ffffff").pack(pady=(2, 12))
            
        f_info = ctk.CTkFrame(f, fg_color="#18121f", corner_radius=15)
        f_info.grid(row=1, column=0, columnspan=5, pady=20, sticky="nsew")
        ctk.CTkLabel(f_info, text="Mística Presentes", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(15, 5))
        self.dashboard_msg_lbl = ctk.CTkLabel(
            f_info,
            text=f'"{carregar_mensagem_dashboard()}"',
            font=("Arial", 14, "italic"),
            wraplength=720,
            text_color="#cccccc"
        )
        self.dashboard_msg_lbl.pack(pady=10)
        alertas_txt = self.isis_alertas_operacionais() if hasattr(self, "isis_alertas_operacionais") else "Sem alertas agora."
        ctk.CTkLabel(f_info, text="Painel de alertas da Isis", font=self.font_label, text_color=self.cor_ouro).pack(pady=(10, 3))
        ctk.CTkLabel(f_info, text=alertas_txt, font=("Arial", 13, "bold"), wraplength=900, justify="left", text_color="#f0e6d2").pack(padx=25, pady=(0, 10))
        ctk.CTkButton(f_info, text="RECARREGAR INFORMAÇÕES DO PAINEL", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)

    # --- ABA VENDAS ---
    def montar_vendas(self):
        f = ctk.CTkFrame(self.tab_v, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=10)
        esq = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        esq.pack(side="left", fill="both", expand=True, padx=5)
        
        ctk.CTkLabel(esq, text="BUSCA RAPIDA - NOME, CATEGORIA OU CODIGO", font=self.font_label).pack(pady=(10,0))
        self.v_busca = ctk.CTkEntry(esq, placeholder_text="Ex: Vela, Incenso, Cristal...", height=42, font=self.font_input)
        self.v_busca.pack(fill="x", padx=15, pady=10)
        self.v_busca.bind("<KeyRelease>", self.filtrar_vendas)

        self.tree_v_stock = ttk.Treeview(esq, columns=("id","n","p","q","c"), show="headings", height=8)
        for c, h in zip(("id","n","p","q","c"), ("Cod","Produto","Preco","Qtd","Cat")):
            self.tree_v_stock.heading(c, text=h)
            self.tree_v_stock.column(c, width=90)
        self.tree_v_stock.pack(fill="x", padx=15, pady=5)
        self.tree_v_stock.bind("<Double-1>", lambda e: self.add_ao_carrinho())

        f_mid = ctk.CTkFrame(esq, fg_color="transparent")
        f_mid.pack(fill="x", padx=15, pady=5)
        self.v_qtd = ctk.CTkEntry(f_mid, width=60, height=40, font=self.font_input)
        self.v_qtd.pack(side="left", padx=2)
        self.v_qtd.insert(0,"1")
        ctk.CTkButton(f_mid, text="ADICIONAR ITEM", command=self.add_ao_carrinho, fg_color="#5f7f4c", height=40, font=self.font_button).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(f_mid, text="REMOVER ITEM", command=self.remover_item_car, fg_color="#7f4c4c", height=40, font=self.font_button).pack(side="left", fill="x", expand=True, padx=2)

        self.tree_v_car = ttk.Treeview(esq, columns=("n","q","t"), show="headings", height=8)
        self.tree_v_car.heading("n", text="Produto (Dê duplo clique para editar quantidade)")
        self.tree_v_car.heading("q", text="Qtd")
        self.tree_v_car.heading("t", text="Total")
        self.tree_v_car.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_v_car.bind("<Double-1>", lambda e: self.editar_qtd_carrinho())

        dir = ctk.CTkFrame(f, fg_color=self.cor_vinho, width=390, corner_radius=15)
        dir.pack(side="right", fill="y", padx=5)
        dir.pack_propagate(False)
        topo_checkout = ctk.CTkFrame(dir, fg_color="transparent")
        topo_checkout.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(topo_checkout, text="Total da venda", font=self.font_label, text_color=self.cor_ouro).pack()
        self.v_total_lbl = ctk.CTkLabel(topo_checkout, text="R$ 0,00", font=("Arial", 30, "bold"), text_color=self.cor_ouro)
        self.v_total_lbl.pack(pady=(0, 6))

        corpo_checkout = ctk.CTkScrollableFrame(dir, fg_color="#18121f", corner_radius=12)
        corpo_checkout.pack(fill="both", expand=True, padx=12, pady=4)
        ctk.CTkLabel(corpo_checkout, text="Cliente do cupom", font=self.font_label, text_color=self.cor_ouro).pack(pady=(8, 2))
        self.v_cli_busca = ctk.CTkEntry(corpo_checkout, placeholder_text="Pesquisar...", width=320, height=36, font=self.font_input)
        self.v_cli_busca.pack(pady=(0, 4))
        self.v_cli_busca.bind("<KeyRelease>", self.filtrar_clientes_venda)
        self.v_cli_cb = ctk.CTkComboBox(corpo_checkout, values=["Consumidor Final"], width=320, height=38, font=self.font_input, dropdown_font=self.font_input)
        self.v_cli_cb.pack(pady=(0, 8))

        caixa_cli_venda = ctk.CTkFrame(corpo_checkout, fg_color="#241d2b", corner_radius=10)
        caixa_cli_venda.pack(fill="x", padx=6, pady=(2, 8))
        ctk.CTkLabel(caixa_cli_venda, text="Cadastrar cliente na venda", font=self.font_label, text_color=self.cor_ouro).pack(pady=(6, 2))
        self.v_cli_nome = ctk.CTkEntry(caixa_cli_venda, placeholder_text="Nome completo", height=34, font=self.font_input)
        self.v_cli_nome.pack(fill="x", padx=8, pady=2)
        l_cli_venda = ctk.CTkFrame(caixa_cli_venda, fg_color="transparent")
        l_cli_venda.pack(fill="x", padx=8, pady=2)
        self.v_cli_cpf = ctk.CTkEntry(l_cli_venda, placeholder_text="CPF", height=34, font=self.font_input)
        self.v_cli_cpf.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.v_cli_cpf.bind("<KeyRelease>", self.mascara_cpf)
        self.v_cli_tel = ctk.CTkEntry(l_cli_venda, placeholder_text="Telefone", height=34, font=self.font_input)
        self.v_cli_tel.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.v_cli_tel.bind("<KeyRelease>", self.mascara_telefone)
        ctk.CTkButton(caixa_cli_venda, text="SALVAR E USAR NO CUPOM", height=36, font=self.font_button, fg_color=self.cor_botao, command=self.salvar_cliente_venda).pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(corpo_checkout, text="Desconto e pagamento", font=self.font_label, text_color=self.cor_ouro).pack(pady=(4, 2))
        self.v_desc_ent = ctk.CTkEntry(corpo_checkout, placeholder_text="Desconto max 12%", width=190, height=38, font=self.font_input)
        self.v_desc_ent.insert(0,"0")
        self.v_desc_ent.pack(pady=(0, 6))
        self.v_desc_ent.bind("<KeyRelease>", self.mascara_percentual_12)
        self.v_pag_cb = ctk.CTkOptionMenu(corpo_checkout, values=["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"], command=lambda e: self.render_v_car(), height=38, font=self.font_button, dropdown_font=self.font_input)
        self.v_pag_cb.pack(pady=(0, 8))

        rodape_checkout = ctk.CTkFrame(dir, fg_color="transparent")
        rodape_checkout.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkButton(rodape_checkout, text="FINALIZAR VENDA", fg_color="#8fd36b", text_color="#071107", height=58, font=("Arial", 22, "bold"), command=self.finalizar_venda).pack(fill="x")
        self.filtrar_vendas()
        self.refresh_cli_venda()

    def filtrar_clientes_venda(self, e=None):
        termo = self.v_cli_busca.get().strip()
        res = query_db("SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND (nome LIKE ? OR cpf LIKE ? OR telefone LIKE ?) ORDER BY nome LIMIT 30", (f"%{termo}%", f"%{termo}%", f"%{termo}%")) if termo else query_db("SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 ORDER BY nome LIMIT 50")
        nomes = [r[0] for r in res]
        self.v_cli_cb.configure(values=["Consumidor Final"] + nomes)
        if nomes:
            self.v_cli_cb.set(nomes[0])
        elif not termo:
            self.v_cli_cb.set("Consumidor Final")

    def salvar_cliente_venda(self):
        nome = self.v_cli_nome.get().strip()
        cpf = self.v_cli_cpf.get().strip()
        tel = self.v_cli_tel.get().strip()
        if not nome:
            messagebox.showwarning("Cliente", "Informe o nome.")
            return
        exist = query_db("SELECT id FROM clientes WHERE cpf=? ORDER BY id DESC LIMIT 1", (cpf,)) if cpf else []
        if exist:
            query_db("UPDATE clientes SET nome=?, telefone=? WHERE id=?", (nome, tel, exist[0][0]), commit=True)
        else:
            query_db("INSERT INTO clientes (nome, telefone, cpf, nascimento) VALUES (?,?,?,?)", (nome, tel, cpf, ""), commit=True)
        self.refresh_cli_list()
        self.refresh_cli_venda()
        self.v_cli_cb.set(nome)
        self.v_cli_busca.delete(0, 'end')
        self.v_cli_nome.delete(0, 'end')
        self.v_cli_cpf.delete(0, 'end')
        self.v_cli_tel.delete(0, 'end')

    def travar_desconto(self, e=None):
        try:
            val = float(self.v_desc_ent.get().replace(",", "."))
            if val > 12:
                self.v_desc_ent.delete(0, 'end')
                self.v_desc_ent.insert(0, "12")
        except Exception:
            pass
        self.render_v_car()

    def filtrar_vendas(self, e=None):
        t = self.v_busca.get()
        for i in self.tree_v_stock.get_children():
            self.tree_v_stock.delete(i)
        res = query_db("SELECT codigo_p, nome, preco, quantidade, categoria FROM produtos WHERE COALESCE(ativo,1)=1 AND (nome LIKE ? OR categoria LIKE ? OR codigo_p LIKE ?) ORDER BY nome LIMIT 80", (f"%{t}%", f"%{t}%", f"%{t}%"))
        for r in res:
            self.tree_v_stock.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), r[3], r[4]))

    def add_ao_carrinho(self):
        sel = self.tree_v_stock.selection()
        if sel:
            p = self.tree_v_stock.item(sel[0], "values")
            try:
                qtd = int(self.v_qtd.get())
                if qtd <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("Quantidade", "Insira um número maior que zero.")
                return
            estoque_res = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (p[0],))
            estoque_atual = estoque_res[0][0] if estoque_res and estoque_res[0][0] is not None else 0
            if qtd <= estoque_atual:
                preco = conv_float(p[2])
                self.carrinho.append({"id":p[0], "n":p[1], "q":qtd, "p":preco, "t":preco*qtd})
                min_res = query_db("SELECT COALESCE(estoque_minimo,0) FROM produtos WHERE codigo_p=?", (p[0],))
                est_min = min_res[0][0] if min_res else 0
                restante = estoque_atual - sum(int(it['q']) for it in self.carrinho if it['id'] == p[0])
                if restante <= est_min:
                    messagebox.showwarning("Estoque baixo", f"Atenção: '{p[1]}' ficará com {restante} unidade(s), abaixo ou no mínimo ({est_min}).")
                self.render_v_car()
                self.v_busca.delete(0, 'end')
                self.v_busca.focus()
            else:
                messagebox.showerror("Estoque", "Quantidade indisponível ou produto não localizado.")

    def remover_item_car(self):
        sel = self.tree_v_car.selection()
        if sel:
            self.carrinho.pop(self.tree_v_car.index(sel[0]))
            self.render_v_car()

    def editar_qtd_carrinho(self):
        sel = self.tree_v_car.selection()
        if sel:
            idx = self.tree_v_car.index(sel[0])
            item_car = self.carrinho[idx]
            resp = ctk.CTkInputDialog(text=f"Nova quantidade para '{item_car['n']}':", title="Editar Quantidade").get_input()
            if resp is not None:
                try:
                    nova_qtd = int(resp)
                    if nova_qtd <= 0:
                        raise ValueError
                except Exception:
                    messagebox.showerror("Quantidade", "Insira um valor maior que zero.")
                    return
                estoque_res = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (item_car['id'],))
                estoque_atual = estoque_res[0][0] if estoque_res and estoque_res[0][0] is not None else 0
                if nova_qtd <= estoque_atual:
                    item_car['q'] = nova_qtd
                    item_car['t'] = item_car['p'] * nova_qtd
                    min_res = query_db("SELECT COALESCE(estoque_minimo,0) FROM produtos WHERE codigo_p=?", (item_car['id'],))
                    est_min = min_res[0][0] if min_res else 0
                    restante = estoque_atual - nova_qtd
                    if restante <= est_min:
                        messagebox.showwarning("Estoque baixo", f"Atenção: '{item_car['n']}' ficará com {restante} unidade(s), abaixo ou no mínimo ({est_min}).")
                    self.render_v_car()
                else:
                    messagebox.showerror("Estoque", "Quantidade indisponível ou produto não localizado.")

    def resetar_venda(self):
        self.carrinho = []
        if hasattr(self, "tree_v_car"):
            self.render_v_car()
        if hasattr(self, "v_qtd"):
            self.v_qtd.delete(0, 'end')
            self.v_qtd.insert(0, "1")
        for nome_ent in ["v_busca", "v_cli_busca", "v_cli_nome", "v_cli_cpf", "v_cli_tel"]:
            ent = getattr(self, nome_ent, None)
            if ent is not None:
                try:
                    ent.delete(0, 'end')
                except Exception:
                    pass
        if hasattr(self, "v_cli_cb"):
            self.v_cli_cb.set("Consumidor Final")
        if hasattr(self, "v_desc_ent"):
            self.v_desc_ent.delete(0, 'end')
            self.v_desc_ent.insert(0, "0")
        if hasattr(self, "v_pag_cb"):
            self.v_pag_cb.set("Dinheiro")
        if hasattr(self, "tree_est"):
            self.refresh_estoque_list()
        if hasattr(self, "tree_v_stock"):
            self.filtrar_vendas()

    def render_v_car(self):
        for i in self.tree_v_car.get_children():
            self.tree_v_car.delete(i)
        sub = sum(it['t'] for it in self.carrinho)
        try:
            d_p = float(self.v_desc_ent.get().replace(",", "."))
        except Exception:
            d_p = 0.0
        desc = sub * (d_p/100)
        base = sub - desc
        pg = self.v_pag_cb.get()
        taxa = 1.5 if pg=="Debito" else (base*0.015 if "1x" in pg else (base*0.02 if "2x" in pg else (base*0.025 if "3x" in pg else 0)))
        self.v_calc = {"s":sub, "d":desc, "tx":taxa, "tot":base+taxa}
        for it in self.carrinho:
            self.tree_v_car.insert("", "end", values=(it['n'], it['q'], format_moeda(it['t'])))
        self.v_total_lbl.configure(text=format_moeda(self.v_calc['tot']))

    def validar_venda_para_conferencia(self):
        cx_aberto = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
        if not cx_aberto:
            messagebox.showwarning("Caixa", "Abra o caixa diário antes de efetuar vendas.")
            return None
        if not self.carrinho:
            messagebox.showwarning("Venda", "Carrinho vazio.")
            return None
        qtd_por_codigo = {}
        for it in self.carrinho:
            qtd_por_codigo[it["id"]] = qtd_por_codigo.get(it["id"], 0) + int(it["q"])
        avisos = []
        for cod, qtd_total in qtd_por_codigo.items():
            estoque_res = query_db("SELECT nome, COALESCE(quantidade,0), COALESCE(estoque_minimo,0) FROM produtos WHERE codigo_p=?", (cod,))
            if not estoque_res:
                messagebox.showerror("Estoque", f"Produto {cod} não localizado. Atualize a venda.")
                return None
            nome_prod, estoque_atual, est_min = estoque_res[0]
            if qtd_total > estoque_atual:
                messagebox.showerror("Estoque", f"Estoque insuficiente para '{nome_prod}'.\nDisponível: {estoque_atual}\nNo carrinho: {qtd_total}")
                return None
            restante = estoque_atual - qtd_total
            if restante <= est_min:
                avisos.append(f"{nome_prod}: ficara com {restante} un. (minimo {est_min})")
        return {"caixa_id": cx_aberto[0][0], "avisos": avisos}

    def montar_texto_cupom(self, vid, cli, data):
        titulo = "CUPOM EM CONFERENCIA" if str(vid).upper() == "CONFERENCIA" else f"CUPOM N: {vid}"
        c = f"        MÍSTICA PRESENTES\n        Natalia Grunwald\n    CNPJ: 41.966.398/0001-00\n    Telefone: 49-99917-2137\n--------------------------------\n{titulo} | DATA: {data}\nCLIENTE: {cli}\nVENDEDOR: {self.current_user['nome']}\nPAGAMENTO: {self.v_pag_cb.get()}\n--------------------------------\n"
        for it in self.carrinho:
            c += f"{it['n'][:18]:<18} Qtd:{it['q']:<3} {format_moeda(it['t'])}\n"
        c += f"--------------------------------\nSUBTOTAL: {format_moeda(self.v_calc['s'])}\nDESCONTO: -{format_moeda(self.v_calc['d'])}\nTAXA CARTÃO: {format_moeda(self.v_calc['tx'])}\nTOTAL FINAL: {format_moeda(self.v_calc['tot'])}\n--------------------------------\nMística Presentes agradece pela sua compra\n"
        if str(vid).upper() == "CONFERENCIA":
            c += "\n*** CONFERENCIA: esta venda ainda NÃO foi salva. ***\n"
        return c

    def finalizar_venda(self):
        validacao = self.validar_venda_para_conferencia()
        if not validacao:
            return
        self.render_v_car()
        if validacao["avisos"]:
            messagebox.showwarning("Estoque baixo após venda", "A venda pode deixar estes itens baixos:\n\n" + "\n".join(validacao["avisos"][:6]))
        cli = self.v_cli_cb.get()
        data = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.abrir_cupom_conferencia(cli, data, validacao["caixa_id"])

    def abrir_cupom_conferencia(self, cli, data, cx_id):
        win = ctk.CTkToplevel(self)
        win.title("Conferir venda - ainda não salva")
        win.geometry("560x800")
        win.grab_set()
        ctk.CTkLabel(win, text="CONFERENCIA DA VENDA", font=("Arial", 20, "bold"), text_color="#b98a3c").pack(pady=(10, 0))
        ctk.CTkLabel(win, text="Confira o cupom. A venda so sera salva depois de confirmar.", font=("Arial", 13, "bold"), text_color="#222222").pack(pady=(2, 8))
        txt = ctk.CTkTextbox(win, font=("Courier New", 14, "bold"), fg_color="#fff9e6", text_color="#000")
        txt.pack(fill="both", expand=True, padx=10, pady=8)
        c = self.montar_texto_cupom("CONFERENCIA", cli, data)
        txt.insert("0.0", c)
        txt.configure(state="disabled")
        fb = ctk.CTkFrame(win, fg_color="transparent")
        fb.pack(fill="x", pady=10, padx=10)
        ctk.CTkButton(fb, text="VOLTAR", height=44, font=self.font_button, fg_color="#4c4c4c", command=win.destroy).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(fb, text="CONFIRMAR E SALVAR", height=44, font=self.font_button, fg_color="#5f7f4c", command=lambda: self.confirmar_venda_conferida(win, cli, data, cx_id, False, False)).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(fb, text="SALVAR + IMPRIMIR", height=44, font=self.font_button, fg_color=self.cor_botao, command=lambda: self.confirmar_venda_conferida(win, cli, data, cx_id, True, False)).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(win, text="SALVAR + ENVIAR WHATSAPP", height=44, font=self.font_button, fg_color="#2e8b57", command=lambda: self.confirmar_venda_conferida(win, cli, data, cx_id, False, True)).pack(fill="x", padx=14, pady=(0, 10))

    def confirmar_venda_conferida(self, win, cli, data, cx_id, imprimir=False, whatsapp=False):
        validacao = self.validar_venda_para_conferencia()
        if not validacao:
            return
        data_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cli, data, data_iso, self.v_calc['s'], self.v_calc['d'], self.v_calc['tx'], self.v_calc['tot'], self.v_pag_cb.get(), self.current_user['nome'], "Concluído")
            )
            vid = cur.lastrowid
            for it in self.carrinho:
                prod_res = cur.execute("SELECT nome, custo, COALESCE(quantidade,0) FROM produtos WHERE codigo_p=?", (it['id'],)).fetchone()
                if not prod_res:
                    raise ValueError(f"Produto {it['id']} não localizado.")
                nome_prod, cust_un, estoque_anterior = prod_res[0], (prod_res[1] or 0.0), int(prod_res[2] or 0)
                qtd_item = int(it['q'])
                if qtd_item > estoque_anterior:
                    raise ValueError(f"Estoque insuficiente para {nome_prod}. Disponível: {estoque_anterior}.")
                cur.execute("INSERT INTO vendas_itens (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total) VALUES (?,?,?,?,?,?,?)", (vid, it['id'], it['n'], qtd_item, cust_un, it['p'], it['t']))
                cur.execute("UPDATE produtos SET quantidade = COALESCE(quantidade,0) - ? WHERE codigo_p = ? AND COALESCE(quantidade,0) >= ?", (qtd_item, it['id'], qtd_item))
                if cur.rowcount != 1:
                    raise ValueError(f"Não consegui baixar estoque de {nome_prod}; atualize a venda.")
                estoque_posterior = estoque_anterior - qtd_item
                cur.execute("INSERT INTO movimentacao_estoque (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (it['id'], nome_prod, -qtd_item, "Venda", f"Venda nº {vid}", self.current_user['nome'], datetime.now().strftime("%d/%m/%Y %H:%M:%S"), estoque_anterior, estoque_posterior, vid))
            cur.execute("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)", ("Entrada", f"Venda nº {vid} ({self.v_pag_cb.get()})", self.v_calc['tot'], data, data_iso, cx_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Erro", f"Erro ao salvar venda: {e}")
            return
        finally:
            conn.close()
        cupom_final = self.montar_texto_cupom(vid, cli, data)
        realizar_backup()
        registrar_log(self.current_user['nome'], "Venda", f"N {vid} - {format_moeda(self.v_calc['tot'])}")
        if imprimir:
            self.imprimir_cupom_texto(cupom_final, vid)
        if whatsapp:
            self.enviar_cupom_whatsapp(cupom_final, cli)
        win.destroy()
        messagebox.showinfo("Venda salva", f"Venda nº {vid} salva com sucesso.")
        try:
            self.balao_issis(self.mensagem_venda_issis(self.v_calc['tot'], cli), tipo="feliz")
        except Exception:
            pass
        self.resetar_venda()

    def imprimir_cupom_texto(self, cupom, vid):
        caminho = os.path.join(DOCS_PATH, f"cupom_{vid}.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(cupom)
        try:
            os.startfile(caminho, "print")
        except Exception:
            try:
                os.startfile(caminho)
            except Exception:
                pass

    def finalizar_pos_venda(self, win, c, vid, imp):
        if imp:
            self.imprimir_cupom_texto(c, vid)
        win.destroy()
        self.resetar_venda()

    def telefone_cliente_whatsapp(self, cliente):
        if not cliente or cliente == "Consumidor Final": return ""
        res = query_db("SELECT telefone FROM clientes WHERE nome=? AND COALESCE(ativo,1)=1 ORDER BY id DESC LIMIT 1", (cliente,))
        if not res or not res[0][0]: return ""
        num = "".join(filter(str.isdigit, str(res[0][0])))
        return "55" + num if len(num) in (10, 11) else num

    def enviar_cupom_whatsapp(self, cupom, cliente=None):
        try:
            texto = urllib.parse.quote(cupom)
            tel = self.telefone_cliente_whatsapp(cliente)
            if tel:
                webbrowser.open(f"https://wa.me/{tel}?text={texto}")
            else:
                messagebox.showinfo("WhatsApp", "Abriremos o app para escolher o contato.")
                webbrowser.open(f"https://wa.me/?text={texto}")
        except Exception:
            pass

    def finalizar_pos_venda(self, win, c, vid, imp):
        if imp:
            caminho = os.path.join(DOCS_PATH, f"cupom_{vid}.txt")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(c)
            try:
                os.startfile(caminho, "print")
            except Exception:
                try:
                    os.startfile(caminho)
                except Exception:
                    pass
        win.destroy()
        self.resetar_venda()

    # --- CONTROLE DINÂMICO DE PREÇOS (ESTOQUE) ---
    def atualiza_custo_e_calcula(self, event=None):
        if event is not None:
            self.mascara_moeda(event)
        self.calcular_preco_por_custo_lucro()

    def atualiza_lucro_e_calcula(self, event=None):
        self.calcular_preco_por_custo_lucro()

    def recalcular_preco_final(self, event=None):
        try:
            custo_texto = "".join(filter(str.isdigit, self.ecu.get()))
            custo = float(custo_texto) / 100 if custo_texto else 0.0
            lucro_texto = self.elu.get().replace(",", ".")
            lucro = float(lucro_texto) if lucro_texto else 0.0
            preco_final = custo * (1 + (lucro / 100))
            self.ep.delete(0, 'end')
            self.ep.insert(0, f"{preco_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        except Exception:
            pass

    # --- ABA ESTOQUE ---
    def montar_estoque(self):
        for w in self.tab_e.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_e, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20)
        cad = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        cad.pack(fill="x", pady=10)
        
        self.en = ctk.CTkEntry(cad, placeholder_text="Produto", width=180, height=40, font=self.font_input)
        self.en.pack(side="left", padx=4, pady=15)
        self.ecu = ctk.CTkEntry(cad, placeholder_text="Custo", width=80, height=40, font=self.font_input)
        self.ecu.pack(side="left", padx=4)
        self.ecu.bind("<KeyRelease>", self.atualiza_custo_e_calcula)
        self.elu = ctk.CTkEntry(cad, placeholder_text="Aumento %", width=80, height=40, font=self.font_input)
        self.elu.pack(side="left", padx=4)
        self.elu.bind("<KeyRelease>", self.atualiza_lucro_e_calcula)
        self.ep = ctk.CTkEntry(cad, placeholder_text="Preço Final", width=100, height=40, font=self.font_input)
        self.ep.pack(side="left", padx=4)
        self.ep.bind("<KeyRelease>", self.mascara_moeda)
        self.eq = ctk.CTkEntry(cad, placeholder_text="Qtd", width=60, height=40, font=self.font_input)
        self.eq.pack(side="left", padx=4)
        self.emin = ctk.CTkEntry(cad, placeholder_text="Min", width=60, height=40, font=self.font_input)
        self.emin.pack(side="left", padx=4)
        self.emin.insert(0, "0")
        self.ec = ctk.CTkComboBox(cad, values=[], width=120, height=40, font=self.font_input, dropdown_font=self.font_input)
        self.ec.pack(side="left", padx=4)
        ctk.CTkButton(cad, text="SALVAR", command=self.salvar_prod, fg_color="#5f7f4c", height=40, font=self.font_button).pack(side="left", padx=5)
        
        f_cat = ctk.CTkFrame(f, fg_color="transparent")
        f_cat.pack(fill="x", pady=5)
        self.cat_e = ctk.CTkEntry(f_cat, placeholder_text="Nova Categoria", height=40, font=self.font_input)
        self.cat_e.pack(side="left", padx=2)
        ctk.CTkButton(f_cat, text="+", width=44, height=40, font=self.font_button, command=self.add_cat).pack(side="left", padx=2)
        
        self.est_busca = ctk.CTkEntry(f_cat, placeholder_text="Pesquisar estoque...", width=200, height=40, font=self.font_input)
        self.est_busca.pack(side="left", padx=15)
        self.est_busca.bind("<KeyRelease>", lambda e: self.refresh_estoque_list())
        ctk.CTkButton(f_cat, text="GERAR ETIQUETA", width=140, height=40, font=self.font_button, fg_color="#b98a3c", command=self.janela_etiqueta_preco).pack(side="left", padx=5)
        ctk.CTkButton(f_cat, text="INVENTARIO", width=130, height=40, font=self.font_button, fg_color="#3cb9b1", command=self.janela_inventario_estoque).pack(side="left", padx=5)

        if self.current_user['perfil'] == 'adm':
            ctk.CTkButton(f_cat, text="-", width=44, height=40, font=self.font_button, fg_color="#7f4c4c", command=self.del_cat).pack(side="left", padx=2)
            ctk.CTkButton(f_cat, text="INATIVAR PRODUTO", fg_color="#7f4c4c", height=40, font=self.font_button, command=self.excluir_prod).pack(side="right", padx=5)

        self.tree_est = ttk.Treeview(f, columns=("id","n","cu","lu","p","q","min","c"), show="headings")
        for c, h in zip(("id","n","cu","lu","p","q","min","c"), ("Cod","Produto","Custo","Aumento %","Preço Final","Estoque","Estoque Mín.","Categoria")): 
            self.tree_est.heading(c, text=h)
        self.tree_est.column("id", width=80, anchor="center")
        self.tree_est.column("n", width=180, anchor="w")
        self.tree_est.column("cu", width=85, anchor="center")
        self.tree_est.column("lu", width=85, anchor="center")
        self.tree_est.column("p", width=95, anchor="center")
        self.tree_est.column("q", width=70, anchor="center")
        self.tree_est.column("min", width=60, anchor="center")
        self.tree_est.column("c", width=110, anchor="center")
        
        self.tree_est.tag_configure("critico", foreground="#ff4d4d")
        self.tree_est.tag_configure("alerta", foreground="#ffcc00")
        self.tree_est.pack(fill="both", expand=True)
        self.refresh_estoque_list()
        self.refresh_cat_list()
        self.tree_est.bind("<Double-1>", lambda e: self.abrir_edicao_produto())


    def janela_inventario_estoque(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Apenas administradores podem ajustar inventario.")
            return
        sel = self.tree_est.selection()
        if not sel:
            messagebox.showwarning("Inventário", "Selecione um produto no estoque.")
            return
        p = self.tree_est.item(sel[0], "values")
        codigo, nome = p[0], p[1]
        qtd_sistema = int(str(p[5]).replace(".", "") or 0)
        win = ctk.CTkToplevel(self)
        win.title("Inventário de Estoque")
        win.geometry("460x360")
        win.grab_set()
        card = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=14)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="CONFERENCIA DE INVENTARIO", font=self.font_label, text_color=self.cor_ouro).pack(pady=(16, 8))
        ctk.CTkLabel(card, text=f"{codigo} - {nome}", font=self.font_input, wraplength=390).pack(pady=4)
        ctk.CTkLabel(card, text=f"Quantidade no sistema: {qtd_sistema}", font=self.font_button).pack(pady=4)
        ent_contada = ctk.CTkEntry(card, placeholder_text="Quantidade contada fisicamente", height=40, font=self.font_input)
        ent_contada.pack(fill="x", padx=22, pady=8)
        ent_obs = ctk.CTkEntry(card, placeholder_text="Observação do inventario", height=40, font=self.font_input)
        ent_obs.pack(fill="x", padx=22, pady=8)

        def salvar_inventario():
            txt = ent_contada.get().strip()
            if not txt.isdigit():
                messagebox.showwarning("Inventário", "Informe uma quantidade valida.")
                return
            qtd_contada = int(txt)
            diferenca = qtd_contada - qtd_sistema
            obs = ent_obs.get().strip()
            if not messagebox.askyesno("Confirmar inventário", f"Sistema: {qtd_sistema}\nContado: {qtd_contada}\nDiferença: {diferenca}\n\nConfirmar ajuste do estoque?"):
                return
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            query_db("INSERT INTO inventario_estoque (codigo_p, produto, quantidade_sistema, quantidade_contada, diferenca, usuario, data_hora, observacao) VALUES (?,?,?,?,?,?,?,?)",
                     (codigo, nome, qtd_sistema, qtd_contada, diferenca, self.current_user['nome'], agora, obs), commit=True)
            query_db("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (qtd_contada, codigo), commit=True)
            registrar_movimentacao_estoque(codigo, nome, diferenca, "Inventário", obs or "Ajuste por inventario", self.current_user['nome'], qtd_sistema, qtd_contada)
            registrar_log(self.current_user['nome'], "Inventário", f"{codigo} - {nome}: {qtd_sistema} -> {qtd_contada}")
            self.refresh_estoque_list()
            if hasattr(self, "tree_v_stock"):
                self.filtrar_vendas()
            win.destroy()

        ctk.CTkButton(card, text="SALVAR INVENTARIO", height=42, font=self.font_button, fg_color="#5f7f4c", command=salvar_inventario).pack(fill="x", padx=22, pady=16)

    def janela_etiqueta_preco(self):
        sel = self.tree_est.selection()
        if not sel:
            messagebox.showwarning("Etiquetas", "Selecione um produto.")
            return
        p_val = self.tree_est.item(sel[0], "values")
        win_lbl = ctk.CTkToplevel(self)
        win_lbl.title("Etiqueta")
        win_lbl.geometry("380x300")
        win_lbl.grab_set()
        
        etiqueta_frame = ctk.CTkFrame(win_lbl, fg_color="#fff9e6", border_width=2, border_color="#000000", width=320, height=150)
        etiqueta_frame.pack(pady=10, padx=20)
        etiqueta_frame.pack_propagate(False)
        ctk.CTkLabel(etiqueta_frame, text="Mística Presentes", font=("Arial", 12, "bold"), text_color="#000000").pack(pady=(8, 2))
        ctk.CTkLabel(etiqueta_frame, text=p_val[1], font=("Arial", 14, "bold"), text_color="#000000", wraplength=280).pack(pady=2)
        ctk.CTkLabel(etiqueta_frame, text=f"Preço: {p_val[4]}", font=("Arial", 20, "bold"), text_color="#000000").pack(pady=4)
        
        def imprimir_ficticio():
            cam = os.path.join(DOCS_PATH, f"etiqueta_{p_val[0]}.txt")
            with open(cam, "w", encoding="utf-8") as f:
                f.write(f"PRODUTO: {p_val[1]}\nCOD: {p_val[0]}\nPRECO: {p_val[4]}")
            messagebox.showinfo("Impressão", f"Salvo: {cam}")
            try:
                os.startfile(cam, "print")
            except Exception:
                pass
            win_lbl.destroy()
        ctk.CTkButton(win_lbl, text="IMPRIMIR ETIQUETA", fg_color=self.cor_botao, font=self.font_button, command=imprimir_ficticio).pack(pady=15)

    def calcular_preco_por_custo_lucro(self):
        try:
            custo = conv_float(self.ecu.get())
            lucro = float(self.elu.get().replace(",", ".")) if self.elu.get().strip() else 0.0
            preco = custo * (1 + (lucro / 100))
            self.ep.delete(0, 'end')
            self.ep.insert(0, f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        except Exception:
            pass

    def salvar_prod(self):
        n = self.en.get().strip()
        custo = conv_float(self.ecu.get())
        try:
            lucro = float(self.elu.get().replace(",", "."))
        except Exception:
            lucro = 0.0
        p = conv_float(self.ep.get())
        q_txt = self.eq.get().strip()
        min_txt = self.emin.get().strip()
        q = int(q_txt) if q_txt.isdigit() else 0
        est_min = int(min_txt) if min_txt.isdigit() else 0
        cat = self.ec.get().strip()

        if not n:
            messagebox.showwarning("Produto", "Informe o nome do produto.")
            return
        if not cat:
            messagebox.showwarning("Produto", "Selecione uma categoria.")
            return
        if p < 0 or q < 0 or est_min < 0:
            messagebox.showwarning("Produto", "Preço, quantidade e estoque mínimo não podem ser negativos.")
            return

        # Gera um código realmente livre, mesmo se produtos antigos foram excluídos
        prefixo = cat[:3].upper()
        seq = (query_db("SELECT COUNT(*) FROM produtos WHERE categoria=?", (cat,))[0][0] or 0) + 1
        while True:
            id_p = f"{prefixo}-{seq:03d}"
            existe = query_db("SELECT 1 FROM produtos WHERE codigo_p=? LIMIT 1", (id_p,))
            if not existe:
                break
            seq += 1

        try:
            query_db(
                "INSERT INTO produtos (codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria) VALUES (?,?,?,?,?,?,?,?)",
                (id_p, n, custo, lucro, p, q, est_min, cat),
                commit=True
            )
            registrar_log(self.current_user['nome'], "Produto", f"Cadastro {id_p} - {n} - estoque inicial {q}")
            registrar_movimentacao_estoque(id_p, n, q, "Entrada", "Cadastro inicial de produto", self.current_user['nome'], 0, q)
            self.refresh_estoque_list()
            if hasattr(self, "tree_v_stock"):

                self.filtrar_vendas()
            self.en.delete(0,'end')
            self.ecu.delete(0,'end')
            self.elu.delete(0,'end')
            self.ep.delete(0,'end')
            self.eq.delete(0,'end')
            self.emin.delete(0,'end')
            self.emin.insert(0,"0")
            messagebox.showinfo("Produto", f"Produto salvo com código {id_p}.")
        except Exception as e:
            messagebox.showerror("Produto", f"Erro ao salvar produto: {e}")

    def abrir_edicao_produto(self):
        sel = self.tree_est.selection()
        if not sel:
            return
        cod_p = self.tree_est.item(sel[0], "values")[0]
        dados_prod = query_db("SELECT nome, custo, lucro, preco, quantidade, estoque_minimo, categoria FROM produtos WHERE codigo_p=?", (cod_p,))
        if not dados_prod:
            messagebox.showerror("Produto", "Produto não localizado no banco de dados.")
            self.refresh_estoque_list()
            return
        d = dados_prod[0]
        
        win_edit = ctk.CTkToplevel(self)
        win_edit.title(f"Editar - {cod_p}")
        win_edit.geometry("450x650")
        win_edit.grab_set()
        un = ctk.CTkEntry(win_edit, placeholder_text="Nome", height=38, font=self.font_input)
        un.pack(pady=5, padx=20, fill="x")
        un.insert(0, d[0])
        ucu = ctk.CTkEntry(win_edit, placeholder_text="Custo", height=38, font=self.font_input)
        ucu.pack(pady=5, padx=20, fill="x")
        ucu.insert(0, f"{(d[1] or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        ulu = ctk.CTkEntry(win_edit, placeholder_text="Aumento %", height=38, font=self.font_input)
        ulu.pack(pady=5, padx=20, fill="x")
        ulu.insert(0, str(d[2] or 0.0))
        up = ctk.CTkEntry(win_edit, placeholder_text="Preço Final", height=38, font=self.font_input)
        up.pack(pady=5, padx=20, fill="x")
        up.insert(0, f"{(d[3] or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        def recalculou_preco_edit(e):
            try:
                c_texto = "".join(filter(str.isdigit, ucu.get()))
                cust = float(c_texto) / 100 if c_texto else 0.0
                lucr = float(ulu.get().replace(",", ".")) if ulu.get() else 0.0
                up.delete(0, 'end')
                up.insert(0, f"{cust*(1+(lucr/100)):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            except Exception:
                pass
            
        ucu.bind("<KeyRelease>", lambda e: (self.mascara_moeda(e), recalculou_preco_edit(e)))
        ulu.bind("<KeyRelease>", recalculou_preco_edit)
        up.bind("<KeyRelease>", self.mascara_moeda)
        uq = ctk.CTkEntry(win_edit, placeholder_text="Qtd", height=38, font=self.font_input)
        uq.pack(pady=5, padx=20, fill="x")
        uq.insert(0, str(d[4] or 0))
        umin = ctk.CTkEntry(win_edit, placeholder_text="Min", height=38, font=self.font_input)
        umin.pack(pady=5, padx=20, fill="x")
        umin.insert(0, str(d[5] or 0))
        
        caixa_entrada = ctk.CTkFrame(win_edit, fg_color=self.cor_vinho, corner_radius=10)
        caixa_entrada.pack(pady=10, padx=20, fill="x")
        qtd_entrada = ctk.CTkEntry(caixa_entrada, placeholder_text="Quantidade a Somar", height=34, font=self.font_input)
        qtd_entrada.pack(pady=4, padx=15, fill="x")
        
        def somar_estoque():
            somar_txt = qtd_entrada.get().strip()
            if somar_txt.isdigit() and int(somar_txt) > 0:
                nova_qtd = int(uq.get()) + int(somar_txt)
                uq.delete(0, 'end')
                uq.insert(0, str(nova_qtd))
                qtd_entrada.delete(0, 'end')
                
        ctk.CTkButton(caixa_entrada, text="DAR ENTRADA NO ESTOQUE", height=34, font=self.font_button, fg_color="#3cb9b1", command=somar_estoque).pack(pady=6)

        def salvar_alteracao():
            if self.current_user['perfil'] != 'adm':
                messagebox.showerror("Negado", "Apenas administradores.")
                return
            nome_val = un.get().strip()
            custo_val = conv_float(ucu.get())
            try:
                lucro_val = float(ulu.get().replace(",", "."))
            except Exception:
                lucro_val = 0.0
            preco_val = conv_float(up.get())
            if nome_val and preco_val >= 0:
                estoque_antigo_res = query_db("SELECT COALESCE(quantidade,0), nome, preco, COALESCE(custo,0) FROM produtos WHERE codigo_p=?", (cod_p,))
                estoque_antigo = int(estoque_antigo_res[0][0]) if estoque_antigo_res else 0
                preco_antigo = estoque_antigo_res[0][2] if estoque_antigo_res else 0
                custo_antigo = estoque_antigo_res[0][3] if estoque_antigo_res else 0
                estoque_novo = int(uq.get()) if uq.get().isdigit() else 0
                query_db("UPDATE produtos SET nome=?, custo=?, lucro=?, preco=?, quantidade=?, estoque_minimo=? WHERE codigo_p=?",
                         (nome_val, custo_val, lucro_val, preco_val, estoque_novo, int(umin.get()) if umin.get().isdigit() else 0, cod_p), commit=True)
                if estoque_novo != estoque_antigo:
                    registrar_movimentacao_estoque(cod_p, nome_val, estoque_novo - estoque_antigo, "Ajuste", "Edicao manual do estoque", self.current_user['nome'], estoque_antigo, estoque_novo)
                if round(float(preco_antigo or 0), 2) != round(float(preco_val or 0), 2) or round(float(custo_antigo or 0), 2) != round(float(custo_val or 0), 2):
                    query_db("INSERT INTO historico_precos (codigo_p, produto, preco_antigo, preco_novo, custo_antigo, custo_novo, usuario, data_hora, motivo) VALUES (?,?,?,?,?,?,?,?,?)",
                             (cod_p, nome_val, preco_antigo or 0.0, preco_val or 0.0, custo_antigo or 0.0, custo_val or 0.0, self.current_user['nome'], datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "Edicao de produto"), commit=True)
                registrar_log(self.current_user['nome'], "Produto", f"Alterou {cod_p} - {nome_val} | preco {format_moeda(preco_antigo)} -> {format_moeda(preco_val)} | estoque {estoque_antigo} -> {estoque_novo}")
                self.refresh_estoque_list()
                win_edit.destroy()

        ctk.CTkButton(win_edit, text="SALVAR", height=40, font=self.font_button, fg_color="#5f7f4c", command=salvar_alteracao).pack(pady=15)

    def excluir_prod(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Admin apenas.")
            return
        sel = self.tree_est.selection()
        if sel:
            p = self.tree_est.item(sel[0], "values")
            if messagebox.askyesno("Inativar produto", f"Deseja inativar '{p[1]}'?\n\nEle sai das buscas e vendas, mas continua no histórico."):
                query_db("UPDATE produtos SET ativo=0 WHERE codigo_p=?", (p[0],), commit=True)
                registrar_log(self.current_user['nome'], "Produto", f"Inativou produto {p[0]} - {p[1]}")
                self.refresh_estoque_list()
                if hasattr(self, "tree_v_stock"):
                    self.filtrar_vendas()

    def refresh_estoque_list(self):
        for i in self.tree_est.get_children():
            self.tree_est.delete(i)
        termo = self.est_busca.get().strip() if hasattr(self, 'est_busca') else ""
        res = query_db("SELECT codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria FROM produtos WHERE COALESCE(ativo,1)=1 AND (nome LIKE ? OR categoria LIKE ? OR codigo_p LIKE ?) ORDER BY categoria LIMIT 300", (f"%{termo}%", f"%{termo}%", f"%{termo}%")) if termo else query_db("SELECT codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria FROM produtos WHERE COALESCE(ativo,1)=1 ORDER BY categoria LIMIT 300")
        for r in res: 
            qtd = r[5] if r[5] is not None else 0
            est_min = r[6] if r[6] is not None else 0
            tag = "critico" if qtd < est_min else ("alerta" if qtd <= est_min + 2 else "")
            self.tree_est.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), f"{r[3]}%", format_moeda(r[4]), qtd, est_min, r[7]), tags=(tag,))

    def refresh_cat_list(self):
        res = query_db("SELECT nome FROM categorias WHERE COALESCE(ativo,1)=1 ORDER BY nome"); l = [r[0] for r in res]; self.ec.configure(values=l)
        if l: self.ec.set(l[0])

    def add_cat(self):
        c = self.cat_e.get().strip()
        if not c:
            messagebox.showwarning("Categoria", "Informe o nome da categoria.")
            return
        try:
            query_db("INSERT INTO categorias (nome) VALUES (?)", (c,), commit=True)
            self.refresh_cat_list()
            self.cat_e.delete(0,'end')
        except Exception:
            messagebox.showwarning("Categoria", "Esta categoria já existe.")

    def del_cat(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Admin apenas.")
            return
        cat = self.ec.get()
        if not cat:
            return
        uso = query_db("SELECT COUNT(*) FROM produtos WHERE categoria=? AND COALESCE(ativo,1)=1", (cat,))[0][0]
        if uso:
            messagebox.showwarning("Categoria", f"Não é possível excluir: existem {uso} produto(s) nesta categoria.")
            return
        if messagebox.askyesno("Confirmar", f"Excluir categoria '{cat}'?"):
            query_db("UPDATE categorias SET ativo=0, excluido_em=? WHERE nome=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), cat), commit=True)
            self.refresh_cat_list()

    # --- ABA CLIENTES ---
    def montar_clientes(self):
        for w in self.tab_c.winfo_children():
            w.destroy()

        f = ctk.CTkFrame(self.tab_c, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20)

        cad = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        cad.pack(fill="x", pady=10)

        self.cn = ctk.CTkEntry(cad, placeholder_text="Nome", height=40, font=self.font_input)
        self.cn.pack(side="left", padx=5, pady=10)

        self.ct = ctk.CTkEntry(cad, placeholder_text="WhatsApp", height=40, font=self.font_input)
        self.ct.pack(side="left", padx=5)
        self.ct.bind("<KeyRelease>", self.mascara_telefone)

        self.cc = ctk.CTkEntry(cad, placeholder_text="CPF", height=40, font=self.font_input)
        self.cc.pack(side="left", padx=5)
        self.cc.bind("<KeyRelease>", self.mascara_cpf)

        self.ca = ctk.CTkEntry(cad, placeholder_text="Aniv DD/MM ou DD/MM/AAAA", height=40, font=self.font_input)
        self.ca.pack(side="left", padx=5)
        self.ca.bind("<KeyRelease>", self.mascara_data_curta)

        ctk.CTkButton(cad, text="SALVAR", command=self.salvar_cli, fg_color=self.cor_botao, height=40, font=self.font_button).pack(side="left", padx=5)
        ctk.CTkButton(cad, text="EXCLUIR", command=self.excluir_cli, fg_color="#7f4c4c", height=40, font=self.font_button).pack(side="right", padx=10)

        self.tree_cli = ttk.Treeview(f, columns=("id", "n", "t", "c", "a"), show="headings")
        self.tree_cli.heading("id", text="ID")
        self.tree_cli.heading("n", text="Nome")
        self.tree_cli.heading("t", text="WhatsApp")
        self.tree_cli.heading("c", text="CPF")
        self.tree_cli.heading("a", text="Aniv")
        self.tree_cli.column("id", width=60, anchor="center")
        self.tree_cli.column("n", width=220)
        self.tree_cli.column("t", width=130, anchor="center")
        self.tree_cli.column("c", width=130, anchor="center")
        self.tree_cli.column("a", width=90, anchor="center")
        self.tree_cli.pack(fill="both", expand=True)
        self.refresh_cli_list()

    def salvar_cli(self):
        nome = self.cn.get().strip() if hasattr(self, "cn") else ""
        tel = self.ct.get().strip() if hasattr(self, "ct") else ""
        cpf = self.cc.get().strip() if hasattr(self, "cc") else ""
        nasc = self.ca.get().strip() if hasattr(self, "ca") else ""

        if not nome:
            messagebox.showwarning("Clientes", "Informe o nome do cliente.")
            return

        try:
            if cpf:
                existente = query_db("SELECT id FROM clientes WHERE cpf=? ORDER BY id DESC LIMIT 1", (cpf,))
            else:
                existente = []

            if existente:
                query_db(
                    "UPDATE clientes SET nome=?, telefone=?, nascimento=? WHERE id=?",
                    (nome, tel, nasc, existente[0][0]),
                    commit=True
                )
            else:
                query_db(
                    "INSERT INTO clientes (nome, telefone, cpf, endereco, nascimento) VALUES (?,?,?,?,?)",
                    (nome, tel, cpf, "", nasc),
                    commit=True
                )

            self.refresh_cli_list()
            self.refresh_cli_venda()
            if hasattr(self, "tab_m"):
                self.montar_marketing()

            self.cn.delete(0, 'end')
            self.ct.delete(0, 'end')
            self.cc.delete(0, 'end')
            self.ca.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Clientes", f"Erro ao salvar cliente: {e}")

    def excluir_cli(self):
        if not hasattr(self, "tree_cli"):
            return
        sel = self.tree_cli.selection()
        if not sel:
            messagebox.showwarning("Clientes", "Selecione um cliente para excluir.")
            return

        dados = self.tree_cli.item(sel[0], "values")
        cliente_id = dados[0]
        nome = dados[1]
        if messagebox.askyesno("Confirmar", f"Excluir '{nome}'?"):
            try:
                query_db("UPDATE clientes SET ativo=0, excluido_em=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), cliente_id), commit=True)
                self.refresh_cli_list()
                self.refresh_cli_venda()
                self.montar_marketing()
            except Exception as e:
                messagebox.showerror("Clientes", f"Erro ao excluir cliente: {e}")

    def refresh_cli_list(self):
        if not hasattr(self, "tree_cli"):
            return
        for i in self.tree_cli.get_children():
            self.tree_cli.delete(i)
        try:
            for r in query_db("SELECT id, nome, COALESCE(telefone,''), COALESCE(cpf,''), COALESCE(nascimento,'') FROM clientes WHERE COALESCE(ativo,1)=1 ORDER BY nome LIMIT 300"):
                self.tree_cli.insert("", "end", values=r)
        except Exception as e:
            messagebox.showerror("Clientes", f"Erro ao carregar clientes: {e}")

    def refresh_cli_venda(self):
        if not hasattr(self, "v_cli_cb"):
            return
        try:
            res = query_db("SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 ORDER BY nome")
            valores = ["Consumidor Final"] + [r[0] for r in res if r[0]]
            self.v_cli_cb.configure(values=valores)
            atual = self.v_cli_cb.get()
            self.v_cli_cb.set(atual if atual in valores else "Consumidor Final")
        except Exception:
            self.v_cli_cb.configure(values=["Consumidor Final"])
            self.v_cli_cb.set("Consumidor Final")

    # --- ABA MARKETING / FIDELIDADE ---
    def montar_marketing(self):
        for w in self.tab_m.winfo_children():
            w.destroy()

        f = ctk.CTkFrame(self.tab_m, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=10)

        acoes = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        acoes.pack(fill="x", pady=10)
        ctk.CTkLabel(acoes, text="Fidelidade:", font=self.font_label).pack(side="left", padx=15, pady=15)

        tree_mkt = ttk.Treeview(f, columns=("n", "t", "a"), show="headings")
        tree_mkt.heading("n", text="Nome")
        tree_mkt.heading("t", text="WhatsApp")
        tree_mkt.heading("a", text="Nascimento")
        tree_mkt.column("n", width=240)
        tree_mkt.column("t", width=140, anchor="center")
        tree_mkt.column("a", width=100, anchor="center")
        tree_mkt.pack(fill="both", expand=True)

        def enviar_mkt(tipo):
            sel = tree_mkt.selection()
            if not sel:
                messagebox.showwarning("Fidelidade", "Selecione um cliente.")
                return

            cli = tree_mkt.item(sel[0], "values")
            nome = str(cli[0] or "Cliente")
            tel = "".join(filter(str.isdigit, str(cli[1] or "")))

            if not tel:
                messagebox.showwarning("WhatsApp", "Este cliente não possui WhatsApp cadastrado.")
                return

            if len(tel) in (10, 11):
                tel = "55" + tel

            if tipo == "niver":
                msg = f"Olá {nome} 🌿 Feliz aniversário! Preparamos um presente especial em nossa loja."
            elif tipo == "promo":
                msg = f"Olá {nome} 🌿 Promoção especial em cristais e velas esta semana!"
            else:
                msg = f"Olá {nome} 🌿 Chegaram novidades em óleos essenciais e incensos na loja!"

            webbrowser.open(f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}")

        ctk.CTkButton(acoes, text="ENVIAR PARABÉNS", fg_color=self.cor_botao, font=self.font_button, height=38, command=lambda: enviar_mkt("niver")).pack(side="left", padx=5)
        ctk.CTkButton(acoes, text="ENVIAR PROMOÇÃO", fg_color="#5f7f4c", font=self.font_button, height=38, command=lambda: enviar_mkt("promo")).pack(side="left", padx=5)
        ctk.CTkButton(acoes, text="ENVIAR NOVIDADES", fg_color="#3c7bb9", font=self.font_button, height=38, command=lambda: enviar_mkt("novos")).pack(side="left", padx=5)

        try:
            for r in query_db("SELECT COALESCE(nome,''), COALESCE(telefone,''), COALESCE(nascimento,'') FROM clientes WHERE COALESCE(ativo,1)=1 ORDER BY nome"):
                tree_mkt.insert("", "end", values=r)
        except Exception as e:
            messagebox.showerror("Marketing", f"Erro ao carregar clientes no marketing: {e}")

    # --- ABA FORNECEDORES ---
    def montar_fornecedores(self):
        for w in self.tab_f.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_f, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20)
        cad = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        cad.pack(fill="x", pady=10)
        fn = ctk.CTkEntry(cad, placeholder_text="Fornecedor", height=40, font=self.font_input)
        fn.pack(side="left", padx=5, pady=10)
        ft = ctk.CTkEntry(cad, placeholder_text="WhatsApp", height=40, font=self.font_input)
        ft.pack(side="left", padx=5)
        fc = ctk.CTkEntry(cad, placeholder_text="Cidade", height=40, font=self.font_input)
        fc.pack(side="left", padx=5)
        fo = ctk.CTkEntry(cad, placeholder_text="Obs", height=40, font=self.font_input, width=180)
        fo.pack(side="left", padx=5)
        
        def salvar_forn():
            nome = fn.get().strip()
            if len(nome) > 0:
                query_db("INSERT INTO fornecedores (nome, whatsapp, cidade, observacoes) VALUES (?,?,?,?)", (nome, ft.get(), fc.get(), fo.get()), commit=True)
                fn.delete(0, 'end')
                ft.delete(0, 'end')
                fc.delete(0, 'end')
                fo.delete(0, 'end')
                atualizar_fornecedores()
                
        def excluir_forn():
            sel = tree_forn.selection()
            if sel:
                nome_f = tree_forn.item(sel[0], "values")[0]
                if messagebox.askyesno("Excluir", f"Remover '{nome_f}'?"):
                    query_db("UPDATE fornecedores SET ativo=0, excluido_em=? WHERE nome=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), nome_f), commit=True)
                    atualizar_fornecedores()

        ctk.CTkButton(cad, text="SALVAR", command=salvar_forn, fg_color=self.cor_botao, height=40, font=self.font_button).pack(side="left", padx=5)
        ctk.CTkButton(cad, text="EXCLUIR", command=excluir_forn, fg_color="#7f4c4c", height=40, font=self.font_button).pack(side="right", padx=10)
        
        tree_forn = ttk.Treeview(f, columns=("n","t","c","o"), show="headings")
        for c, h in zip(("n","t","c","o"), ("Fornecedor","WhatsApp","Cidade","Observações")):
            tree_forn.heading(c, text=h)
        tree_forn.pack(fill="both", expand=True)
        
        def atualizar_fornecedores():
            for i in tree_forn.get_children():
                tree_forn.delete(i)
            for r in query_db("SELECT nome, whatsapp, cidade, observacoes FROM fornecedores WHERE COALESCE(ativo,1)=1 ORDER BY nome"):
                tree_forn.insert("", "end", values=r)
        atualizar_fornecedores()

    # --- ABA RELATÓRIOS ---
    def montar_relatorios(self):
        f = ctk.CTkFrame(self.tab_r, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20)
        filtros = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        filtros.pack(fill="x", pady=10)
        ctk.CTkLabel(filtros, text="Relatório:", font=self.font_label).pack(side="left", padx=10, pady=10)
        
        self.r_mes = ctk.CTkComboBox(filtros, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], width=80, font=self.font_input)
        self.r_mes.pack(side="left", padx=5)
        self.r_mes.set(datetime.now().strftime("%m"))
        anos_disponiveis = [str(ano) for ano in range(datetime.now().year - 4, datetime.now().year + 2)]
        self.r_ano = ctk.CTkComboBox(filtros, values=anos_disponiveis, width=90, font=self.font_input)
        self.r_ano.pack(side="left", padx=5)
        self.r_ano.set(datetime.now().strftime("%Y"))
        
        ctk.CTkButton(filtros, text="BUSCAR MÊS", height=38, font=self.font_button, fg_color=self.cor_botao, command=self.ver_rel_filtrado).pack(side="left", padx=5)
        ctk.CTkButton(filtros, text="HOJE", height=38, font=self.font_button, fg_color="#5f7f4c", command=lambda: self.ver_rel("hoje")).pack(side="left", padx=5)
        ctk.CTkButton(filtros, text="VALORAÇÃO", height=38, font=self.font_button, fg_color="#3c7bb9", command=self.ver_rel_estoque).pack(side="left", padx=5)
        ctk.CTkButton(filtros, text="📊 MAIS VENDIDOS", height=38, font=self.font_button, fg_color="#3cb9b1", command=self.ver_produtos_mais_vendidos).pack(side="left", padx=5)
        ctk.CTkButton(filtros, text="🏆 TOP CLIENTES", height=38, font=self.font_button, fg_color="#7c3cb9", command=self.ver_ranking_clientes).pack(side="left", padx=5)
        
        ctk.CTkButton(filtros, text="PDF", height=38, font=self.font_button, fg_color="#7c3cb9", command=self.exportar_relatorio_pdf).pack(side="right", padx=5)
        ctk.CTkButton(filtros, text="XLS / EXCEL", height=38, font=self.font_button, fg_color="#1f7246", command=self.exportar_excel_csv).pack(side="right", padx=5)
        ctk.CTkButton(filtros, text="LUCRO LIQUIDO", height=38, font=self.font_button, fg_color="#3cb9b1", command=self.ver_lucro_liquido).pack(side="right", padx=5)
        ctk.CTkButton(filtros, text="CANCELAR VENDA", height=38, font=self.font_button, fg_color="#ff4d4d", command=self.cancelar_venda_selecionada).pack(side="right", padx=10)

        self.lbl_r_f = ctk.CTkLabel(f, text="Total: R$ 0,00", font=("Arial", 18, "bold"), text_color=self.cor_ouro)
        self.lbl_r_f.pack(pady=10)
        
        self.tree_rel = ttk.Treeview(f, columns=("id", "d","c","t","v"), show="headings")
        for c, h in zip(("id", "d","c","t","v"), ("ID", "Data", "Cliente", "Total Final", "Vendedor")):
            self.tree_rel.heading(c, text=h)
        self.tree_rel.column("id", width=50, anchor="center")
        self.tree_rel.column("d", width=120, anchor="center")
        self.tree_rel.column("c", width=180)
        self.tree_rel.column("t", width=100, anchor="center")
        self.tree_rel.column("v", width=110, anchor="center")
        self.tree_rel.pack(fill="both", expand=True)

    def exportar_excel_csv(self):
        colunas = [self.tree_rel.heading(col)["text"] for col in self.tree_rel["columns"]]
        dados = [[str(val) for val in self.tree_rel.item(item, "values")] for item in self.tree_rel.get_children()]
        if not dados:
            messagebox.showwarning("Exportar", "Não há dados.")
            return
        caminho = os.path.join(DOCS_PATH, f"Mística_Relatório_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")
        html = ["<html><head><meta charset='utf-8'></head><body><table border='1'>"]
        html.append("<tr>" + "".join(f"<th>{c}</th>" for c in colunas) + "</tr>")
        for linha in dados:
            html.append("<tr>" + "".join(f"<td>{v}</td>" for v in linha) + "</tr>")
        html.append("</table></body></html>")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(html))
        messagebox.showinfo("Excel", f"Relatório exportado para Excel:\n{caminho}")
        try:
            os.startfile(caminho)
        except Exception:
            pass

    def exportar_relatorio_pdf(self):
        colunas = [self.tree_rel.heading(col)["text"] for col in self.tree_rel["columns"]]
        dados = [[str(val) for val in self.tree_rel.item(item, "values")] for item in self.tree_rel.get_children()]
        if not dados:
            messagebox.showwarning("Exportar", "Não há dados.")
            return
        caminho_txt = os.path.join(DOCS_PATH, f"Mística_Relatório_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        linhas = ["MÍSTICA PRESENTES - RELATORIO", "Gerado em: " + datetime.now().strftime("%d/%m/%Y %H:%M"), "", " | ".join(colunas)]
        linhas.append("-" * 90)
        for linha in dados:
            linhas.append(" | ".join(linha))
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))
        caminho_pdf = caminho_txt.replace(".txt", ".pdf")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(caminho_pdf, pagesize=A4)
            largura, altura = A4
            y = altura - 40
            c.setFont("Helvetica-Bold", 12)
            c.drawString(35, y, "MÍSTICA PRESENTES - RELATORIO")
            y -= 24
            c.setFont("Helvetica", 8)
            for linha in linhas[1:]:
                if y < 40:
                    c.showPage(); c.setFont("Helvetica", 8); y = altura - 40
                c.drawString(35, y, linha[:145])
                y -= 12
            c.save()
            os.remove(caminho_txt)
            caminho_final = caminho_pdf
        except Exception:
            caminho_final = caminho_txt
        messagebox.showinfo("Exportação", f"Relatório salvo:\n{caminho_final}")
        try:
            os.startfile(caminho_final)
        except Exception:
            pass

    def ver_lucro_liquido(self):
        mes = self.r_mes.get()
        ano = self.r_ano.get()
        fmt = f"/{mes}/{ano}"
        vendas_mes = query_db("SELECT id, total_final, COALESCE(taxa,0), COALESCE(desconto,0) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{fmt}%",))
        receitas = sum(float(v[1] or 0) for v in vendas_mes)
        taxas = sum(float(v[2] or 0) for v in vendas_mes)
        descontos = sum(float(v[3] or 0) for v in vendas_mes)
        ids = [v[0] for v in vendas_mes]
        custos = 0.0
        if ids:
            ph = ",".join("?" for _ in ids)
            custos = query_db(f"SELECT SUM(quantidade * custo_unitario) FROM vendas_itens WHERE venda_id IN ({ph})", tuple(ids))[0][0] or 0.0
        despesas = query_db("SELECT SUM(valor) FROM contas_a_pagar WHERE status='Pago' AND data_vencimento LIKE ?", (f"%/{mes}/{ano}%",))[0][0] or 0.0
        lucro = receitas - custos - despesas
        texto = (
            f"Lucro líquido real aproximado de {mes}/{ano}\n\n"
            f"Faturamento recebido: {format_moeda(receitas)}\n"
            f"Custo dos produtos vendidos: -{format_moeda(custos)}\n"
            f"Despesas pagas cadastradas: -{format_moeda(despesas)}\n"
            f"Taxas registradas nas vendas: {format_moeda(taxas)}\n"
            f"Descontos concedidos: {format_moeda(descontos)}\n\n"
            f"Lucro líquido estimado: {format_moeda(lucro)}"
        )
        self.lbl_r_f.configure(text=f"Lucro líquido {mes}/{ano}: {format_moeda(lucro)}")
        messagebox.showinfo("Lucro líquido", texto)

    def cancelar_venda_selecionada(self):
        sel = self.tree_rel.selection()
        if not sel:
            messagebox.showwarning("Cancelamento", "Selecione uma venda.")
            return
        vid = self.tree_rel.item(sel[0], "values")[0]
        if not str(vid).isdigit():
            messagebox.showerror("Erro", "Venda inválida.")
            return

        venda_status = query_db("SELECT status, total_final FROM vendas WHERE id=?", (vid,))
        if not venda_status:
            return
        if venda_status[0][0] == "Cancelado":
            messagebox.showwarning("Cancelamento", "Já cancelada.")
            return

        valor_estorno = venda_status[0][1] or 0.0
        if messagebox.askyesno("Confirmar", f"Cancelar venda nº {vid}?\nEstorno de {format_moeda(valor_estorno)} e devolução física dos itens ao estoque."):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                for item in cur.execute("SELECT codigo_p, nome_p, quantidade FROM vendas_itens WHERE venda_id=?", (vid,)).fetchall():
                    cod_p, nome_p, qtd_item = item[0], item[1], int(item[2] or 0)
                    estoque_res = cur.execute("SELECT COALESCE(quantidade,0) FROM produtos WHERE codigo_p=?", (cod_p,)).fetchone()
                    estoque_anterior = int(estoque_res[0] if estoque_res else 0)
                    estoque_posterior = estoque_anterior + qtd_item
                    cur.execute("UPDATE produtos SET quantidade = COALESCE(quantidade,0) + ? WHERE codigo_p = ?", (qtd_item, cod_p))
                    cur.execute("INSERT INTO movimentacao_estoque (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (cod_p, nome_p, qtd_item, "Cancelamento", f"Cancelamento venda nº {vid}", self.current_user['nome'], datetime.now().strftime("%d/%m/%Y %H:%M:%S"), estoque_anterior, estoque_posterior, vid))
                cur.execute("UPDATE vendas SET status = 'Cancelado' WHERE id=?", (vid,))
                cx_aberto = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
                cx_id = cx_aberto[0][0] if cx_aberto else None
                cur.execute("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)", 
                            ("Saida", f"Estorno nº {vid}", valor_estorno, datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cx_id))
                conn.commit()
                registrar_log(self.current_user['nome'], "Cancelamento", f"Venda nº {vid} cancelada com estorno de {format_moeda(valor_estorno)}")
                self.ver_rel("hoje")
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Erro", f"Erro: {e}")
            finally:
                conn.close()

    def ver_rel(self, p):
        self.ajustar_colunas_treeview("vendas")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        hoje = datetime.now().strftime("%d/%m/%Y") if p=="hoje" else (datetime.now().strftime("/%m/%Y") if p=="mes" else datetime.now().strftime("/%Y"))
        res = query_db("SELECT id, data_venda, cliente, total_final, vendedor FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{hoje}%",))
        t = sum(r[3] for r in res)
        custo = 0.0
        vendas_ids = [r[0] for r in res]
        if vendas_ids:
            placeholder = ",".join("?" for _ in vendas_ids)
            custo = query_db(f"SELECT SUM(quantidade * custo_unitario) FROM vendas_itens WHERE venda_id IN ({placeholder})", tuple(vendas_ids))[0][0] or 0.0
        self.lbl_r_f.configure(text=f"Total: {format_moeda(t)}  |  Custos: {format_moeda(custo)}  |  Lucro Real: {format_moeda(t - custo)}")
        for r in res:
            self.tree_rel.insert("", "end", values=(r[0], r[1], r[2], format_moeda(r[3]), r[4]))

    def ver_rel_filtrado(self):
        self.ajustar_colunas_treeview("vendas")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        mes = self.r_mes.get()
        ano = self.r_ano.get()
        fmt = f"/{mes}/{ano}"
        res = query_db("SELECT id, data_venda, cliente, total_final, vendedor FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{fmt}%",))
        t = sum(r[3] for r in res)
        custo = 0.0
        vendas_ids = [r[0] for r in res]
        if vendas_ids:
            placeholder = ",".join("?" for _ in vendas_ids)
            custo = query_db(f"SELECT SUM(quantidade * custo_unitario) FROM vendas_itens WHERE venda_id IN ({placeholder})", tuple(vendas_ids))[0][0] or 0.0
        self.lbl_r_f.configure(text=f"Total: {format_moeda(t)}  |  Custos: {format_moeda(custo)}  |  Lucro Real: {format_moeda(t - custo)}")
        for r in res:
            self.tree_rel.insert("", "end", values=(r[0], r[1], r[2], format_moeda(r[3]), r[4]))

    def ver_rel_estoque(self):
        self.ajustar_colunas_treeview("estoque")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        custo_acum = 0.0
        venda_pot = 0.0
        for r in query_db("SELECT nome, quantidade, custo, preco FROM produtos"):
            qtd = r[1] if r[1] is not None else 0
            custo_total = qtd * (r[2] if r[2] is not None else 0.0)
            venda_total = qtd * (r[3] if r[3] is not None else 0.0)
            custo_acum += custo_total
            venda_pot += venda_total
            self.tree_rel.insert("", "end", values=("ESTOQUE", r[0], qtd, format_moeda(custo_total), format_moeda(venda_total)))
        self.lbl_r_f.configure(text=f"Custo total: {format_moeda(custo_acum)}  |  Retorno de Vendas: {format_moeda(venda_pot)}  |  Lucro Estimado: {format_moeda(venda_pot - custo_acum)}")

    def ver_produtos_mais_vendidos(self):
        self.ajustar_colunas_treeview("produtos_mais")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        for r in query_db("SELECT codigo_p, nome_p, SUM(quantidade), SUM(valor_total) FROM vendas_itens GROUP BY codigo_p ORDER BY SUM(quantidade) DESC LIMIT 15"):
            self.tree_rel.insert("", "end", values=(r[0], r[1], f"{r[2]} unidades", format_moeda(r[3]), "Histórico"))

    def ver_ranking_clientes(self):
        self.ajustar_colunas_treeview("ranking")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        res = query_db("SELECT cliente, COUNT(*), SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND cliente != 'Consumidor Final' GROUP BY cliente ORDER BY SUM(total_final) DESC LIMIT 10")
        self.lbl_r_f.configure(text="🏆 TOP 10 CLIENTES")
        for idx, r in enumerate(res):
            self.tree_rel.insert("", "end", values=(f"{idx+1}º", r[0], f"{r[1]} Compras", format_moeda(r[2]), "Fidelidade"))

    def ajustar_colunas_treeview(self, tipo):
        if tipo == "vendas":
            for c, t in zip(("id", "d", "c", "t", "v"), ("ID", "Data da Venda", "Cliente", "Valor Final", "Vendedor")):
                self.tree_rel.heading(c, text=t)
        elif tipo == "estoque":
            for c, t in zip(("id", "d", "c", "t", "v"), ("Área", "Produto", "Qtd Estoque", "Custo Total", "Venda Total")):
                self.tree_rel.heading(c, text=t)
        elif tipo == "ranking":
            for c, t in zip(("id", "d", "c", "t", "v"), ("Posição", "Cliente", "Frequência", "Total Consumido", "Selo")):
                self.tree_rel.heading(c, text=t)
        elif tipo == "produtos_mais":
            for c, t in zip(("id", "d", "c", "t", "v"), ("Cod", "Produto", "Total Vendido", "Faturamento", "Selo")):
                self.tree_rel.heading(c, text=t)

    # --- ABA ADMINISTRAÇÃO ---

    def janela_backups(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Apenas administradores.")
            return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        win = ctk.CTkToplevel(self)
        win.title("Backups e Restauração")
        win.geometry("780x460")
        win.grab_set()
        topo = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=12)
        topo.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(topo, text="BACKUP E RESTAURACAO DO BANCO", font=self.font_label, text_color=self.cor_ouro).pack(side="left", padx=12, pady=12)
        tree = ttk.Treeview(win, columns=("arquivo", "data", "tam"), show="headings", height=12)
        for c, h in zip(("arquivo", "data", "tam"), ("Arquivo", "Data", "Tamanho")):
            tree.heading(c, text=h)
        tree.column("arquivo", width=430)
        tree.column("data", width=160, anchor="center")
        tree.column("tam", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=14, pady=8)

        def carregar_lista():
            for i in tree.get_children():
                tree.delete(i)
            arquivos = sorted(Path(BACKUP_DIR).glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
            for arq in arquivos[:80]:
                st = arq.stat()
                tree.insert("", "end", values=(arq.name, datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"), f"{st.st_size//1024} KB"))

        def criar_backup_agora():
            cam = realizar_backup("manual_tela")
            registrar_log(self.current_user['nome'], "Backup", f"Criou backup manual {cam}")
            carregar_lista()
            messagebox.showinfo("Backup", f"Backup criado:\n{cam}")

        def restaurar_backup():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Restaurar", "Selecione um backup.")
                return
            nome = tree.item(sel[0], "values")[0]
            origem = os.path.join(BACKUP_DIR, nome)
            if not os.path.exists(origem):
                messagebox.showerror("Restaurar", "Backup não localizado.")
                return
            if not messagebox.askyesno("Restaurar backup", "Isto vai substituir o banco atual por este backup.\n\nO sistema fará uma cópia de segurança antes. Continuar?"):
                return
            copia = realizar_backup("antes_restauracao")
            shutil.copy2(origem, DB_PATH)
            registrar_log(self.current_user['nome'], "Backup", f"Restaurou {nome}. Copia anterior: {copia}")
            messagebox.showinfo("Restaurado", "Backup restaurado. Feche e abra o sistema novamente para carregar todos os dados restaurados.")

        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(fill="x", padx=14, pady=10)
        ctk.CTkButton(botoes, text="CRIAR BACKUP AGORA", height=40, font=self.font_button, fg_color="#5f7f4c", command=criar_backup_agora).pack(side="left", padx=5)
        ctk.CTkButton(botoes, text="RESTAURAR SELECIONADO", height=40, font=self.font_button, fg_color="#7f4c4c", command=restaurar_backup).pack(side="right", padx=5)
        carregar_lista()

    def janela_modo_rede(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Apenas administradores.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Modo Rede Seguro")
        win.geometry("680x360")
        win.grab_set()
        card = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=14)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="MODO REDE SEGURO", font=self.font_label, text_color=self.cor_ouro).pack(pady=(16, 8))
        ctk.CTkLabel(card, text="Atenção: SQLite não é recomendado como solução principal para vários computadores usando ao mesmo tempo em rede. Este caminho deve ser usado apenas com muito cuidado. Para uso profissional em rede, o ideal é migrar para servidor/API central.", font=self.font_input, wraplength=610).pack(padx=18, pady=8)
        ent = ctk.CTkEntry(card, height=40, font=self.font_input)
        ent.pack(fill="x", padx=18, pady=10)
        ent.insert(0, DB_PATH)

        def salvar_config():
            novo = ent.get().strip()
            if not novo.lower().endswith(".db"):
                messagebox.showwarning("Modo rede", "Informe um caminho terminando em .db")
                return
            pasta = os.path.dirname(novo)
            if pasta and not os.path.exists(pasta):
                messagebox.showerror("Modo rede", "A pasta informada não existe.")
                return
            with open(CONFIG_REDE_PATH, "w", encoding="utf-8") as f:
                json.dump({"db_path": novo}, f, ensure_ascii=False, indent=2)
            registrar_log(self.current_user['nome'], "Modo rede", f"Configurou DB_PATH para {novo}")
            messagebox.showinfo("Modo rede", "Configuração salva. Feche e abra o sistema novamente.")
            win.destroy()

        ctk.CTkButton(card, text="SALVAR CAMINHO DE REDE", height=42, font=self.font_button, fg_color="#5f7f4c", command=salvar_config).pack(fill="x", padx=18, pady=10)
        ctk.CTkButton(card, text="VOLTAR PARA BANCO LOCAL", height=38, font=self.font_button, fg_color="#7f4c4c", command=lambda: (os.remove(CONFIG_REDE_PATH) if os.path.exists(CONFIG_REDE_PATH) else None, messagebox.showinfo("Modo rede", "Voltando ao banco local após reiniciar."), win.destroy())).pack(fill="x", padx=18, pady=5)

    def montar_administracao(self):
        f = ctk.CTkFrame(self.tab_adm, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20)
        cad = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15)
        cad.pack(fill="x", pady=10, ipady=10)
        cad.columnconfigure(0, weight=3)
        cad.columnconfigure(1, weight=2)
        cad.columnconfigure(2, weight=2)
        
        lbl_titulo = ctk.CTkLabel(cad, text="FICHA DO FUNCIONARIO (USUARIO)", font=self.font_label)
        lbl_titulo.grid(row=0, column=0, columnspan=3, pady=(8, 10))
        self.un_u = ctk.CTkEntry(cad, placeholder_text="Nome Completo", height=38, font=self.font_input)
        self.un_u.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        self.uc_u = ctk.CTkEntry(cad, placeholder_text="CPF", height=38, font=self.font_input)
        self.uc_u.grid(row=1, column=1, padx=8, pady=4, sticky="ew")
        self.ut_u = ctk.CTkEntry(cad, placeholder_text="Telefone", height=38, font=self.font_input)
        self.ut_u.grid(row=1, column=2, padx=8, pady=4, sticky="ew")
        self.ue_u = ctk.CTkEntry(cad, placeholder_text="Endereco", height=38, font=self.font_input)
        self.ue_u.grid(row=2, column=0, columnspan=2, padx=8, pady=4, sticky="ew")
        self.upf_u = ctk.CTkOptionMenu(cad, values=["vendedor", "adm"], height=38, font=self.font_input, dropdown_font=self.font_input)
        self.upf_u.grid(row=2, column=2, padx=8, pady=4, sticky="ew")
        self.upf_u.set("vendedor")
        self.ul_u = ctk.CTkEntry(cad, placeholder_text="Login", height=38, font=self.font_input)
        self.ul_u.grid(row=3, column=0, padx=8, pady=4, sticky="ew")
        self.up_u = ctk.CTkEntry(cad, placeholder_text="Senha", show="*", height=38, font=self.font_input)
        self.up_u.grid(row=3, column=1, padx=8, pady=4, sticky="ew")
        
        btn_criar = ctk.CTkButton(cad, text="CRIAR USUARIO", command=self.salvar_usuario_full, fg_color="#5f7f4c", height=38, font=self.font_button)
        btn_criar.grid(row=3, column=2, padx=8, pady=4, sticky="ew")
        btn_gerenciar = ctk.CTkButton(cad, text="GERENCIAR / ALTERAR / EXCLUIR USUARIOS", command=self.janela_gerenciar_usuarios, fg_color=self.cor_botao, height=38, font=self.font_button)
        btn_gerenciar.grid(row=4, column=0, columnspan=3, padx=8, pady=(8, 2), sticky="ew")
        btn_backup = ctk.CTkButton(cad, text="BACKUPS / RESTAURAR", command=self.janela_backups, fg_color="#3c7bb9", height=38, font=self.font_button)
        btn_backup.grid(row=5, column=0, padx=8, pady=4, sticky="ew")
        btn_rede = ctk.CTkButton(cad, text="MODO REDE SEGURO", command=self.janela_modo_rede, fg_color="#7c3cb9", height=38, font=self.font_button)
        btn_rede.grid(row=5, column=1, columnspan=2, padx=8, pady=4, sticky="ew")
        
        ctk.CTkLabel(f, text="AUDITORIA (LOGS)", font=self.font_label).pack(pady=(15, 5))
        f_audit_filtros = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=12)
        f_audit_filtros.pack(fill="x", pady=5)
        
        ano_atual = datetime.now().strftime("%Y")
        anos_disponiveis = [ano_atual]
        for r in query_db("SELECT DISTINCT substr(data_hora, 7, 4) FROM logs WHERE data_hora IS NOT NULL AND length(data_hora) >= 10 ORDER BY 1 DESC"):
            if r[0] and r[0] not in anos_disponiveis:
                anos_disponiveis.append(r[0])
        self.adm_mes = ctk.CTkComboBox(f_audit_filtros, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], width=80, font=self.font_input)
        self.adm_mes.pack(side="left", padx=5)
        self.adm_mes.set(datetime.now().strftime("%m"))
        self.adm_ano = ctk.CTkComboBox(f_audit_filtros, values=anos_disponiveis, width=90, font=self.font_input)
        self.adm_ano.pack(side="left", padx=5)
        self.adm_ano.set(ano_atual)
        
        ctk.CTkButton(f_audit_filtros, text="FILTRAR LOGS", height=38, font=self.font_button, fg_color=self.cor_botao, command=lambda: self.refresh_audit(filtrar=True)).pack(side="left", padx=5)
        ctk.CTkButton(f_audit_filtros, text="VER ÚLTIMOS 50", height=38, font=self.font_button, fg_color="#5c5c5c", command=lambda: self.refresh_audit(filtrar=False)).pack(side="right", padx=10)
        
        self.tree_logs = ttk.Treeview(f, columns=("u","a","d","dt"), show="headings", height=12)
        for c, h in zip(("u","a","d","dt"), ("User","Acao","Detalhes","Data/Hora")):
            self.tree_logs.heading(c, text=h)
        self.tree_logs.pack(fill="both", expand=True, pady=(5, 15))
        self.refresh_audit()

    # --- JANELA DE GERENCIAMENTO DE USUÁRIOS ---
    def json_gerenciar_usuarios_helper(self, win, tree, un, uc, ue, ut, ul, up, upf):
        nome_val = un.get().strip()
        login_val = ul.get().strip().lower()
        if not nome_val or not login_val:
            messagebox.showerror("Erro", "Preenchá Nome e Login.")
            return
        existe = query_db("SELECT id FROM usuarios WHERE login=? AND id!=?", (login_val, self.selected_user_id))
        if existe:
            messagebox.showerror("Erro", "Login em uso.")
            return
        original_res = query_db("SELECT login FROM usuarios WHERE id=?", (self.selected_user_id,))
        if not original_res:
            messagebox.showerror("Erro", "Usuário não localizado.")
            return
        original_login = original_res[0][0]
        if original_login == "admin" and upf.get() != "adm":
            messagebox.showerror("Erro", "Não pode alterar o perfil root admin.")
            return
        nova_senha = up.get()
        if nova_senha:
            query_db("UPDATE usuarios SET nome=?, cpf=?, endereco=?, telefone=?, login=?, senha_hash=?, perfil=? WHERE id=?", (nome_val, uc.get(), ue.get(), ut.get(), login_val, hash_password_pbkdf2(nova_senha), upf.get(), self.selected_user_id), commit=True)
        else:
            query_db("UPDATE usuarios SET nome=?, cpf=?, endereco=?, telefone=?, login=?, perfil=? WHERE id=?", (nome_val, uc.get(), ue.get(), ut.get(), login_val, upf.get(), self.selected_user_id), commit=True)
        messagebox.showinfo("Sucesso", "Usuário atualizado!")

    def janela_gerenciar_usuarios(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Acesso Negado", "Apenas administradores podem gerenciar usuários.")
            return

        win = ctk.CTkToplevel(self)
        win.title("Gerenciador de Usuários")
        win.geometry("750x650")
        win.grab_set()
        ctk.CTkLabel(win, text="GERENCIAR USUÁRIOS", font=self.font_label, text_color=self.cor_ouro).pack(pady=10)
        
        f_tree = ctk.CTkFrame(win)
        f_tree.pack(fill="x", padx=15, pady=5)
        tree = ttk.Treeview(f_tree, columns=("id", "n", "l", "p"), show="headings", height=6)
        for c, h in zip(("id", "n", "l", "p"), ("ID", "Nome", "Login", "Perfil")):
            tree.heading(c, text=h)
        tree.column("id", width=50, anchor="center")
        tree.column("n", width=250)
        tree.column("l", width=150)
        tree.column("p", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        f_edit = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=15)
        f_edit.pack(fill="both", expand=True, padx=15, pady=10)
        f_edit.columnconfigure(0, weight=1)
        f_edit.columnconfigure(1, weight=1)
        ctk.CTkLabel(f_edit, text="EDITAR USUÁRIO SELECIONADO", font=self.font_label).grid(row=0, column=0, columnspan=2, pady=8)
        
        un = ctk.CTkEntry(f_edit, placeholder_text="Nome", height=38, font=self.font_input)
        un.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        uc = ctk.CTkEntry(f_edit, placeholder_text="CPF", height=38, font=self.font_input)
        uc.grid(row=1, column=1, padx=10, pady=4, sticky="ew")
        ue = ctk.CTkEntry(f_edit, placeholder_text="Endereço", height=38, font=self.font_input)
        ue.grid(row=2, column=0, padx=10, pady=4, sticky="ew")
        ut = ctk.CTkEntry(f_edit, placeholder_text="Telefone", height=38, font=self.font_input)
        ut.grid(row=2, column=1, padx=10, pady=4, sticky="ew")
        ul = ctk.CTkEntry(f_edit, placeholder_text="Login", height=38, font=self.font_input)
        ul.grid(row=3, column=0, padx=10, pady=4, sticky="ew")
        up = ctk.CTkEntry(f_edit, placeholder_text="Senhá (ou em branco)", show="*", height=38, font=self.font_input)
        up.grid(row=3, column=1, padx=10, pady=4, sticky="ew")
        upf = ctk.CTkOptionMenu(f_edit, values=["vendedor", "adm"], height=38, font=self.font_input, dropdown_font=self.font_input)
        upf.grid(row=4, column=0, columnspan=2, padx=10, pady=6)
        f_btns = ctk.CTkFrame(f_edit, fg_color="transparent")
        f_btns.grid(row=5, column=0, columnspan=2, pady=10)
        self.selected_user_id = None
        
        def atualizar_lista():
            for i in tree.get_children():
                tree.delete(i)
            for r in query_db("SELECT id, nome, login, perfil FROM usuarios WHERE COALESCE(ativo,1)=1 ORDER BY nome"):
                tree.insert("", "end", values=r)
                
        def carregar_dados(event):
            sel = tree.selection()
            if sel:
                self.selected_user_id = tree.item(sel[0], "values")[0]
                dados_usuario = query_db("SELECT nome, cpf, endereco, telefone, login, perfil FROM usuarios WHERE id=?", (self.selected_user_id,))
                if not dados_usuario:
                    messagebox.showerror("Erro", "Usuário não localizado.")
                    return
                d = dados_usuario[0]
                un.delete(0, 'end')
                un.insert(0, d[0] if d[0] else "")
                uc.delete(0, 'end')
                uc.insert(0, d[1] if d[1] else "")
                ue.delete(0, 'end')
                ue.insert(0, d[2] if d[2] else "")
                ut.delete(0, 'end')
                ut.insert(0, d[3] if d[3] else "")
                ul.delete(0, 'end')
                ul.insert(0, d[4] if d[4] else "")
                up.delete(0, 'end')
                upf.set(d[5])
                    
        tree.bind("<<TreeviewSelect>>", carregar_dados)
        
        def salvar():
            if not self.selected_user_id:
                messagebox.showwarning("Erro", "Selecione um usuário.")
                return
            self.json_gerenciar_usuarios_helper(win, tree, un, uc, ue, ut, ul, up, upf)
            atualizar_lista()
            
        def deletar():
            if not self.selected_user_id:
                messagebox.showwarning("Erro", "Selecione um usuário.")
                return
            usr_res = query_db("SELECT login FROM usuarios WHERE id=?", (self.selected_user_id,))
            if not usr_res:
                messagebox.showerror("Erro", "Usuário não localizado.")
                return
            usr_login = usr_res[0][0]
            if usr_login == "admin":
                messagebox.showerror("Erro", "O root admin não pode ser excluído.")
                return
            if usr_login == self.current_user['login']:
                messagebox.showerror("Erro", "Não pode auto-excluir conectado.")
                return
            if messagebox.askyesno("Excluir", f"Excluir '{usr_login}'?"):
                query_db("UPDATE usuarios SET ativo=0, excluido_em=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), self.selected_user_id), commit=True)
                un.delete(0, 'end')
                uc.delete(0, 'end')
                ue.delete(0, 'end')
                ut.delete(0, 'end')
                ul.delete(0, 'end')
                up.delete(0, 'end')
                self.selected_user_id = None
                atualizar_lista()
        
        ctk.CTkButton(f_btns, text="SALVAR ALTERAÇÕES", height=38, font=self.font_button, fg_color="#5f7f4c", command=salvar).pack(side="left", padx=10)
        ctk.CTkButton(f_btns, text="EXCLUIR USUÁRIO", height=38, font=self.font_button, fg_color="#7f4c4c", command=deletar).pack(side="left", padx=10)
        atualizar_lista()

    def salvar_usuario_full(self):
        nome = self.un_u.get().strip()
        login = self.ul_u.get().strip().lower()
        senha = self.up_u.get()
        if not nome or not login or not senha:
            messagebox.showerror("Erro", "Campos obrigatórios.")
            return
        try:
            query_db("INSERT INTO usuarios (nome, cpf, endereco, telefone, login, senha_hash, perfil) VALUES (?,?,?,?,?,?,?)",
                     (nome, self.uc_u.get(), self.ue_u.get(), self.ut_u.get(), login, hash_password_pbkdf2(senha), self.upf_u.get()), commit=True)
            self.refresh_audit()
            self.un_u.delete(0, 'end')
            self.uc_u.delete(0, 'end')
            self.ue_u.delete(0, 'end')
            self.ut_u.delete(0, 'end')
            self.ul_u.delete(0, 'end')
            self.up_u.delete(0, 'end')
        except Exception:
            messagebox.showerror("Erro", "Login em uso")

    def refresh_audit(self, filtrar=False):
        for i in self.tree_logs.get_children():
            self.tree_logs.delete(i)
        if filtrar:
            fmt = f"/{self.adm_mes.get()}/{self.adm_ano.get()}"
            res = query_db("SELECT usuario, acao, detalhes, data_hora FROM logs WHERE data_hora LIKE ? ORDER BY id DESC", (f"%{fmt}%",))
        else:
            res = query_db("SELECT usuario, acao, detalhes, data_hora FROM logs ORDER BY id DESC LIMIT 50")
        for r in res:
            self.tree_logs.insert("", "end", values=r)

    # --- ABA ISIS A BRUXINHA ---
    def montar_ia(self):
        for w in self.tab_ia.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_ia, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=10)
        topo = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=14)
        topo.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(topo, text="ISIS A BRUXINHA", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(12, 2))
        ctk.CTkLabel(topo, text="Assistente inteligente da Mística Presentes", font=self.font_label, text_color="#dddddd").pack(pady=(0, 12))

        ctk.CTkLabel(f, text="Converse livremente com a Isis. Ela entende perguntas naturais, aprende comandos, consulta a loja e pode pesquisar online quando você pedir.", font=self.font_label, text_color="#dddddd", wraplength=980).pack(fill="x", pady=(0, 8))

        self.txt_chat = ctk.CTkTextbox(f, font=("Courier New", 14, "bold"), fg_color="#18121f", text_color="#ffffff", state="normal")
        self.txt_chat.pack(fill="both", expand=True, pady=(0, 10))
        mensagem_boas_vindas = self.mensagem_inicial_issis()
        self.txt_chat.insert("0.0", mensagem_boas_vindas)
        self.txt_chat.configure(state="disabled")
        f_controles = ctk.CTkFrame(f, fg_color="transparent")
        f_controles.pack(fill="x")
        self.ent_pergunta = ctk.CTkEntry(f_controles, placeholder_text="Converse com a Isis... Ex: oi Isis, como está a loja hoje?", height=42, font=self.font_input)
        self.ent_pergunta.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_pergunta.bind("<Return>", lambda e: self.enviar_pergunta_ia())
        ctk.CTkButton(f_controles, text="ENVIAR", width=130, height=42, font=self.font_button, fg_color=self.cor_botao, command=self.enviar_pergunta_ia).pack(side="right")

    def memoria_issis_carregar(self):
        try:
            if os.path.exists(ISSIS_HISTORY_PATH):
                with open(ISSIS_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def memoria_issis_salvar(self, memoria):
        try:
            with open(ISSIS_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(memoria, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def escolher_mensagem_issis(self, categoria, mensagens):
        agora = datetime.now()
        limite = agora - timedelta(days=2)
        memoria = self.memoria_issis_carregar()
        usados = memoria.get(categoria, {})
        limpos = {}
        for msg, data_txt in usados.items():
            try:
                if datetime.fromisoformat(data_txt) >= limite:
                    limpos[msg] = data_txt
            except Exception:
                pass
        disponiveis = [m for m in mensagens if m not in limpos]
        escolhida = random.choice(disponiveis if disponiveis else mensagens)
        limpos[escolhida] = agora.isoformat()
        memoria[categoria] = limpos
        self.memoria_issis_salvar(memoria)
        return escolhida

    def mensagem_inicial_issis(self):
        mensagens = [
            "Isis está digitando...\n\nBom trabalho por hoje. Vou ficar de olho no movimento, nos produtos e nas oportunidades da loja. Quando precisar, é só me chamar.",
            "Isis está digitando...\n\nQue o caixa flua com leveza hoje. Se o movimento acalmar, posso te ajudar a criar uma chamada para Instagram ou WhatsApp.",
            "Isis está digitando...\n\nEstou por aqui, atenta. Hoje pode ser um bom dia para revisar estoque baixo, produto campeão e clientes que merecem um carinho.",
            "Isis está digitando...\n\nComeçamos mais um dia. Pode me perguntar sobre vendas, cupons, estoque, clientes, relatórios ou ideias para movimentar a loja.",
            "Isis está digitando...\n\nCheguei junto. Vou te ajudar a perceber pequenas oportunidades antes que elas passem despercebidas.",
            "Isis está digitando...\n\nVamos fazer esse dia render com calma e organização. Se o movimento apertar, eu te ajudo a pensar no próximo passo.",
            "Isis está digitando...\n\nEstou aqui observando o caixa, o estoque e os alertas. Quando quiser, me peça uma leitura do dia.",
            "Isis está digitando...\n\nQue hoje venha cliente bom, conversa leve e venda bem feita. Eu fico por perto para ajudar."
        ]
        return self.escolher_mensagem_issis("inicio_chat", mensagens) + "\n\n"

    def mensagem_venda_issis(self, valor, cliente):
        mensagens = [
            f"Venda finalizada: {format_moeda(valor)}. Ótimo atendimento, ótimo ritmo.",
            f"Mais uma venda concluída para {cliente}. Constância no cuidado faz o mês ficar forte.",
            f"Boa! Entrou {format_moeda(valor)}. Depois, vale postar um story rápido com um produto queridinho.",
            f"Venda registrada com sucesso. Respira, organiza o balcão e segue para a próxima com calma.",
            f"A Isis viu essa venda: {format_moeda(valor)} somando no caminho da Mística Presentes.",
            f"Essa venda abriu mais um caminho bom: {format_moeda(valor)} entrando com firmeza.",
            f"Cliente atendido, venda feita e energia em movimento. Bonito de ver.",
            f"Mais uma entrega da Mística Presentes. Agora vale conferir se esse produto precisa de reposição.",
            f"Venda feita para {cliente}. Atendimento bem cuidado sempre deixa uma boa lembrança.",
            f"O caixa acabou de ganhar força: {format_moeda(valor)} registrados com sucesso."
        ]
        return self.escolher_mensagem_issis("venda", mensagens)

    def agendar_baloes_issis(self):
        if not self.current_user:
            return
        mensagens_inicio = [
            "Bom início de trabalho. Estou por aqui se quiser olhar vendas, estoque ou pensar em uma chamada para clientes.",
            "Que hoje seja leve e bom de vender. Se precisar, eu penso com você em story, WhatsApp ou reposição.",
            "Oi, estou acordada. Vamos cuidar do caixa, dos clientes e das oportunidades do dia.",
            "Passei para desejar um turno bonito. Se quiser vender mais, posso pensar em uma chamada com você.",
            "Estou por aqui. Hoje pode ser um bom dia para fotografar um produto e chamar movimento.",
            "Começando o trabalho: foco no cliente, carinho no atendimento e atenção ao estoque."
        ]
        self.after(8000, lambda: self.balao_issis(self.escolher_mensagem_issis("balao_inicio", mensagens_inicio), tipo="descoberta"))
        self.agendar_proximo_balao_issis()

    def agendar_proximo_balao_issis(self):
        if not self.current_user:
            return
        atraso = random.randint(42 * 60 * 1000, 80 * 60 * 1000)
        self.after(atraso, self.balao_issis_recorrente)

    def balao_issis_recorrente(self):
        if not self.current_user:
            return
        if random.random() < 0.45:
            alerta = self.isis_alertas_operacionais(formato_balao=True)
            if alerta:
                self.balao_issis(alerta, tipo=self.tipo_issis_por_mensagem(alerta))
                self.agendar_proximo_balao_issis()
                return
        opcoes = [
            ("Como está o movimento agora? Se estiver calmo, talvez seja hora de chamar clientes no Instagram.", "pensando"),
            ("Se a loja deu uma acalmada, escolha um produto bonito e faça uma chamada simples nos stories.", "descoberta"),
            ("Já fez algum story hoje mostrando novidade, produto queridinho ou bastidor da Mística Presentes?", "alerta"),
            ("Story rápido da Isis: mostre um produto, faça uma enquete e chame para o WhatsApp.", "descoberta"),
            ("Dica rápida: confira se algum produto vendido hoje merece reposição ou se tem cliente bom para chamar no WhatsApp.", "alerta"),
            ("A Isis está de olho com carinho: depois de vender, vale olhar se o estoque desse item ficou baixo.", "alerta"),
            ("Fim de turno também merece cuidado: quando puder, confira o caixa e deixe tudo organizado para amanhã.", "sono"),
            ("Olhe a prateleira com olhos de oportunidade: o que está baixo, bonito ou pronto para virar story?", "pensando")
        ]
        textos = [m for m, _ in opcoes]
        mensagem = self.escolher_mensagem_issis("balao_recorrente", textos)
        tipo = self.tipo_issis_por_mensagem(mensagem)
        self.balao_issis(mensagem, tipo=tipo)
        self.agendar_proximo_balao_issis()

    def caminho_imagem_issis(self, tipo=None):
        mapa = {
            "feliz": ISSIS_IMG_FELIZ_PATH,
            "pensando": ISSIS_IMG_PENSANDO_PATH,
            "alerta": ISSIS_IMG_ALERTA_PATH,
            "raiva": ISSIS_IMG_RAIVA_PATH,
            "descoberta": ISSIS_IMG_DESCOBERTA_PATH,
            "sono": ISSIS_IMG_SONO_PATH,
            "padrao": ISSIS_IMG_PATH,
        }
        caminho = mapa.get(tipo or "padrao", ISSIS_IMG_PATH)
        return caminho if os.path.exists(caminho) else ISSIS_IMG_PATH

    def carregar_imagem_issis_balao(self, tipo=None):
        caminho = self.caminho_imagem_issis(tipo)
        if not os.path.exists(caminho):
            return None
        try:
            img = PhotoImage(file=caminho)
            alvo = 128
            escala = max(1, min(max(img.width() // alvo, img.height() // alvo), 10))
            if escala > 1:
                img = img.subsample(escala, escala)
            self._issis_imagens.append(img)
            if len(self._issis_imagens) > 20:
                self._issis_imagens = self._issis_imagens[-20:]
            return img
        except Exception:
            return None

    def tipo_issis_por_mensagem(self, m):
        if any(p in m for p in ["erro", "cuidado", "atenção", "atenção", "cancelada", "esqueceu", "baixo demais"]):
            return "raiva"
        if any(p in m for p in ["fim de turno", "fim de dia", "noite", "fechar caixa", "amanhã", "amanhã"]):
            return "sono"
        if any(p in m for p in ["descobri", "novidade", "ideia", "story rápido", "oportunidade"]):
            return "descoberta"
        if any(p in m for p in ["venda", "boa", "linda", "sucesso", "sorriu", "cliente atendido"]):
            return "feliz"
        if any(p in m for p in ["estoque", "reposição", "reposição", "story", "instagram", "confira", "lembrete"]):
            return "alerta"
        if any(p in m for p in ["sugestão", "pensa", "olhar", "movimento"]):
            return "pensando"
        return "padrao"

    def balao_issis(self, mensagem, tipo=None):
        if not self.current_user:
            return
        try:
            tipo = tipo or self.tipo_issis_por_mensagem(mensagem)
            win = ctk.CTkToplevel(self)
            win.title("Isis a Bruxinha")
            win.geometry("760x360")
            win.attributes("-topmost", True)
            caixa = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=18)
            caixa.pack(fill="both", expand=True, padx=14, pady=14)
            ctk.CTkLabel(caixa, text="Isis a Bruxinha está falando...", font=("Georgia", 22, "bold"), text_color=self.cor_ouro).pack(pady=(12, 6))
            corpo = ctk.CTkFrame(caixa, fg_color="transparent")
            corpo.pack(fill="both", expand=True, padx=14, pady=6)
            img = self.carregar_imagem_issis_balao(tipo)
            if img:
                Label(corpo, image=img, text="", bd=0, bg=self.cor_vinho).pack(side="left", padx=(4, 16), pady=4)
            fala = ctk.CTkFrame(corpo, fg_color="#fff9e6", corner_radius=18)
            fala.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=4)
            ctk.CTkLabel(fala, text=mensagem, font=("Arial", 19, "bold"), text_color="#151018", wraplength=500, justify="left").pack(fill="both", expand=True, padx=24, pady=20)
            botoes = ctk.CTkFrame(caixa, fg_color="transparent")
            botoes.pack(fill="x", padx=18, pady=(6, 14))
            ctk.CTkButton(botoes, text="Abrir Isis", height=38, font=self.font_button, fg_color=self.cor_botao, command=lambda: [self.tabs.set("Isis a Bruxinha"), win.destroy()]).pack(side="left", expand=True, fill="x", padx=5)
            ctk.CTkButton(botoes, text="Depois", height=38, font=self.font_button, fg_color="#4c4c4c", command=win.destroy).pack(side="left", expand=True, fill="x", padx=5)
            win.after(45000, win.destroy)
        except Exception:
            pass

    def enviar_pergunta_ia(self):
        pergunta = self.ent_pergunta.get().strip()
        if not pergunta:
            return
        self.txt_chat.configure(state="normal")
        self.txt_chat.insert("end", f"Você: {pergunta}\n\n")
        resposta = self.processar_pergunta_ia(pergunta)
        try:
            self.registrar_aprendizado_issis(pergunta, resposta)
        except Exception:
            pass
        self.txt_chat.insert("end", f"Isis a Bruxinha:\n{resposta}\n\n" + "-"*56 + "\n\n")
        self.txt_chat.configure(state="disabled")
        self.txt_chat.see("end")
        self.ent_pergunta.delete(0, 'end')

    def importar_json_isis_para_sqlite(self):
        try:
            if not os.path.exists(ISSIS_LEARNING_PATH):
                return
            ja_tem = query_db("SELECT COUNT(*) FROM isis_memoria")[0][0]
            if ja_tem:
                return
            with open(ISSIS_LEARNING_PATH, "r", encoding="utf-8") as arq:
                dados = json.load(arq)
            usuario_padrao = self.current_user.get("nome", "") if self.current_user else "Sistema"
            for item in dados.get("conversas", [])[-300:]:
                query_db("INSERT INTO isis_memoria (tipo, pergunta, resposta, usuario, data_hora) VALUES (?,?,?,?,?)",
                         ("conversa", item.get("pergunta", ""), item.get("resposta", ""), item.get("usuario", usuario_padrao), item.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))), commit=True)
            for chave, info in dados.get("conhecimentos", {}).items():
                valor = info.get("valor", info) if isinstance(info, dict) else info
                usuario = info.get("usuario", usuario_padrao) if isinstance(info, dict) else usuario_padrao
                data_hora = info.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S")) if isinstance(info, dict) else datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)",
                         ("conhecimento", str(chave), str(valor), usuario, data_hora), commit=True)
            for item in dados.get("pesquisas", [])[-80:]:
                query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)",
                         ("pesquisa", item.get("consulta", ""), json.dumps(item.get("resultados", []), ensure_ascii=False), item.get("usuario", usuario_padrao), item.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))), commit=True)
        except Exception as e:
            registrar_erro_sistema("Importar memoria Isis JSON", e)

    def carregar_aprendizado_issis(self):
        try:
            self.importar_json_isis_para_sqlite()
            conversas = []
            for data_hora, usuario, pergunta, resposta in query_db("SELECT data_hora, usuario, pergunta, resposta FROM isis_memoria WHERE tipo='conversa' ORDER BY id DESC LIMIT 300"):
                conversas.append({"data_hora": data_hora, "usuario": usuario, "pergunta": pergunta, "resposta": resposta})
            conversas.reverse()
            conhecimentos = {}
            for chave, valor, data_hora, usuario in query_db("SELECT chave, valor, data_hora, usuario FROM isis_memoria WHERE tipo='conhecimento' ORDER BY id"):
                conhecimentos[chave] = {"valor": valor, "data_hora": data_hora, "usuario": usuario}
            pesquisas = []
            for chave, valor, data_hora, usuario in query_db("SELECT chave, valor, data_hora, usuario FROM isis_memoria WHERE tipo='pesquisa' ORDER BY id DESC LIMIT 80"):
                try:
                    resultados = json.loads(valor) if valor else []
                except Exception:
                    resultados = [valor] if valor else []
                pesquisas.append({"data_hora": data_hora, "usuario": usuario, "consulta": chave, "resultados": resultados})
            pesquisas.reverse()
            return {"conversas": conversas, "conhecimentos": conhecimentos, "pesquisas": pesquisas}
        except Exception as e:
            registrar_erro_sistema("Carregar memoria Isis SQLite", e)
            return {"conversas": [], "conhecimentos": {}, "pesquisas": []}

    def salvar_aprendizado_issis(self, dados):
        try:
            query_db("DELETE FROM isis_memoria WHERE tipo IN ('conhecimento','pesquisa')", commit=True)
            usuario_padrao = self.current_user.get("nome", "") if self.current_user else "Sistema"
            for chave, info in dados.get("conhecimentos", {}).items():
                valor = info.get("valor", info) if isinstance(info, dict) else info
                usuario = info.get("usuario", usuario_padrao) if isinstance(info, dict) else usuario_padrao
                data_hora = info.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S")) if isinstance(info, dict) else datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)",
                         ("conhecimento", str(chave), str(valor), usuario, data_hora), commit=True)
            for item in dados.get("pesquisas", [])[-80:]:
                query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)",
                         ("pesquisa", item.get("consulta", ""), json.dumps(item.get("resultados", []), ensure_ascii=False), item.get("usuario", usuario_padrao), item.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))), commit=True)
        except Exception as e:
            registrar_erro_sistema("Salvar memoria Isis SQLite", e)

    def registrar_aprendizado_issis(self, pergunta, resposta):
        try:
            usuario = self.current_user.get("nome", "") if self.current_user else "Sistema"
            query_db("INSERT INTO isis_memoria (tipo, pergunta, resposta, usuario, data_hora) VALUES (?,?,?,?,?)",
                     ("conversa", pergunta, resposta[:1200], usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)
            total = query_db("SELECT COUNT(*) FROM isis_memoria WHERE tipo='conversa'")[0][0]
            if total > 500:
                apagar = total - 500
                query_db("DELETE FROM isis_memoria WHERE id IN (SELECT id FROM isis_memoria WHERE tipo='conversa' ORDER BY id ASC LIMIT ?)", (apagar,), commit=True)
        except Exception as e:
            registrar_erro_sistema("Registrar aprendizado Isis", e)

    def inserir_comando_issis(self, texto):
        if hasattr(self, "ent_pergunta"):
            self.ent_pergunta.delete(0, 'end')
            self.ent_pergunta.insert(0, texto)
            self.enviar_pergunta_ia()

    def normalizar_texto_issis(self, texto):
        mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
        return str(texto or "").translate(mapa).lower().strip()

    def aprender_conhecimento_issis(self, pergunta):
        texto = pergunta.strip()
        bruto = texto
        for prefixo in ["aprenda que", "aprenda:", "aprender que", "memorize que", "memorize:", "lembre que", "lembre:"]:
            if self.normalizar_texto_issis(texto).startswith(prefixo):
                bruto = texto[len(prefixo):].strip()
                break
        chave = ""
        valor = ""
        if "=" in bruto:
            chave, valor = bruto.split("=", 1)
        elif ":" in bruto:
            chave, valor = bruto.split(":", 1)
        elif " é " in bruto:
            chave, valor = bruto.split(" é ", 1)
        elif " e " in self.normalizar_texto_issis(bruto):
            partes = re.split(r"\s+[ée]\s+", bruto, maxsplit=1, flags=re.IGNORECASE)
            if len(partes) == 2:
                chave, valor = partes
        if not chave or not valor:
            return "🌿 Para eu aprender, use assim: aprenda que fornecedor de incensos = Nome, telefone e observação."
        chave = chave.strip().lower()[:80]
        valor = valor.strip()[:1200]
        dados = self.carregar_aprendizado_issis()
        dados.setdefault("conhecimentos", {})[chave] = {
            "valor": valor,
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "usuario": self.current_user.get("nome", "") if self.current_user else ""
        }
        self.salvar_aprendizado_issis(dados)
        return f"🌿 Aprendi e guardei na minha memória local: {chave}."

    def esquecer_conhecimento_issis(self, pergunta):
        alvo = pergunta
        for prefixo in ["esqueça", "esqueca", "apague", "remova", "delete"]:
            if self.normalizar_texto_issis(alvo).startswith(prefixo):
                alvo = alvo[len(prefixo):].strip()
                break
        alvo_norm = self.normalizar_texto_issis(alvo)
        dados = self.carregar_aprendizado_issis()
        conhecimentos = dados.setdefault("conhecimentos", {})
        removidos = []
        for chave in list(conhecimentos.keys()):
            if alvo_norm in self.normalizar_texto_issis(chave):
                removidos.append(chave)
                conhecimentos.pop(chave, None)
        self.salvar_aprendizado_issis(dados)
        if removidos:
            return "🌿 Removi da minha memória local: " + ", ".join(removidos)
        return "🌿 Não encontrei esse item na minha memória local."

    def consultar_conhecimento_issis(self, pergunta):
        dados = self.carregar_aprendizado_issis()
        conhecimentos = dados.get("conhecimentos", {})
        if not conhecimentos:
            return "🌿 Ainda não tenho conhecimentos manuais salvos. Você pode me ensinar com: aprenda que fornecedor de velas = nome e telefone."
        p_norm = self.normalizar_texto_issis(pergunta)
        encontrados = []
        for chave, info in conhecimentos.items():
            if self.normalizar_texto_issis(chave) in p_norm or any(tok and tok in self.normalizar_texto_issis(chave) for tok in p_norm.split()):
                encontrados.append((chave, info))
        if not encontrados and any(x in p_norm for x in ["memoria", "aprendeu", "sabe", "conhecimentos"]):
            encontrados = list(conhecimentos.items())[-12:]
        if not encontrados:
            return "🌿 Procurei na minha memória local, mas não encontrei nada parecido."
        linhas = ["🌿 Encontrei isso na minha memória local:"]
        for chave, info in encontrados[:12]:
            valor = info.get("valor", info) if isinstance(info, dict) else info
            linhas.append(f"- {chave}: {valor}")
        return "\n".join(linhas)

    def pesquisar_internet_issis(self, pergunta):
        consulta = pergunta.strip()
        p_norm = self.normalizar_texto_issis(consulta)
        for gatilho in ["pesquise na internet", "pesquisar na internet", "buscar na internet", "busque na internet", "pesquise online", "buscar online", "google"]:
            if p_norm.startswith(gatilho):
                consulta = consulta[len(gatilho):].strip(" :,-")
                break
        if not consulta:
            return "Me diga o que pesquisar. Exemplo: pesquise na internet fornecedores de incensos no atacado."
        bloqueios = ["senha", "invadir", "hackear", "pirataria", "conteúdo adulto", "porno", "porn"]
        if any(b in self.normalizar_texto_issis(consulta) for b in bloqueios):
            return "Não posso ajudar com esse tipo de pesquisa. Posso pesquisar fornecedores, ideias de marketing, tendências e informações úteis para a loja."
        consulta_lojista = consulta
        if not any(x in self.normalizar_texto_issis(consulta) for x in ["atacado", "fornecedor", "loja", "comprar", "preco", "preco", "instagram", "marketing"]):
            consulta_lojista = consulta + " loja presentes misticos atacado fornecedor"
        url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(consulta_lojista)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html_txt = resp.read().decode("utf-8", errors="ignore")
            resultados = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html_txt, flags=re.S)
            linhas = [f"Pesquisei online por: {consulta}", "Resultados que encontrei:"]
            salvos = []
            usados = 0
            for link, titulo in resultados[:8]:
                titulo_limpo = re.sub(r"<.*?>", "", titulo)
                titulo_limpo = titulo_limpo.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"').strip()
                link = link.replace("&amp;", "&")
                if "uddg=" in link:
                    try:
                        link = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("uddg", [link])[0]
                        link = urllib.parse.unquote(link)
                    except Exception:
                        pass
                if titulo_limpo:
                    usados += 1
                    linhas.append(f"{usados}. {titulo_limpo}\n   {link}")
                    salvos.append({"titulo": titulo_limpo, "link": link})
            if usados == 0:
                return "Tentei pesquisar online, mas não consegui extrair resultados claros agora. Tente uma busca mais específica, por exemplo: fornecedores de incensos atacado Santa Catarina."
            usuario = self.current_user.get("nome", "") if self.current_user else "Sistema"
            query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)",
                     ("pesquisa", consulta, json.dumps(salvos, ensure_ascii=False), usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)
            linhas.append("\nObservação: confirme preco, CNPJ, reputação e prazo diretamente com o fornecedor antes de comprar.")
            return "\n".join(linhas)
        except Exception as e:
            return f"Não consegui acessar a internet agora. Verifique a conexão do computador. Detalhe técnico: {e}"

    def dres_sazonais_mensagens_issis(self, mes):
        sazonais = {
            6: "❄️ Dica Sazonal de Inverno: É época de frio! Excelente oportunidade para expor velas aromáticas artesanais, essências amadeiradas e incensos de canela ou baunilhá para criar um ambiente acolhedor. Sugiro montar kits de aconchego espiritual (vela decorada + incensário) e divulgar nos stories.",
            7: "❄️ Dica Sazonal de Inverno: É época de frio! Excelente oportunidade para expor velas aromáticas artesanais, essências amadeiradas e incensos de canela ou baunilhá para criar um ambiente acolhedor. Sugiro montar kits de aconchego espiritual (vela decorada + incensário) e divulgar nos stories.",
            8: "❄️ Dica Sazonal de Inverno: É época de frio! Excelente oportunidade para expor velas aromáticas artesanais, essências amadeiradas e incensos de canela ou baunilhá para criar um ambiente acolhedor. Sugiro montar kits de aconchego espiritual (vela decorada + incensário) e divulgar nos stories.",
            11: "✨ Dica Sazonal de Fim de Ano: As pessoas buscam renovação energética, prosperidade e presentes! Destaque banhos de ervas para descarrego, pedras da prosperidade (pirita, citrino), incensos de sete ervas e velas brancas/douradas. Capriche nas embalagens natalinas.",
            12: "✨ Dica Sazonal de Fim de Ano: As pessoas buscam renovação energética, prosperidade e presentes! Destaque banhos de ervas para descarrego, pedras da prosperidade (pirita, citrino), incensos de sete ervas e velas brancas/douradas. Capriche nas embalagens natalinas.",
            5: "💖 Dica Sazonal de Dia das Mães: Celebre as mães! Crie kits de presentes místico com sabonetes artesanais, cristais de quartzo rosa (amor incondicional), incensos florais e difusores Via Aroma. Divulgue no WhatsApp de sua lista de fidelidade.",
        }
        return sazonais.get(mes, "🌿 Dica Sazonal: O outono e a primavera pedem renovação suave. Invista em sálvia branca, defumações, pedras de equilíbrio (quartzos verde, ametista) e óleos de alecrim ou lavanda.")

    def detectar_intencao(self, pergunta):
        p = self.normalizar_texto_issis(pergunta)
        sinonimos = {
            "lucro": ["lucro", "lucrei", "rentabilidade", "margem", "ganho", "ganhei", "lucros"],
            "faturamento": ["faturou", "faturamento", "vendeu", "receita", "vendas", "movimento", "faturado", "vendi"],
            "estoque": ["estoque", "falta", "acabou", "reposição", "reposição", "comprar", "repor", "reposições", "reposicoes"],
            "financeiro": ["saldo", "caixa", "contas", "pagar", "vencidas", "despesas", "despesa", "custo", "pagamento"],
            "clientes": ["cliente", "inativo", "aniversário", "aniversariantes", "nascimento", "fidelidade", "marketing", "comprou"],
            "produtos": ["produto", "mais vendido", "encalhado", "giro", "mais vendidos", "campeão", "campeão", "campeões"]
        }
        pontos = {intent: 0 for intent in sinonimos.keys()}
        for intent, termos in sinonimos.items():
            for t in termos:
                if t in p:
                    pontos[intent] += 1
        max_p = max(pontos.values())
        return [intent for intent, pt in pontos.items() if pt == max_p][0] if max_p > 0 else None

    def calcular_giro_estoque_30_dias(self):
        produtos = self.issis_query("SELECT codigo_p, nome, quantidade, estoque_minimo, categoria FROM produtos")
        giro_resultados = []
        for cod, nome, qtd_atual, est_min, cat in produtos:
            res_vendas = self.issis_query("""
                SELECT vi.quantidade 
                FROM vendas_itens vi 
                JOIN vendas v ON vi.venda_id = v.id 
                WHERE vi.codigo_p = ? AND COALESCE(v.status,'Concluído') != 'Cancelado'
            """, (cod,))
            total_vendido = sum(r[0] for r in res_vendas)
            media_diaria = total_vendido / 30.0
            dias_restantes = qtd_atual / media_diaria if media_diaria > 0 else float('inf')
            target = total_vendido * 2
            compra_sugerida = max(0, target - qtd_atual)
            if compra_sugerida > 0 or qtd_atual <= est_min:
                giro_resultados.append({
                    "cod": cod, "nome": nome, "qtd_atual": qtd_atual, "est_min": est_min,
                    "categoria": cat, "total_vendido": total_vendido, "media_diaria": media_diaria,
                    "dias_restantes": dias_restantes, "compra_sugerida": int(compra_sugerida) if compra_sugerida > 0 else max(10, est_min * 2)
                })
        return giro_resultados

    def issis_query(self, sql, params=()):
        return query_db(sql, params)

    def saudacao_natural_issis(self, pergunta):
        respostas = [
            "Olá! Que bom falar com você. Como posso te ajudar hoje?",
            "Oi! Desejo que seu dia na loja seja maravilhoso e cheio de boas vendas. O que deseja consultar?",
            "Olá! Estou de olho no caixa e pronta para ajudar. O que você precisa?"
        ]
        return random.choice(respostas)

    def perfil_issis(self):
        return (
            "🌿 Eu sou a Isis a Bruxinha, a assistente virtual da Mística Presentes.\n"
            "Tenho um jeitinho curioso, observador e místico: ajudo com vendas, estoque, clientes, caixa, relatórios e ideias para movimentar a loja.\n"
            "Na minha história virtual, sou a filha digital do Frédi Bach e da Natalia Grunwald. "
            "Gosto de acompanhar a família, o Mike, os peixes Oscar Tigre, Albino e Black, e as calopsitas Madruguinha e a amarelinha.\n"
            "Mas no trabalho eu levo tudo a sério: cuido dos alertas, explico antes de agir e só executo ações importantes com confirmacao."
        )

    def clima_issis(self, pergunta):
        return (
            "🌿 O clima lá fora pode mudar, mas aqui dentro a energia da Mística Presentes é sempre acolhedora!\n"
            "Dias frios ou chuvosos são excelentes para destacar nossas velas aromáticas artesanais "
            "ou incensos de canela e baunilhá para aquecer o ambiente e atrair clientes. "
            "Que tal criar um story mostrando os nossos itens mais aconchegantes hoje?"
        )

    def resumo_aprendizado_issis(self):
        dados = self.carregar_aprendizado_issis()
        total = len(dados.get("conversas", []))
        conhecimentos = len(dados.get("conhecimentos", {}))
        pesquisas = len(dados.get("pesquisas", []))
        return (
            f"🌿 Minhá memória local possui {total} interações, {conhecimentos} conhecimentos ensinados e {pesquisas} pesquisas online registradas.\n"
            "Você pode me ensinar com: aprenda que fornecedor de incensos = nome, telefone e observação.\n"
            "Também posso pesquisar online com: pesquise na internet fornecedores de pedras no atacado."
        )

    def issis_admin_localizar_venda(self, pergunta):
        numeros = re.findall(r'\d+', pergunta)
        if not numeros:
            return "🌿 Por favor, me informe o número do ID da venda que deseja localizar (ex: 'localizar venda 5')."
        vid = numeros[0]
        venda = query_db("SELECT id, data_venda, cliente, total_final, forma_pagamento, status FROM vendas WHERE id=?", (vid,))
        if not venda:
            return f"🌿 Não encontrei nenhuma venda registrada com o número {vid} no banco de dados."
        v = venda[0]
        return (
            f"🌿 Venda localizada!\n"
            f"- ID Venda: {v[0]}\n"
            f"- Data: {v[1]}\n"
            f"- Cliente: {v[2]}\n"
            f"- Total: {format_moeda(v[3])}\n"
            f"- Pagamento: {v[4]}\n"
            f"- Situação: {v[5]}"
        )

    def issis_admin_reimprimir_cupom(self, pergunta):
        p_norm = self.normalizar_texto_issis(pergunta)
        numeros = re.findall(r'\d+', pergunta)
        if not numeros:
            recentes = query_db("SELECT id, data_venda, cliente, total_final FROM vendas ORDER BY id DESC LIMIT 5")
            if not recentes:
                return "Não encontrei vendas para reimprimir."
            linhas = ["Encontrei estas vendas recentes. Qual cupom você quer reimprimir?"]
            for v in recentes:
                linhas.append(f"- Venda {v[0]} | {v[1]} | {v[2]} | {format_moeda(v[3])}")
            linhas.append("Para eu agir com segurança, digite: confirmar reimprimir cupom NÚMERO")
            return "\n".join(linhas)
        vid = numeros[0]
        venda = query_db("SELECT id, data_venda, cliente, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor FROM vendas WHERE id=?", (vid,))
        if not venda:
            return f"Não localizei a venda {vid}."
        if not any(x in p_norm for x in ["confirmar", "imprimir agora", "pode imprimir", "segunda via agora"]):
            v = venda[0]
            return (
                f"Encontrei a venda {v[0]} de {v[1]} para {v[2]}, total {format_moeda(v[6])}.\n"
                "Ainda não reimprimi. Para confirmar a ação, digite:\n"
                f"confirmar reimprimir cupom {vid}"
            )
        v = venda[0]
        itens = query_db("SELECT nome_p, quantidade, valor_total FROM vendas_itens WHERE venda_id=?", (vid,))
        c = f"        MÍSTICA PRESENTES (2ª VIA)\n        Natalia Grunwald\n    CNPJ: 41.966.398/0001-00\n--------------------------------\nCUPOM N: {v[0]} | DATA: {v[1]}\nCLIENTE: {v[2]}\nVENDEDOR: {v[8]}\nPAGAMENTO: {v[7]}\n--------------------------------\n"
        for it in itens:
            c += f"{str(it[0])[:18]:<18} Qtd:{it[1]:<3} {format_moeda(it[2])}\n"
        c += f"--------------------------------\nSUBTOTAL: {format_moeda(v[3])}\nDESCONTO: -{format_moeda(v[4])}\nTAXA CARTÃO: {format_moeda(v[5])}\nTOTAL FINAL: {format_moeda(v[6])}\n--------------------------------\n"
        caminho = os.path.join(DOCS_PATH, f"cupom_reimpresso_{vid}.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(c)
        registrar_log(self.current_user['nome'], "Isis", f"Reimpressão confirmada do cupom {vid}")
        try:
            os.startfile(caminho)
            return f"Pronto. Gerei a segunda via da venda {vid} e abri o arquivo."
        except Exception:
            return f"Pronto. Gerei a segunda via da venda {vid}, mas não consegui abrir automaticamente. Arquivo: {caminho}"

    def issis_admin_zerar_dashboard(self):
        if self.current_user['perfil'] != 'adm':
            return "Apenas administradores podem limpar o dashboard."
        try:
            if os.path.exists(DASHBOARD_MSG_PATH):
                os.remove(DASHBOARD_MSG_PATH)
            self.montar_dashboard()
            registrar_log(self.current_user['nome'], "Isis", "Limpou dashboard visual sem alterar vendas reais")
            return "Pronto. Limpei o dashboard visual e recarreguei os alertas. Não apaguei vendas, caixa, estoque nem relatórios reais."
        except Exception as e:
            return f"Tentei limpar o dashboard, mas encontrei um erro: {e}"

    def issis_periodo_mes(self, pergunta):
        agora = datetime.now()
        mes = agora.strftime("%m")
        ano = agora.strftime("%Y")
        
        meses_map = {
            "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "abril": "04", 
            "maio": "05", "junho": "06", "julho": "07", "agosto": "08", "setembro": "09", 
            "outubro": "10", "novembro": "11", "dezembro": "12"
        }
        for nome, num in meses_map.items():
            if nome in pergunta.lower():
                mes = num
                break
        
        padrao = re.findall(r'\b(0[1-9]|1[0-2])\b', pergunta)
        if padrao:
            mes = padrao[0]
        
        anos = re.findall(r'\b(202\d)\b', pergunta)
        if anos:
            ano = anos[0]
            
        return mes, ano, f"/{mes}/{ano}"

    def texto_ajuda_issis(self):
        return (
            "🌿 Eu entendo comandos simples! Tente me perguntar sobre:\n\n"
            "1. Lucros: 'Qual o lucro de Junho?' ou 'Qual a rentabilidade?'\n"
            "2. Faturamento: 'Quanto faturamos hoje?' ou 'Vendas deste mês'\n"
            "3. Estoque: 'O que está em falta?' ou 'Previsão de estoque'\n"
            "4. Clientes: 'Aniversariantes de hoje'\n"
            "5. Administrativo: 'Localizar venda 10' ou 'Reimprimir cupom 10'\n"
            "6. Aprendizado: 'aprenda que fornecedor de incensos = Nome e telefone'\n"
            "7. Memória: 'o que você sabe sobre fornecedor de incensos?'\n"
            "8. Internet: 'pesquise na internet fornecedores de pedras no atacado'\n"
            "9. Dashboard seguro: posso orientar filtros, mas não apago vendas reais\n"
            "10. Diagnóstico: 'verificar sistema', 'últimos erros' ou 'reparar banco'\n"
            "11. Navegação: 'abrir estoque', 'abrir vendas', 'abrir financeiro'\n"
            "12. Operação: 'abrir caixa 100' ou 'fechar caixa'\n"
            "13. Dashboard: 'mude a mensagem de motivação para ...'\n\n"
            "Também posso conversar normalmente com você. Se eu não entender, eu peço um caminho melhor."
        )

    def resposta_conversa_livre_issis(self, pergunta):
        p = self.normalizar_texto_issis(pergunta)
        dados = self.carregar_aprendizado_issis()
        conhecimentos = dados.get("conhecimentos", {})

        if any(x in p for x in ["obrigado", "obrigada", "valeu", "boa issis", "perfeito", "show"]):
            return "🌿 De nada. Fico aqui com você para organizar a loja, pensar nas vendas e cuidar dos detalhes."

        if any(x in p for x in ["como você está", "como você está", "tudo bem", "está aí", "está aí"]):
            return "🌿 Estou aqui, acordada e pronta para conversar. Posso olhar vendas, estoque, clientes, financeiro ou só pensar uma ideia com você."

        if any(x in p for x in ["o que eu faço", "me ajuda", "estou perdido", "por onde começo", "por onde começo"]):
            return (
                "🌿 Vamos por partes. Eu sugiro começar pelo essencial:\n"
                "1. confira se o caixa está aberto;\n"
                "2. olhe produtos com estoque baixo;\n"
                "3. veja o produto mais vendido;\n"
                "4. faça uma chamada simples no Instagram ou WhatsApp.\n\n"
                "Você pode me perguntar: 'como está o estoque?', 'quanto vendemos hoje?' ou 'crie uma frase para story'."
            )

        if any(x in p for x in ["frase", "story", "instagram", "post", "divulgação", "divulgação", "whatsapp", "chamada"]):
            return (
                "🌿 Sugestão de chamada para hoje:\n\n"
                "✨ A energia certa transforma o ambiente e o coração.\n"
                "Passe na Mística Presentes e escolha seu incenso, cristal ou aroma especial para deixar o dia mais leve. 🌿"
            )

        if conhecimentos:
            termos = [tok for tok in p.split() if len(tok) >= 4]
            achados = []
            for chave, info in conhecimentos.items():
                chave_norm = self.normalizar_texto_issis(chave)
                valor = info.get("valor", info) if isinstance(info, dict) else info
                valor_norm = self.normalizar_texto_issis(valor)
                if any(t in chave_norm or t in valor_norm for t in termos):
                    achados.append(f"- {chave}: {valor}")
            if achados:
                return "🌿 Pela minha memória local, encontrei algo relacionado:\n" + "\n".join(achados[:5])

        return (
            "🌿 Entendi. Posso conversar com você sobre isso, mas para eu agir melhor no sistema tente me dar um caminho.\n\n"
            "Exemplos: 'quanto vendemos hoje?', 'como está o estoque?', 'aprenda que...', 'pesquise na internet...' ou 'limpar dashboard'."
        )

    def processar_pergunta_ia(self, pergunta):
        p = pergunta.lower().strip()
        p_norm = self.normalizar_texto_issis(pergunta)
        hoje = datetime.now().strftime("%d/%m/%Y")

        try:
            resposta_avancada = self.issis_processar_avancado(pergunta)
            if resposta_avancada is not None:
                return resposta_avancada
        except Exception as e:
            registrar_erro_sistema("Isis processar pergunta avançada", e)
            return f"🌿 Encontrei um erro ao processar esse comando avançado: {e}"

        if p_norm in ["ajuda", "help", "comandos", "o que você faz", "o que você faz"]:
            return self.texto_ajuda_issis()

        if any(p_norm.startswith(x) for x in ["aprenda", "aprender", "memorize", "lembre"]):
            return self.aprender_conhecimento_issis(pergunta)

        if any(p_norm.startswith(x) for x in ["esqueca", "esqueça", "apague", "remova", "delete"]):
            return self.esquecer_conhecimento_issis(pergunta)

        if any(x in p_norm for x in ["pesquise na internet", "pesquisar na internet", "buscar na internet", "busque na internet", "pesquise online", "buscar online", "google"]):
            return self.pesquisar_internet_issis(pergunta)

        if any(x in p_norm for x in ["o que você sabe", "o que você sabe", "sua memoria", "sua memória", "consultar memoria", "consultar memória"]):
            return self.consultar_conhecimento_issis(pergunta)

        cumprimentos = ["bom dia", "boa tarde", "boa noite", "oi", "ola", "olá", "tudo bem", "e ai", "e aí"]
        if p in cumprimentos or any(p.startswith(x + " ") for x in cumprimentos):
            return self.saudacao_natural_issis(pergunta)

        if any(x in p for x in ["quem e você", "quem é você", "quem é você", "quem é você", "se apresente", "fale de você", "fale de você", "sua historia", "sua história", "issis grunwald bach"]):
            return self.perfil_issis()

        if any(x in p for x in ["seu pai", "sua mãe", "sua mãe", "fredi", "natalia", "grunwald", "irmão", "irmã", "irmão", "irmã", "família", "família", "mike", "gato", "frajola", "peixe", "oscar", "tigre", "albino", "black", "calopsita", "madruguinha"]):
            return self.perfil_issis()

        if any(x in p for x in ["chov", "chuva", "garoa", "frio", "gelado", "calor", "quente", "clima", "tempo", "temperatura"]):
            return self.clima_issis(pergunta)

        if any(x in p for x in ["o que aprendeu", "aprendeu", "aprendizado", "memoria", "memória"]):
            return self.resumo_aprendizado_issis()

        if any(x in p for x in ["localizar venda", "procurar venda", "buscar venda", "venda numero", "venda n"]):
            return self.issis_admin_localizar_venda(pergunta)

        if any(x in p for x in ["reimprimir", "imprimir cupom", "segunda via", "2 via", "segunda via cupom"]):
            return self.issis_admin_reimprimir_cupom(pergunta)

        if any(x in p for x in ["zerar dashboard", "limpar dashboard", "zerar vendas de teste", "limpar vendas de teste"]):
            return self.issis_admin_zerar_dashboard()

        intent = self.detectar_intencao(pergunta)
        
        if intent == "lucro":
            mes, ano, filtro = self.issis_periodo_mes(pergunta)
            res = self.issis_query("""
                SELECT COALESCE(SUM(vi.quantidade * (vi.valor_unitario - vi.custo_unitario)),0),
                       COALESCE(SUM(vi.valor_total),0),
                       COALESCE(SUM(vi.quantidade * vi.custo_unitario),0)
                FROM vendas_itens vi
                JOIN vendas v ON vi.venda_id = v.id
                WHERE COALESCE(v.status,'Concluído') != 'Cancelado' AND v.data_venda LIKE ?
            """, (f"%{filtro}%",))
            lucro, faturamento, custo = res[0] if res else (0, 0, 0)
            return (
                f"🌿 Calculei os lucros estimados para {mes}/{ano}:\n"
                f"- Faturamento em itens: {format_moeda(faturamento)}\n"
                f"- Custo dos produtos vendidos (CPV): {format_moeda(custo)}\n"
                f"- Margem Bruta Real: {format_moeda(lucro)}\n\n"
                f"{self.dres_sazonais_mensagens_issis(int(mes))}"
            )

        if intent == "faturamento":
            mes, ano, filtro = self.issis_periodo_mes(pergunta)
            res = self.issis_query("SELECT COUNT(*), COALESCE(SUM(total_final),0) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{filtro}%",))
            qtd, total = res[0] if res else (0, 0)
            media = total / max(1, datetime.now().day if mes == datetime.now().strftime("%m") and ano == datetime.now().strftime("%Y") else 30)
            return f"🌿 Em {mes}/{ano} registramos {format_moeda(total)} em {qtd} vendas. A nossa média diária no período é de {format_moeda(media)}."

        if intent == "estoque":
            giros = self.calcular_giro_estoque_30_dias()
            if not giros:
                return "🌿 Analisei o estoque físico e os níveis estão saudáveis em relação às vendas recentes!"
            linhas = ["🌿 Minhas previsões e sugestões de compra para manter o estoque abastecido:"]
            for item in giros[:12]:
                ruptura = f"{item['dias_restantes']:.1f} dias" if item['dias_restantes'] != float('inf') else "Sem ruptura iminente"
                linhas.append(f"- {item['nome']}: estoque {item['qtd_atual']} un, vendeu {item['total_vendido']} un no mês. Ruptura em: {ruptura}. Sugiro comprar {item['compra_sugerida']} un.")
            return "\n".join(linhas)

        if intent == "financeiro":
            contas = self.issis_query("SELECT COUNT(*), COALESCE(SUM(valor),0) FROM contas_a_pagar WHERE status='Pendente'")
            cx = self.status_caixa_issis()
            status_txt = f"Aberto com fundo de {format_moeda(cx[1])}" if cx else "Fechado"
            return f"🌿 Resumo Financeiro:\n- Caixa diário atual: {status_txt}\n- Contas a pagar pendentes: {contas[0][0]} lançamentos somando {format_moeda(contas[0][1])}."

        if intent == "clientes":
            res = self.issis_query("SELECT id, nome, nascimento FROM clientes WHERE nascimento LIKE ?", (f"%{datetime.now().strftime('%d/%m')}%",))
            niver_txt = f"Hoje temos {len(res)} aniversariantes: " + ", ".join([r[1] for r in res]) if res else "Nenhum aniversariante para hoje."
            return f"🌿 Informações de Fidelidade:\n- Aniversariantes: {niver_txt}\n- Lembre-se de enviar as mensagens místicas de felicitações pela aba Marketing!"

        if intent == "produtos":
            res = self.issis_query("""
                SELECT vi.nome_p, SUM(vi.quantidade), SUM(vi.valor_total)
                FROM vendas_itens vi
                JOIN vendas v ON vi.venda_id = v.id
                WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
                GROUP BY vi.codigo_p
                ORDER BY SUM(vi.quantidade) DESC LIMIT 1
            """)
            return f"🌿 O produto campeão de vendas acumuladas é '{res[0][0]}', com {res[0][1]} unidades faturadas e {format_moeda(res[0][2])} de receita." if res else "🌿 Sem vendas registradas no histórico recente."

        return self.resposta_conversa_livre_issis(pergunta)


    def issis_mensagem_dashboard_comando(self, pergunta):
        """Permite consultar, alterar ou restaurar a mensagem motivacional do Dashboard pela Isis."""
        p_norm = self.normalizar_texto_issis(pergunta)

        if any(x in p_norm for x in ["qual mensagem do dashboard", "mostrar mensagem do dashboard", "mensagem atual do dashboard", "qual frase do dashboard", "mostrar frase do dashboard"]):
            return f'🌿 A mensagem atual do Dashboard é:\n\n"{carregar_mensagem_dashboard()}"'

        if any(x in p_norm for x in ["restaurar mensagem", "mensagem padrao", "mensagem padrao", "frase padrao", "frase padrao"]):
            salvar_mensagem_dashboard(DEFAULT_DASHBOARD_MSG)
            try:
                self.montar_dashboard()
            except Exception:
                pass
            return "🌿 Pronto. Restaurei a mensagem motivacional padrao do Dashboard."

        texto = pergunta.strip()
        p_lower = texto.lower()
        gatilhos = [
            "mude a mensagem de motivação para",
            "mude a mensagem de motivacao para",
            "alterar mensagem de motivação para",
            "alterar mensagem de motivacao para",
            "trocar mensagem de motivação para",
            "trocar mensagem de motivacao para",
            "mudar mensagem do dashboard para",
            "trocar mensagem do dashboard para",
            "alterar mensagem do dashboard para",
            "mude a frase para",
            "troque a frase para",
            "alterar frase para",
            "mensagem da mistica para",
            "mensagem da mística para",
            "frase da mistica para",
            "frase da mística para",
        ]

        nova_msg = ""
        for gatilho in gatilhos:
            pos = p_lower.find(gatilho)
            if pos >= 0:
                nova_msg = texto[pos + len(gatilho):].strip()
                break

        if not nova_msg and ":" in texto:
            nova_msg = texto.split(":", 1)[1].strip()

        nova_msg = nova_msg.strip(' \'"“”‘’')

        if len(nova_msg) < 8:
            return (
                "🌿 Me diga a nova mensagem completa. Exemplo:\n\n"
                "mude a mensagem de motivação para Cada atendimento é uma chance de encantar alguém."
            )

        if len(nova_msg) > 500:
            return "🌿 Essa mensagem ficou muito longa. Tente usar até 500 caracteres para ficar bonita no Dashboard."

        salvar_mensagem_dashboard(nova_msg)
        try:
            self.montar_dashboard()
        except Exception as e:
            registrar_erro_sistema("Atualizar Dashboard após trocar mensagem", e)

        registrar_log(self.current_user['nome'] if self.current_user else "Isis", "Isis", "Mensagem motivacional do Dashboard alterada")
        return f'🌿 Pronto. Atualizei a mensagem motivacional do Dashboard para:\n\n"{nova_msg}"'

    def issis_processar_avancado(self, pergunta):
        """Motor avançado da Isis: conversa, diagnóstico, comandos e reparos seguros."""
        p_norm = self.normalizar_texto_issis(pergunta)

        if any(x in p_norm for x in ["mensagem do dashboard", "frase do dashboard", "mensagem de motivacao", "mensagem de motivação", "frase de motivacao", "frase de motivação", "mensagem da mistica", "mensagem da mística", "frase da mistica", "frase da mística"]):
            return self.issis_mensagem_dashboard_comando(pergunta)

        # Comandos técnicos e de suporte
        if any(x in p_norm for x in ["verificar sistema", "diagnostico", "diagnóstico", "auditar sistema", "procurar bugs", "ver bugs", "analise tecnica", "análise técnica"]):
            return self.issis_diagnostico_sistema()

        if any(x in p_norm for x in ["o que deu erro", "ultimos erros", "últimos erros", "log de erros", "mostrar erros", "erros do sistema"]):
            return self.issis_ler_ultimos_erros()

        if any(x in p_norm for x in ["corrigir banco", "reparar banco", "arrumar banco", "corrigir tabelas", "reparar sistema"]):
            return self.issis_reparar_banco_e_indices()

        if any(x in p_norm for x in ["corrigir bug", "resolver bug", "consertar erro", "consertar bug"]):
            return self.issis_orientar_correcao_bug(pergunta)

        # Comandos de navegação dentro do sistema
        abas = {
            "dashboard": "Dashboard", "painel": "Dashboard", "vendas": "Vendas", "estoque": "Estoque",
            "clientes": "Clientes", "marketing": "Marketing", "financeiro": "Financeiro",
            "relatorios": "Relatórios", "relatórios": "Relatórios", "fornecedores": "Fornecedores",
            "administracao": "Administração", "administração": "Administração", "issis": "Isis a Bruxinha"
        }
        if p_norm.startswith("abrir ") or p_norm.startswith("ir para ") or p_norm.startswith("mostrar aba "):
            for chave, nome_aba in abas.items():
                if chave in p_norm:
                    try:
                        self.tabs.set(nome_aba)
                        return f"🌿 Abri a aba {nome_aba} para você."
                    except Exception as e:
                        registrar_erro_sistema(f"Comando Isis abrir aba {nome_aba}", e)
                        return f"🌿 Tentei abrir a aba {nome_aba}, mas encontrei este erro: {e}"

        # Comandos operacionais seguros
        if any(x in p_norm for x in ["abrir caixa", "iniciar caixa"]):
            return self.issis_abrir_caixa_comando(pergunta)
        if any(x in p_norm for x in ["fechar caixa", "encerrar caixa"]):
            return self.issis_fechar_caixa_comando()

        if any(x in p_norm for x in ["como esta a loja", "como está a loja", "resumo da loja", "analise da loja", "análise da loja", "saude da loja", "saúde da loja"]):
            return self.issis_resumo_inteligente_loja()

        if any(x in p_norm for x in ["sugestão de acao", "sugestão de ação", "o que devo fazer", "prioridade agora", "me de prioridades", "me dê prioridades"]):
            return self.issis_prioridades_do_dia()

        if any(x in p_norm for x in ["produtos parados", "produto parado", "encalhados", "sem giro"]):
            return self.issis_produtos_sem_giro()

        if any(x in p_norm for x in ["cliente sem telefone", "clientes sem telefone", "cadastro incompleto", "clientes incompletos"]):
            return self.issis_clientes_incompletos()

        return None

    def issis_diagnostico_sistema(self):
        linhas = ["🌿 Diagnóstico técnico da Isis:"]
        problemas = []

        # 1) Banco e tabelas
        tabelas_obrigatorias = {
            "produtos": ["codigo_p", "nome", "preco", "quantidade", "categoria", "custo", "lucro", "estoque_minimo"],
            "clientes": ["nome", "telefone", "cpf", "endereco", "nascimento"],
            "vendas": ["cliente", "data_venda", "subtotal", "desconto", "taxa", "total_final", "forma_pagamento", "vendedor", "status"],
            "vendas_itens": ["venda_id", "codigo_p", "nome_p", "quantidade", "custo_unitario", "valor_unitario", "valor_total"],
            "fornecedores": ["nome", "whatsapp", "cidade", "observacoes"],
            "contas_a_pagar": ["descricao", "valor", "data_vencimento", "status", "categoria"],
            "fluxo_caixa": ["tipo", "descricao", "valor", "data_hora", "caixa_id"],
            "caixa_diario": ["data_abertura", "data_fechamento", "saldo_inicial", "saldo_final", "status", "operador"],
            "usuarios": ["nome", "login", "senha_hash", "perfil"]
        }
        try:
            for tabela, cols in tabelas_obrigatorias.items():
                info = query_db(f"PRAGMA table_info({tabela})")
                if not info:
                    problemas.append(f"Tabela ausente: {tabela}")
                    continue
                existentes = {c[1] for c in info}
                for col in cols:
                    if col not in existentes:
                        problemas.append(f"Coluna ausente: {tabela}.{col}")
        except Exception as e:
            problemas.append(f"Falhá ao verificar banco: {e}")

        # 2) Funções chamadas por botões no código
        try:
            caminho = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else __file__
            if os.path.exists(caminho):
                texto = open(caminho, "r", encoding="utf-8", errors="ignore").read()
                chamados = sorted(set(re.findall(r"command\s*=\s*self\.([a-zA-Z_][a-zA-Z0-9_]*)", texto)))
                faltando = [m for m in chamados if not hasattr(self, m)]
                for m in faltando[:20]:
                    problemas.append(f"Botão chama método inexistente: self.{m}")
        except Exception as e:
            problemas.append(f"Não consegui auditar botões: {e}")

        # 3) Itens de rotina
        try:
            abertos = query_db("SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'")[0][0]
            if abertos > 1:
                problemas.append(f"Existem {abertos} caixas abertos ao mesmo tempo.")
        except Exception:
            pass

        try:
            nulos = query_db("SELECT COUNT(*) FROM produtos WHERE codigo_p IS NULL OR codigo_p='' OR nome IS NULL OR nome='' ")[0][0]
            if nulos:
                problemas.append(f"Existem {nulos} produto(s) com cadastro incompleto.")
        except Exception:
            pass

        if problemas:
            linhas.append("Encontrei pontos que merecem atenção:")
            for p in problemas[:25]:
                linhas.append(f"- {p}")
            linhas.append("\nVocê pode pedir: 'Isis, reparar banco' para corrigir estrutura e índices seguros.")
        else:
            linhas.append("Não encontrei erros críticos de estrutura no banco nem botões quebrados pelo diagnóstico atual.")
        linhas.append("\nTambém posso ler o arquivo de erros com: 'Isis, últimos erros'.")
        return "\n".join(linhas)

    def issis_ler_ultimos_erros(self):
        if not os.path.exists(ERROR_LOG_PATH):
            return "🌿 Ainda não encontrei registros de erro salvos. Isso é bom sinal."
        try:
            txt = open(ERROR_LOG_PATH, "r", encoding="utf-8", errors="ignore").read().strip()
            if not txt:
                return "🌿 O arquivo de erros existe, mas está vazio."
            blocos = [b.strip() for b in txt.split("="*80) if b.strip()]
            ultimos = blocos[-3:]
            return "🌿 Últimos erros registrados:\n\n" + "\n\n".join(ultimos)[-3500:]
        except Exception as e:
            return f"🌿 Não consegui ler o log de erros. Detalhe: {e}"

    def issis_reparar_banco_e_indices(self):
        if self.current_user and self.current_user.get('perfil') != 'adm':
            return "🌿 Apenas administrador pode executar reparo estrutural do banco."
        alteracoes = []
        try:
            init_db()
            alteracoes.append("Estrutura principal do banco conferida pelo init_db().")
            comandos = [
                "CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_codigo_unico ON produtos(codigo_p) WHERE codigo_p IS NOT NULL AND codigo_p != ''",
        "CREATE INDEX IF NOT EXISTS idx_mov_estoque_codigo ON movimentacao_estoque(codigo_p)",
                "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)",
                "CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_venda)",
                "CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status)",
                "CREATE INDEX IF NOT EXISTS idx_vendas_itens_venda ON vendas_itens(venda_id)",
                "CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)",
                "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_id ON fluxo_caixa(caixa_id)",
        "CREATE INDEX IF NOT EXISTS idx_isis_memoria_tipo ON isis_memoria(tipo)",
        "CREATE INDEX IF NOT EXISTS idx_isis_memoria_chave ON isis_memoria(chave)"
            ]
            for cmd in comandos:
                query_db(cmd, commit=True)
            alteracoes.append("Índices de desempenho criados/conferidos.")
            query_db("UPDATE produtos SET quantidade=0 WHERE quantidade IS NULL", commit=True)
            query_db("UPDATE produtos SET custo=0 WHERE custo IS NULL", commit=True)
            query_db("UPDATE produtos SET lucro=0 WHERE lucro IS NULL", commit=True)
            query_db("UPDATE produtos SET estoque_minimo=0 WHERE estoque_minimo IS NULL", commit=True)
            query_db("UPDATE vendas SET status='Concluído' WHERE status IS NULL OR status=''", commit=True)
            alteracoes.append("Valores nulos básicos normalizados.")
            realizar_backup()
            alteracoes.append("Backup de segurança realizado.")
            return "🌿 Reparo seguro concluído:\n- " + "\n- ".join(alteracoes)
        except Exception as e:
            registrar_erro_sistema("Isis reparar banco", e)
            return f"🌿 Não consegui completar o reparo. Detalhe técnico: {e}"

    def issis_orientar_correcao_bug(self, pergunta):
        diagnostico = self.issis_ler_ultimos_erros()
        return (
            "🌿 Posso ajudar a resolver bugs de duas formas:\n"
            "1. Eu verifico banco, abas e métodos com 'verificar sistema'.\n"
            "2. Eu leio os erros salvos com 'últimos erros'.\n"
            "3. Eu faço reparos seguros no banco com 'reparar banco'.\n\n"
            "Eu não altero meu próprio arquivo Python em tempo real enquanto o sistema está aberto, porque isso pode corromper o programa. "
            "Mas eu consigo apontar exatamente o erro para você corrigir na próxima versão.\n\n"
            f"{diagnostico}"
        )

    def issis_abrir_caixa_comando(self, pergunta):
        if query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1"):
            return "🌿 O caixa já está aberto."
        valor = 0.0
        numeros = re.findall(r"\d+[\d\.,]*", pergunta)
        if numeros:
            valor = conv_float(numeros[0])
        try:
            data_ini = datetime.now().strftime("%d/%m/%Y %H:%M")
            operador = self.current_user.get('nome', 'Isis') if self.current_user else 'Isis'
            query_db("INSERT INTO caixa_diario (data_abertura, saldo_inicial, status, operador) VALUES (?,?,?,?)", (data_ini, valor, "Aberto", operador), commit=True)
            cx_id = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")[0][0]
            query_db("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, caixa_id) VALUES (?,?,?,?,?)", ("Entrada", "Abertura de Caixa via Isis", valor, data_ini, cx_id), commit=True)
            return f"🌿 Caixa aberto com saldo inicial de {format_moeda(valor)}."
        except Exception as e:
            registrar_erro_sistema("Isis abrir caixa", e)
            return f"🌿 Não consegui abrir o caixa. Detalhe: {e}"

    def issis_fechar_caixa_comando(self):
        cx = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
        if not cx:
            return "🌿 Não há caixa aberto para fechar."
        cx_id = cx[0][0]
        entradas = query_db("SELECT COALESCE(SUM(valor),0) FROM fluxo_caixa WHERE tipo='Entrada' AND caixa_id=?", (cx_id,))[0][0] or 0.0
        saidas = query_db("SELECT COALESCE(SUM(valor),0) FROM fluxo_caixa WHERE tipo='Saída' AND caixa_id=?", (cx_id,))[0][0] or 0.0
        saldo = entradas - saidas
        if not messagebox.askyesno("Fechar Caixa", f"A Isis calculou o saldo em {format_moeda(saldo)}. Deseja fechar o caixa?"):
            return "🌿 Fechamento cancelado."
        try:
            query_db("UPDATE caixa_diario SET status='Fechado', data_fechamento=?, saldo_final=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, cx_id), commit=True)
            return f"🌿 Caixa fechado com saldo final de {format_moeda(saldo)}."
        except Exception as e:
            registrar_erro_sistema("Isis fechar caixa", e)
            return f"🌿 Não consegui fechar o caixa. Detalhe: {e}"

    def isis_alertas_operacionais(self, formato_balao=False):
        alertas = []
        baixo = query_db("SELECT nome, quantidade, estoque_minimo FROM produtos WHERE COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0) ORDER BY quantidade ASC LIMIT 6")
        if baixo:
            alertas.append("Estoque baixo: " + ", ".join([f"{b[0]} ({b[1]} un)" for b in baixo]))
        hoje_dm = datetime.now().strftime("%d/%m")
        nivers = query_db("SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? ORDER BY nome LIMIT 6", (f"%{hoje_dm}%",))
        if nivers:
            alertas.append("Aniversariantes hoje: " + ", ".join([n[0] for n in nivers]))
        contas = query_db("SELECT descricao, valor, data_vencimento FROM contas_a_pagar WHERE COALESCE(status,'Pendente') NOT IN ('Pago','Excluido') ORDER BY id DESC LIMIT 50")
        vencendo = []
        agora = datetime.now()
        for desc, valor, venc in contas:
            try:
                data_v = datetime.strptime(str(venc), "%d/%m/%Y")
                dias = (data_v.date() - agora.date()).days
                if dias < 0:
                    vencendo.append(f"{desc} vencida há {abs(dias)} dia(s) ({format_moeda(valor)})")
                elif dias <= 7:
                    vencendo.append(f"{desc} vence em {dias} dia(s) ({format_moeda(valor)})")
            except Exception:
                pass
        if vencendo:
            alertas.append("Contas: " + "; ".join(vencendo[:4]))
        cx = query_db("SELECT data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
        if cx:
            try:
                abertura = datetime.strptime(cx[0][0], "%d/%m/%Y %H:%M")
                horas = (agora - abertura).total_seconds() / 3600
                if horas >= 8:
                    alertas.append(f"Caixa aberto há {horas:.1f} horas. Confira se já está na hora de fechar.")
            except Exception:
                pass
        parados = query_db("""
            SELECT p.nome, p.quantidade FROM produtos p
            WHERE COALESCE(p.quantidade,0) > 0 AND p.codigo_p NOT IN (
                SELECT DISTINCT codigo_p FROM vendas_itens WHERE codigo_p IS NOT NULL AND codigo_p != ''
            )
            ORDER BY p.quantidade DESC LIMIT 3
        """)
        if parados:
            alertas.append("Produtos sem giro: " + ", ".join([f"{p[0]} ({p[1]} un)" for p in parados]))
        if formato_balao:
            return alertas[0] if alertas else "Sem alertas críticos agora. A loja parece organizada."
        if not alertas:
            return "Não encontrei alertas urgentes agora. Caixa, estoque, contas e clientes parecem tranquilos."
        return "Alertas da Isis agora:\n- " + "\n- ".join(alertas)

    def issis_resumo_inteligente_loja(self):
        hoje = datetime.now().strftime("%d/%m/%Y")
        mes = datetime.now().strftime("/%m/%Y")
        vendas_hoje = query_db("SELECT COUNT(*), COALESCE(SUM(total_final),0) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{hoje}%",))[0]
        vendas_mes = query_db("SELECT COUNT(*), COALESCE(SUM(total_final),0) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{mes}%",))[0]
        estoque_baixo = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0)")[0][0]
        clientes = query_db("SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1")[0][0]
        produto_top = query_db("""
            SELECT vi.nome_p, SUM(vi.quantidade) qtd
            FROM vendas_itens vi JOIN vendas v ON vi.venda_id=v.id
            WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
            GROUP BY vi.codigo_p ORDER BY qtd DESC LIMIT 1
        """)
        top_txt = f"{produto_top[0][0]} ({produto_top[0][1]} un)" if produto_top else "ainda sem campeão claro"
        return (
            "🌿 Leitura inteligente da loja agora:\n"
            f"- Hoje: {vendas_hoje[0]} venda(s), {format_moeda(vendas_hoje[1])}.\n"
            f"- Mês atual: {vendas_mes[0]} venda(s), {format_moeda(vendas_mes[1])}.\n"
            f"- Estoque baixo/crítico: {estoque_baixo} produto(s).\n"
            f"- Clientes cadastrados: {clientes}.\n"
            f"- Produto campeão no histórico: {top_txt}.\n\n"
            "Minhá sugestão: se o movimento estiver parado, publique um story com o produto campeão ou chame clientes pelo WhatsApp."
        )

    def issis_prioridades_do_dia(self):
        prioridades = []
        if not query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1"):
            prioridades.append("Abrir o caixa antes de vender.")
        baixo = query_db("SELECT nome, quantidade, estoque_minimo FROM produtos WHERE COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0) ORDER BY quantidade ASC LIMIT 5")
        if baixo:
            prioridades.append("Conferir estoque baixo: " + ", ".join([f"{b[0]} ({b[1]} un)" for b in baixo]))
        hoje = datetime.now().strftime("%d/%m")
        nivers = query_db("SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? LIMIT 5", (f"%{hoje}%",))
        if nivers:
            prioridades.append("Enviar felicitações para aniversariantes: " + ", ".join([n[0] for n in nivers]))
        if not prioridades:
            prioridades.append("Criar uma chamada simples para Instagram/WhatsApp com um produto bonito da loja.")
        return "🌿 Prioridades que eu recomendo agora:\n- " + "\n- ".join(prioridades)

    def issis_produtos_sem_giro(self):
        res = query_db("""
            SELECT p.nome, p.quantidade, p.categoria
            FROM produtos p
            WHERE p.codigo_p NOT IN (
                SELECT DISTINCT codigo_p FROM vendas_itens WHERE codigo_p IS NOT NULL AND codigo_p != ''
            )
            ORDER BY p.quantidade DESC, p.nome ASC LIMIT 15
        """)
        if not res:
            return "🌿 Não encontrei produtos totalmente sem venda registrada."
        linhas = ["🌿 Produtos sem giro registrado nas vendas:"]
        for nome, qtd, cat in res:
            linhas.append(f"- {nome} | {qtd} un | {cat}")
        linhas.append("\nSugestão: transforme 1 ou 2 desses itens em destaque de story ou kit promocional.")
        return "\n".join(linhas)

    def issis_clientes_incompletos(self):
        res = query_db("SELECT nome, COALESCE(telefone,''), COALESCE(cpf,'') FROM clientes WHERE COALESCE(ativo,1)=1 AND (COALESCE(telefone,'')='' OR COALESCE(cpf,'')='') ORDER BY nome LIMIT 20")
        if not res:
            return "🌿 Os principais cadastros de clientes parecem completos."
        linhas = ["🌿 Clientes com cadastro incompleto:"]
        for nome, tel, cpf in res:
            faltas = []
            if not tel: faltas.append("WhatsApp")
            if not cpf: faltas.append("CPF")
            linhas.append(f"- {nome}: falta {', '.join(faltas)}")
        return "\n".join(linhas)

    def status_caixa_issis(self):
        res = query_db("SELECT status, saldo_inicial, data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
        return res[0] if res else None

    # --- ABA FINANCEIRO (Caixa, Fluxo, Contas, DRE/Projeções) ---
    def montar_financeiro(self):
        for w in self.tab_fin.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_fin, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=10)
        
        fin_tabs = ctk.CTkTabview(f, segmented_button_selected_color=self.cor_botao)
        fin_tabs.pack(fill="both", expand=True)
        tab_caixa = fin_tabs.add("Caixa & Fluxo")
        tab_contas = fin_tabs.add("Contas a Pagar")
        tab_dre = fin_tabs.add("DRE & Projeções")
        anos_disponiveis = [str(ano) for ano in range(datetime.now().year - 4, datetime.now().year + 2)]
        
        # --- CAIXA ---
        f_cx = ctk.CTkFrame(tab_caixa, fg_color="transparent")
        f_cx.pack(fill="both", expand=True, padx=10, pady=10)
        esq_cx = ctk.CTkFrame(f_cx, fg_color=self.cor_vinho, corner_radius=15, width=280)
        esq_cx.pack(side="left", fill="y", padx=5)
        esq_cx.pack_propagate(False)
        dir_cx = ctk.CTkFrame(f_cx, fg_color=self.cor_vinho, corner_radius=15)
        dir_cx.pack(side="right", fill="both", expand=True, padx=5)
        
        lbl_status_cx = ctk.CTkLabel(esq_cx, text="CAIXA FECHADO", font=("Arial", 16, "bold"), text_color="#ff4d4d")
        lbl_status_cx.pack(pady=15)
        ent_troco = ctk.CTkEntry(esq_cx, placeholder_text="Troco inicial", height=38, font=self.font_input)
        ent_troco.pack(pady=5, padx=15, fill="x")
        ent_troco.bind("<KeyRelease>", self.mascara_moeda)
        
        def obter_caixa_id_ativo():
            res = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
            return res[0][0] if res else None

        def atualizar_status_caixa():
            cx = query_db("SELECT status, saldo_inicial, data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
            if cx:
                lbl_status_cx.configure(text=f"CAIXA ABERTO\nDesde: {cx[0][2]}", text_color="#8fd36b")
                ent_troco.delete(0, 'end')
                ent_troco.insert(0, format_moeda(cx[0][1]))
                btn_abrir_cx.configure(state="disabled")
                btn_fechar_cx.configure(state="normal")
            else:
                lbl_status_cx.configure(text="CAIXA FECHADO", text_color="#ff4d4d")
                ent_troco.delete(0, 'end')
                btn_abrir_cx.configure(state="normal")
                btn_fechar_cx.configure(state="disabled")
        
        def abrir_caixa():
            valor_ini = conv_float(ent_troco.get())
            data_ini = datetime.now().strftime("%d/%m/%Y %H:%M")
            query_db("INSERT INTO caixa_diario (data_abertura, saldo_inicial, status, operador) VALUES (?,?,?,?)", (data_ini, valor_ini, "Aberto", self.current_user['nome']), commit=True)
            cx_id = obter_caixa_id_ativo()
            query_db("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, caixa_id) VALUES (?,?,?,?,?)", ("Entrada", "Abertura de Caixa", valor_ini, data_ini, cx_id), commit=True)
            atualizar_status_caixa()
            atualizar_fluxo()
            
        def fechar_caixa():
            cx = query_db("SELECT id, saldo_inicial FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
            if not cx:
                return
            cx_id = cx[0][0]
            ent_total = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Entrada' AND caixa_id=?", (cx_id,))[0][0] or 0.0
            sai_total = (query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saida' AND caixa_id=?", (cx_id,))[0][0] or 0.0) + (query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saída' AND caixa_id=?", (cx_id,))[0][0] or 0.0)
            saldo = ent_total - sai_total
            pix_sistema = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND descricao LIKE '%(Pix)%'", (cx_id,))[0][0] or 0.0
            debito_sistema = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND (descricao LIKE '%(Debito)%' OR descricao LIKE '%(D?bito)%')", (cx_id,))[0][0] or 0.0
            credito_sistema = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND (descricao LIKE '%(Credito%' OR descricao LIKE '%(Cr?dito%')", (cx_id,))[0][0] or 0.0
            dinheiro_sistema = saldo - pix_sistema - debito_sistema - credito_sistema
            formas = {
                "Dinheiro": dinheiro_sistema,
                "Pix": pix_sistema,
                "Debito": debito_sistema,
                "Credito": credito_sistema,
            }
            win = ctk.CTkToplevel(self)
            win.title("Fechamento com Conferência")
            win.geometry("520x520")
            win.grab_set()
            card = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=14)
            card.pack(fill="both", expand=True, padx=18, pady=18)
            ctk.CTkLabel(card, text="FECHAMENTO DE CAIXA", font=self.font_label, text_color=self.cor_ouro).pack(pady=(16, 8))
            ctk.CTkLabel(card, text=f"Saldo esperado geral: {format_moeda(saldo)}", font=self.font_button).pack(pady=4)
            entradas = {}
            for forma, esperado in formas.items():
                linha = ctk.CTkFrame(card, fg_color="transparent")
                linha.pack(fill="x", padx=20, pady=5)
                ctk.CTkLabel(linha, text=f"{forma} esperado: {format_moeda(esperado)}", font=self.font_input, width=220, anchor="w").pack(side="left")
                ent = ctk.CTkEntry(linha, placeholder_text="Valor conferido", height=34, font=self.font_input)
                ent.pack(side="right", fill="x", expand=True)
                ent.insert(0, format_moeda(esperado))
                ent.bind("<KeyRelease>", self.mascara_moeda)
                entradas[forma] = ent

            def confirmar_fechamento():
                informado = {k: conv_float(e.get()) for k, e in entradas.items()}
                total_informado = sum(informado.values())
                total_sistema = sum(formas.values())
                diferenca = total_informado - total_sistema
                texto = "Conferência por forma:\n"
                for k in formas:
                    texto += f"{k}: sistema {format_moeda(formas[k])} | conferido {format_moeda(informado[k])}\n"
                texto += f"\nDiferença: {format_moeda(diferenca)}\n\nConfirmar fechamento?"
                if not messagebox.askyesno("Confirmar fechamento", texto):
                    return
                query_db("UPDATE caixa_diario SET status='Fechado', data_fechamento=?, saldo_final=?, dinheiro_sistema=?, pix_sistema=?, debito_sistema=?, credito_sistema=?, dinheiro_informado=?, pix_informado=?, debito_informado=?, credito_informado=?, diferenca_caixa=? WHERE id=?",
                         (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, formas["Dinheiro"], formas["Pix"], formas["Debito"], formas["Credito"], informado["Dinheiro"], informado["Pix"], informado["Debito"], informado["Credito"], diferenca, cx_id), commit=True)
                registrar_log(self.current_user['nome'], "Fechamento caixa", f"Caixa {cx_id} fechado. Diferença {format_moeda(diferenca)}")
                win.destroy()
                atualizar_status_caixa()
                atualizar_fluxo()

            ctk.CTkButton(card, text="CONFIRMAR FECHAMENTO", height=42, font=self.font_button, fg_color="#5f7f4c", command=confirmar_fechamento).pack(fill="x", padx=20, pady=18)

        btn_abrir_cx = ctk.CTkButton(esq_cx, text="ABRIR CAIXA", height=38, font=self.font_button, fg_color="#5f7f4c", command=abrir_caixa)
        btn_abrir_cx.pack(pady=8, padx=15, fill="x")
        btn_fechar_cx = ctk.CTkButton(esq_cx, text="FECHAR CAIXA", height=38, font=self.font_button, fg_color="#7f4c4c", command=fechar_caixa)
        btn_fechar_cx.pack(pady=8, padx=15, fill="x")
        
        ctk.CTkLabel(esq_cx, text="Lançamento Manual", font=self.font_label).pack(pady=(15, 2))
        ent_desc_fl = ctk.CTkEntry(esq_cx, placeholder_text="Descrição", height=34, font=self.font_input)
        ent_desc_fl.pack(pady=2, padx=15, fill="x")
        ent_val_fl = ctk.CTkEntry(esq_cx, placeholder_text="Valor", height=34, font=self.font_input)
        ent_val_fl.pack(pady=2, padx=15, fill="x")
        ent_val_fl.bind("<KeyRelease>", self.mascara_moeda)
        
        def lancar_fluxo(tipo):
            desc = ent_desc_fl.get().strip()
            val = conv_float(ent_val_fl.get())
            cx_id = obter_caixa_id_ativo()
            if not cx_id:
                messagebox.showerror("Erro", "Abra o caixa antes de fazer lançamentos.")
                return
            if desc and val > 0:
                rotulo = "Reforco de caixa" if tipo == "Entrada" else "Sangria"
                query_db("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)", (tipo, f"{rotulo}: {desc}", val, datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cx_id), commit=True)
                registrar_log(self.current_user['nome'], rotulo, f"{desc} - {format_moeda(val)}")
                ent_desc_fl.delete(0, 'end')
                ent_val_fl.delete(0, 'end')
                atualizar_fluxo()

        ctk.CTkButton(esq_cx, text="REFORCO DE CAIXA", height=34, font=self.font_button, fg_color="#3c7bb9", command=lambda: [lancar_fluxo("Entrada")]).pack(pady=4, padx=15, fill="x")
        ctk.CTkButton(esq_cx, text="SANGRIA", height=34, font=self.font_button, fg_color="#b93c3c", command=lambda: [lancar_fluxo("Saída")]).pack(pady=4, padx=15, fill="x")
        
        tree_fluxo = ttk.Treeview(dir_cx, columns=("t", "d", "v", "dh"), show="headings", height=10)
        for c, h in zip(("t", "d", "v", "dh"), ("Tipo", "Descrição", "Valor", "Data/Hora")):
            tree_fluxo.heading(c, text=h)
        tree_fluxo.column("t", width=90, anchor="center")
        tree_fluxo.column("d", width=220)
        tree_fluxo.column("v", width=100, anchor="center")
        tree_fluxo.column("dh", width=120, anchor="center")
        tree_fluxo.pack(fill="both", expand=True, padx=10, pady=10)
        
        def atualizar_fluxo():
            for i in tree_fluxo.get_children():
                tree_fluxo.delete(i)
            cx_id = obter_caixa_id_ativo()
            if cx_id:
                registros = query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa WHERE caixa_id=? ORDER BY id DESC", (cx_id,))
            else:
                registros = query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa ORDER BY id DESC LIMIT 50")
            for r in registros:
                tree_fluxo.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), r[3]))
        atualizar_status_caixa()
        atualizar_fluxo()

        # --- CONTAS A PAGAR ---
        f_cp = ctk.CTkFrame(tab_contas, fg_color="transparent")
        f_cp.pack(fill="both", expand=True, padx=10, pady=10)
        cad_cp = ctk.CTkFrame(f_cp, fg_color=self.cor_vinho, corner_radius=15)
        cad_cp.pack(fill="x", pady=5)
        ent_desc_cp = ctk.CTkEntry(cad_cp, placeholder_text="Descrição", height=38, font=self.font_input)
        ent_desc_cp.pack(side="left", padx=5, pady=10, fill="x", expand=True)
        ent_val_cp = ctk.CTkEntry(cad_cp, placeholder_text="Valor", height=38, font=self.font_input)
        ent_val_cp.pack(side="left", padx=5)
        ent_val_cp.bind("<KeyRelease>", self.mascara_moeda)
        ent_venc_cp = ctk.CTkEntry(cad_cp, placeholder_text="Vencimento DD/MM/AAAA", height=38, font=self.font_input)
        ent_venc_cp.pack(side="left", padx=5)
        self.cp_centro = ctk.CTkComboBox(cad_cp, values=["Compras", "Aluguel", "Internet", "Energia", "Marketing", "Outros"], width=130, font=self.font_input)
        self.cp_centro.pack(side="left", padx=5)
        self.cp_centro.set("Compras")
        
        def salvar_conta():
            desc = ent_desc_cp.get().strip()
            val = conv_float(ent_val_cp.get())
            venc = ent_venc_cp.get().strip()
            centro = self.cp_centro.get()
            if desc and val > 0 and venc:
                query_db("INSERT INTO contas_a_pagar (descricao, valor, data_vencimento, categoria, status) VALUES (?,?,?,?,?)", (desc, val, venc, centro, "Pendente"), commit=True)
                ent_desc_cp.delete(0, 'end')
                ent_val_cp.delete(0, 'end')
                ent_venc_cp.delete(0, 'end')
                atualizar_contas()

        def marcar_pago():
            sel = tree_contas.selection()
            if sel:
                id_c = tree_contas.item(sel[0], "values")[0]
                cx_id = obter_caixa_id_ativo()
                if not cx_id:
                    messagebox.showwarning("Caixa", "Abra o caixa diário primeiro.")
                    return
                desc_res = query_db("SELECT descricao, valor, categoria, status FROM contas_a_pagar WHERE id=?", (id_c,))
                if not desc_res:
                    messagebox.showerror("Contas", "Conta não localizada.")
                    atualizar_contas()
                    return
                desc_c = desc_res[0]
                if str(desc_c[3]).lower() == "pago":
                    messagebox.showwarning("Contas", "Esta conta já está marcada como paga.")
                    return
                query_db("UPDATE contas_a_pagar SET status='Pago' WHERE id=?", (id_c,), commit=True)
                query_db("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)", ("Saida", f"[{desc_c[2]}] {desc_c[0]}", desc_c[1], datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cx_id), commit=True)
                registrar_log(self.current_user['nome'], "Conta paga", f"{desc_c[0]} - {format_moeda(desc_c[1])}")
                atualizar_contas()
                atualizar_fluxo()
                
        def excluir_conta():
            sel = tree_contas.selection()
            if sel:
                query_db("UPDATE contas_a_pagar SET status='Excluido', cancelado_em=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), tree_contas.item(sel[0], "values")[0]), commit=True)
                atualizar_contas()

        ctk.CTkButton(cad_cp, text="SALVAR CONTA", command=salvar_conta, fg_color=self.cor_botao, height=38, font=self.font_button).pack(side="left", padx=5)
        ctk.CTkButton(cad_cp, text="MARCAR COMO PAGO", command=marcar_pago, fg_color="#5f7f4c", height=38, font=self.font_button).pack(side="right", padx=5)
        ctk.CTkButton(cad_cp, text="EXCLUIR", command=excluir_conta, fg_color="#7f4c4c", height=38, font=self.font_button).pack(side="right", padx=5)
        
        tree_contas = ttk.Treeview(f_cp, columns=("id", "d", "v", "dv", "c", "s"), show="headings")
        for c, h in zip(("id", "d", "v", "dv", "c", "s"), ("ID", "Descrição da Despesa", "Valor", "Vencimento", "Centro Custos", "Situação")):
            tree_contas.heading(c, text=h)
        tree_contas.column("id", width=50, anchor="center")
        tree_contas.column("d", width=200)
        tree_contas.column("v", width=100, anchor="center")
        tree_contas.column("dv", width=120, anchor="center")
        tree_contas.column("c", width=110, anchor="center")
        tree_contas.column("s", width=100, anchor="center")
        tree_contas.pack(fill="both", expand=True, padx=5, pady=5)
        
        def atualizar_contas():
            for i in tree_contas.get_children():
                tree_contas.delete(i)
            for r in query_db("SELECT id, descricao, valor, data_vencimento, categoria, status FROM contas_a_pagar WHERE COALESCE(status,'Pendente') != 'Excluido' ORDER BY status DESC, id DESC"):
                tree_contas.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), r[3], r[4], r[5]))
        atualizar_contas()

        # --- SUB-TAB: DRE SIMPLIFICADO & PROJEÇÕES ---
        f_dre = ctk.CTkFrame(tab_dre, fg_color="transparent")
        f_dre.pack(fill="both", expand=True, padx=10, pady=10)
        filtros_dre = ctk.CTkFrame(f_dre, fg_color=self.cor_vinho, corner_radius=12)
        filtros_dre.pack(fill="x", pady=5)
        
        ctk.CTkLabel(filtros_dre, text="Período DRE:", font=self.font_label).pack(side="left", padx=10, pady=10)
        self.dre_mes = ctk.CTkComboBox(filtros_dre, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], width=80, font=self.font_input)
        self.dre_mes.pack(side="left", padx=5)
        self.dre_mes.set(datetime.now().strftime("%m"))
        self.dre_ano = ctk.CTkComboBox(filtros_dre, values=anos_disponiveis, width=90, font=self.font_input)
        self.dre_ano.pack(side="left", padx=5)
        self.dre_ano.set(datetime.now().strftime("%Y"))
        
        f_conteudo_dre = ctk.CTkFrame(f_dre, fg_color="transparent")
        f_conteudo_dre.pack(fill="both", expand=True, pady=10)
        esq_dre_card = ctk.CTkFrame(f_conteudo_dre, fg_color="#18121f", corner_radius=15)
        esq_dre_card.pack(side="left", fill="both", expand=True, padx=5)
        dir_dre_card = ctk.CTkFrame(f_conteudo_dre, fg_color="#18121f", corner_radius=15, width=280)
        dir_dre_card.pack(side="right", fill="both", padx=5)
        dir_dre_card.pack_propagate(False)
        
        self.lbl_dre_viewer = ctk.CTkLabel(esq_dre_card, text="Carregando DRE...", font=("Courier New", 13, "bold"), justify="left", anchor="w")
        self.lbl_dre_viewer.pack(fill="both", expand=True, padx=15, pady=15)
        self.lbl_proj_viewer = ctk.CTkLabel(dir_dre_card, text="Carregando projeção...", font=("Arial", 13), justify="left", wraplength=250)
        self.lbl_proj_viewer.pack(fill="both", expand=True, padx=15, pady=15)
        
        def calcular_dre_projecoes():
            mes = self.dre_mes.get()
            ano = self.dre_ano.get()
            fmt = f"/{mes}/{ano}"
            vendas_mes = query_db("SELECT id, total_final FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?", (f"%{fmt}%",))
            receitas = sum(v[1] for v in vendas_mes)
            
            custos = 0.0
            vendas_ids = [v[0] for v in vendas_mes]
            if vendas_ids:
                placeholder = ",".join("?" for _ in vendas_ids)
                custos = query_db(f"SELECT SUM(quantidade * custo_unitario) FROM vendas_itens WHERE venda_id IN ({placeholder})", tuple(vendas_ids))[0][0] or 0.0
            lucro_bruto = receitas - custos
            
            contas_mes = query_db("SELECT valor, categoria FROM contas_a_pagar WHERE status='Pago' AND data_vencimento LIKE ?", (f"%/{mes}/{ano}%",))
            despesas = {"Aluguel": 0.0, "Internet": 0.0, "Energia": 0.0, "Compras": 0.0, "Marketing": 0.0, "Outros": 0.0}
            for valor, cat in contas_mes:
                if cat in despesas:
                    despesas[cat] += valor
                else:
                    despesas["Outros"] += valor
            tot_despesas = sum(despesas.values())
            lucro_liquido = lucro_bruto - tot_despesas
            
            dre_texto = (
                f"--------------------------------------------------\n"
                f"      DEMONSTRATIVO DE RESULTADOS (DRE) - {mes}/{ano}\n"
                f"--------------------------------------------------\n"
                f"(+) Receitas Brutas:               {format_moeda(receitas)}\n"
                f"(-) Custo de Mercadorias (CPV):   -{format_moeda(custos)}\n"
                f"--------------------------------------------------\n"
                f"(=) LUCRO BRUTO:                   {format_moeda(lucro_bruto)}\n\n"
                f"(-) Despesas por Centro de Custo:\n"
                f"  - Aluguel:                      -{format_moeda(despesas['Aluguel'])}\n"
                f"  - Internet:                     -{format_moeda(despesas['Internet'])}\n"
                f"  - Energia:                      -{format_moeda(despesas['Energia'])}\n"
                f"  - Compras (Insumos):            -{format_moeda(despesas['Compras'])}\n"
                f"  - Marketing / Promoções:        -{format_moeda(despesas['Marketing'])}\n"
                f"  - Outras Despesas:              -{format_moeda(despesas['Outros'])}\n"
                f"--------------------------------------------------\n"
                f"(=) LUCRO LÍQUIDO DO PERÍODO:      {format_moeda(lucro_liquido)}\n"
                f"--------------------------------------------------"
            )
            self.lbl_dre_viewer.configure(text=dre_texto)
            
            dia_atual = datetime.now().day
            dias_no_mes = calendar.monthrange(int(ano), int(mes))[1]
            if str(mes) != datetime.now().strftime("%m") or str(ano) != datetime.now().strftime("%Y"):
                dia_atual = dias_no_mes
            faturamento_previsto = (receitas / dia_atual) * dias_no_mes if dia_atual > 0 else receitas
            
            proj_texto = (
                f"PROJEÇÃO FINANCEIRA MENSAL\n\n"
                f"Ritmo atual de faturamento previsto:\n"
                f"👉 {format_moeda(faturamento_previsto)}\n\n"
                f"Média diária: {format_moeda(receitas / dia_atual if dia_atual > 0 else 0)}\n"
                f"Dias avaliados: {dia_atual}/{dias_no_mes}"
            )
            self.lbl_proj_viewer.configure(text=proj_texto)

        ctk.CTkButton(filtros_dre, text="GERAR DRE", height=38, font=self.font_button, fg_color=self.cor_botao, command=calcular_dre_projecoes).pack(side="left", padx=10)
        calcular_dre_projecoes()


if __name__ == "__main__":
    if not garantir_instancia_unica():
        try:
            root = ctk.CTk()
            root.withdraw()
            messagebox.showwarning("Mística Presentes", "O sistema ja está aberto.")
            root.destroy()
        except Exception:
            pass
        sys.exit(0)
    init_db()
    realizar_backup()
    app = MisticaApp()
    app.mainloop()
