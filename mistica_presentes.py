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
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
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
from services.estoque_service import (
    consultar_estoque_produto,
    registrar_inventario_service,
    registrar_movimentacao_estoque_service,
    validar_estoque_carrinho,
)
from services.produto_service import (
    adicionar_categoria_produto,
    cadastrar_produto_service,
    consultar_produto_edicao,
    contar_produtos_categoria,
    editar_produto_service,
    inativar_categoria_produto,
    inativar_produto_service,
    listar_categorias_produto,
    listar_estoque_produtos,
    pesquisar_produtos_venda,
)
from services.venda_service import (
    calcular_total_venda,
    cancelar_venda_service,
    consultar_venda_salva,
    obter_resumo_venda,
    registrar_venda_service,
)
from services.isis_service import processar_comando_inteligente as isis_processar_comando_inteligente
from services.caixa_service import (
    abrir_caixa as caixa_abrir,
    excluir_conta as caixa_excluir_conta,
    fechar_caixa_conferido as caixa_fechar_conferido,
    fechar_caixa_simples as caixa_fechar_simples,
    lancar_fluxo as caixa_lancar_fluxo,
    listar_contas as caixa_listar_contas,
    listar_fluxo as caixa_listar_fluxo,
    marcar_conta_paga as caixa_marcar_conta_paga,
    obter_caixa_id_ativo as caixa_obter_id_ativo,
    obter_conta as caixa_obter_conta,
    resumo_fechamento_caixa as caixa_resumo_fechamento,
    salvar_conta as caixa_salvar_conta,
    status_caixa_aberto as caixa_status_aberto,
)
from services.dashboard_service import obter_kpis_dashboard
from services.relatorio_service import (
    calcular_dre_periodo,
    relatorio_lucro_liquido,
    relatorio_produtos_mais_vendidos,
    relatorio_ranking_clientes,
    relatorio_valoracao_estoque,
    relatorio_vendas_periodo,
)
from services.isis_service import (
    alertas_operacionais as isis_alertas_service,
    aniversariantes_hoje as isis_aniversariantes_hoje,
    calcular_giro_estoque_30_dias as isis_calcular_giro_estoque_30_dias,
    clientes_incompletos_texto as isis_clientes_incompletos_texto,
    consulta_sql as isis_consulta_sql,
    detectar_intencao as isis_detectar_intencao,
    diagnostico_banco_operacional as isis_diagnostico_banco_operacional,
    dica_sazonal as isis_dica_sazonal,
    normalizar_texto as isis_normalizar_texto,
    periodo_mes as isis_periodo_mes_service,
    prioridades_do_dia as isis_prioridades_do_dia_texto,
    produtos_sem_giro_texto as isis_produtos_sem_giro_texto,
    reparar_banco_e_indices as isis_reparar_banco_service,
    resumo_financeiro_isis as isis_resumo_financeiro_service,
    resumo_inteligente_loja as isis_resumo_inteligente_loja_service,
)
from isis.commands import cupom_venda as isis_cupom_venda, localizar_venda as isis_localizar_venda, vendas_recentes as isis_vendas_recentes
from isis.memory import (
    carregar_aprendizado as isis_carregar_aprendizado,
    importar_json_para_sqlite as isis_importar_json_para_sqlite,
    registrar_conversa as isis_registrar_conversa,
    registrar_pesquisa as isis_registrar_pesquisa,
    salvar_aprendizado as isis_salvar_aprendizado,
)

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
    """Converte valores monetarios em float.

    Aceita: 18, 18,00, R$ 18,00, 1.250,50 e 1250.50.
    """
    if texto is None:
        return 0.0
    txt = str(texto).strip()
    if not txt:
        return 0.0
    txt = txt.replace("R$", "").replace("r$", "").replace(" ", "")
    try:
        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        limpo = re.sub(r"[^0-9]", "", str(texto))
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
        registrar_movimentacao_estoque_service(
            codigo_p,
            produto,
            quantidade,
            tipo,
            motivo,
            usuario,
            estoque_anterior,
            estoque_posterior,
            venda_id,
        )
    except Exception as exc:
        registrar_erro_sistema("registrar_movimentacao_estoque", exc)

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
    except Exception as exc:
        print(f"[Erro] Falha ao registrar log do sistema: {exc}")


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

    def adicionar_barra_rolagem_tree(self, tree):
        try:
            parent = tree.master
            yscroll = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=yscroll.set)
            yscroll.pack(side='right', fill='y')
        except Exception:
            pass

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
        res = query_db("SELECT nome, perfil, login, senha_hash, COALESCE(senha_salt,'') FROM usuarios WHERE login=? AND COALESCE(ativo,1)=1", (u,))
        autenticado = False
        if res:
            nome, perfil, login, senha_hash, senha_salt = res[0]
            if senha_salt:
                autenticado = senha_hash == hash_password_pbkdf2(senha_plana, str(senha_salt).encode("utf-8"))
            else:
                autenticado = senha_hash == hash_password_pbkdf2(senha_plana)
                if autenticado:
                    novo_salt = secrets.token_hex(16)
                    novo_hash = hash_password_pbkdf2(senha_plana, novo_salt.encode("utf-8"))
                    query_db("UPDATE usuarios SET senha_hash=?, senha_salt=? WHERE login=?", (novo_hash, novo_salt, login), commit=True)
        if res and autenticado:
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
            salt = secrets.token_hex(16)
            query_db("UPDATE usuarios SET senha_hash=?, senha_salt=? WHERE login=?", (hash_password_pbkdf2(senha_txt, salt.encode("utf-8")), salt, login_usuario), commit=True)
            messagebox.showinfo("Sucesso", "Senha atualizada! Prossiga com o login.")
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

        dados_dash = obter_kpis_dashboard()
        kpis = [
            ("VENDAS HOJE", format_moeda(dados_dash["tot_hoje"]), "#5f7f4c"),
            ("VENDAS MES", format_moeda(dados_dash["tot_mes"]), "#b98a3c"),
            ("PRODUTOS", str(dados_dash["qtd_prod"]), "#3c7bb9"),
            ("CLIENTES", str(dados_dash["qtd_cli"]), "#7c3cb9"),
            ("PECAS ESTOQUE", str(dados_dash["tot_estoque"]), "#3cb9b1")
        ]
        for idx, (titulo, val, cor) in enumerate(kpis):
            card = ctk.CTkFrame(f, fg_color=self.cor_vinho, corner_radius=15, border_width=2, border_color=cor)
            card.grid(row=0, column=idx, padx=8, pady=10, sticky="ew")
            ctk.CTkLabel(card, text=titulo, font=("Arial", 11, "bold"), text_color=cor).pack(pady=(12, 2))
            ctk.CTkLabel(card, text=val, font=("Arial", 22, "bold"), text_color="#ffffff").pack(pady=(2, 12))

        f_info = ctk.CTkFrame(f, fg_color="#18121f", corner_radius=15)
        f_info.grid(row=1, column=0, columnspan=5, pady=20, sticky="nsew")
        ctk.CTkLabel(f_info, text="Mistica Presentes", font=("Georgia", 28, "bold"), text_color=self.cor_ouro).pack(pady=(15, 5))
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
        ctk.CTkButton(f_info, text="RECARREGAR INFORMACOES DO PAINEL", height=40, font=self.font_button, fg_color=self.cor_botao, command=self.montar_dashboard).pack(pady=15)

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
        self.adicionar_barra_rolagem_tree(self.tree_v_stock)
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
        self.adicionar_barra_rolagem_tree(self.tree_v_car)
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
        res = pesquisar_produtos_venda(t)
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
                messagebox.showerror("Quantidade", "Insira um numero maior que zero.")
                return
            info = consultar_estoque_produto(p[0])
            estoque_atual = info["quantidade"] if info else 0
            total_no_carrinho = qtd + sum(int(it["q"]) for it in self.carrinho if it["id"] == p[0])
            if total_no_carrinho <= estoque_atual:
                preco = conv_float(p[2])
                self.carrinho.append({"id": p[0], "n": p[1], "q": qtd, "p": preco, "t": preco * qtd})
                est_min = info["estoque_minimo"] if info else 0
                restante = estoque_atual - total_no_carrinho
                if restante <= est_min:
                    messagebox.showwarning("Estoque baixo", f"Atencao: '{p[1]}' ficara com {restante} unidade(s), abaixo ou no minimo ({est_min}).")
                self.render_v_car()
                self.v_busca.delete(0, 'end')
                self.v_busca.focus()
            else:
                messagebox.showerror("Estoque", "Quantidade indisponivel ou produto nao localizado.")

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
                info = consultar_estoque_produto(item_car["id"])
                estoque_atual = info["quantidade"] if info else 0
                outros = sum(int(it["q"]) for pos, it in enumerate(self.carrinho) if pos != idx and it["id"] == item_car["id"])
                total_no_carrinho = outros + nova_qtd
                if total_no_carrinho <= estoque_atual:
                    item_car['q'] = nova_qtd
                    item_car['t'] = item_car['p'] * nova_qtd
                    est_min = info["estoque_minimo"] if info else 0
                    restante = estoque_atual - total_no_carrinho
                    if restante <= est_min:
                        messagebox.showwarning("Estoque baixo", f"Atencao: '{item_car['n']}' ficara com {restante} unidade(s), abaixo ou no minimo ({est_min}).")
                    self.render_v_car()
                else:
                    messagebox.showerror("Estoque", "Quantidade indisponivel ou produto nao localizado.")

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
        self.v_calc = calcular_total_venda(self.carrinho, self.v_desc_ent.get(), self.v_pag_cb.get())
        for it in self.carrinho:
            self.tree_v_car.insert("", "end", values=(it['n'], it['q'], format_moeda(it['t'])))
        self.v_total_lbl.configure(text=format_moeda(self.v_calc['tot']))

    def validar_venda_para_conferencia(self):
        cx_id = caixa_obter_id_ativo()
        if not cx_id:
            messagebox.showwarning("Caixa", "Abra o caixa diario antes de efetuar vendas.")
            return None
        if not self.carrinho:
            messagebox.showwarning("Venda", "Carrinho vazio.")
            return None
        try:
            avisos = validar_estoque_carrinho(self.carrinho)
        except Exception as e:
            messagebox.showerror("Estoque", str(e))
            return None
        return {"caixa_id": cx_id, "avisos": avisos}

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
        try:
            vid = registrar_venda_service(
                self.carrinho,
                cli,
                data,
                data_iso,
                self.v_calc,
                self.v_pag_cb.get(),
                self.current_user['nome'],
                cx_id,
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar venda: {e}")
            return
        cupom_final = self.montar_texto_cupom(vid, cli, data)
        realizar_backup()
        registrar_log(self.current_user['nome'], "Venda", f"N {vid} - {format_moeda(self.v_calc['tot'])}")
        if imprimir:
            self.imprimir_cupom_texto(cupom_final, vid)
        if whatsapp:
            self.enviar_cupom_whatsapp(cupom_final, cli)
        win.destroy()
        messagebox.showinfo("Venda salva", f"Venda no {vid} salva com sucesso.")
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
            messagebox.showwarning("Inventario", "Selecione um produto no estoque.")
            return
        p = self.tree_est.item(sel[0], "values")
        codigo, nome = p[0], p[1]
        qtd_sistema = int(str(p[5]).replace(".", "") or 0)
        win = ctk.CTkToplevel(self)
        win.title("Inventario de Estoque")
        win.geometry("460x360")
        win.grab_set()
        card = ctk.CTkFrame(win, fg_color=self.cor_vinho, corner_radius=14)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="CONFERENCIA DE INVENTARIO", font=self.font_label, text_color=self.cor_ouro).pack(pady=(16, 8))
        ctk.CTkLabel(card, text=f"{codigo} - {nome}", font=self.font_input, wraplength=390).pack(pady=4)
        ctk.CTkLabel(card, text=f"Quantidade no sistema: {qtd_sistema}", font=self.font_button).pack(pady=4)
        ent_contada = ctk.CTkEntry(card, placeholder_text="Quantidade contada fisicamente", height=40, font=self.font_input)
        ent_contada.pack(fill="x", padx=22, pady=8)
        ent_obs = ctk.CTkEntry(card, placeholder_text="Observacao do inventario", height=40, font=self.font_input)
        ent_obs.pack(fill="x", padx=22, pady=8)

        def salvar_inventario():
            txt = ent_contada.get().strip()
            if not txt.isdigit():
                messagebox.showwarning("Inventario", "Informe uma quantidade valida.")
                return
            qtd_contada = int(txt)
            diferenca = qtd_contada - qtd_sistema
            obs = ent_obs.get().strip()
            if not messagebox.askyesno("Confirmar inventario", f"Sistema: {qtd_sistema}\nContado: {qtd_contada}\nDiferenca: {diferenca}\n\nConfirmar ajuste do estoque?"):
                return
            try:
                registrar_inventario_service(codigo, nome, qtd_sistema, qtd_contada, self.current_user['nome'], obs)
                registrar_log(self.current_user['nome'], "Inventario", f"{codigo} - {nome}: {qtd_sistema} -> {qtd_contada}")
                self.refresh_estoque_list()
                if hasattr(self, "tree_v_stock"):
                    self.filtrar_vendas()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Inventario", f"Erro ao salvar inventario: {e}")

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
            messagebox.showwarning("Produto", "Preco, quantidade e estoque minimo nao podem ser negativos.")
            return

        try:
            id_p = cadastrar_produto_service(n, custo, lucro, p, q, est_min, cat, self.current_user['nome'])
            registrar_log(self.current_user['nome'], "Produto", f"Cadastro {id_p} - {n} - estoque inicial {q}")
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
            messagebox.showinfo("Produto", f"Produto salvo com codigo {id_p}.")
        except Exception as e:
            messagebox.showerror("Produto", f"Erro ao salvar produto: {e}")

    def abrir_edicao_produto(self):
        sel = self.tree_est.selection()
        if not sel:
            return
        cod_p = self.tree_est.item(sel[0], "values")[0]
        d = consultar_produto_edicao(cod_p)
        if not d:
            messagebox.showerror("Produto", "Produto nao localizado no banco de dados.")
            self.refresh_estoque_list()
            return

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
        up = ctk.CTkEntry(win_edit, placeholder_text="Preco Final", height=38, font=self.font_input)
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
            estoque_novo = int(uq.get()) if uq.get().isdigit() else 0
            estoque_minimo = int(umin.get()) if umin.get().isdigit() else 0
            try:
                resumo = editar_produto_service(
                    cod_p,
                    nome_val,
                    custo_val,
                    lucro_val,
                    preco_val,
                    estoque_novo,
                    estoque_minimo,
                    self.current_user['nome'],
                )
                registrar_log(
                    self.current_user['nome'],
                    "Produto",
                    f"Alterou {cod_p} - {nome_val} | preco {format_moeda(resumo['preco_antigo'])} -> {format_moeda(preco_val)} | estoque {resumo['estoque_antigo']} -> {estoque_novo}",
                )
                self.refresh_estoque_list()
                if hasattr(self, "tree_v_stock"):
                    self.filtrar_vendas()
                win_edit.destroy()
            except Exception as e:
                messagebox.showerror("Produto", f"Erro ao alterar produto: {e}")

        ctk.CTkButton(win_edit, text="SALVAR", height=40, font=self.font_button, fg_color="#5f7f4c", command=salvar_alteracao).pack(pady=15)

    def excluir_prod(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Admin apenas.")
            return
        sel = self.tree_est.selection()
        if sel:
            p = self.tree_est.item(sel[0], "values")
            if messagebox.askyesno("Inativar produto", f"Deseja inativar '{p[1]}'?\n\nEle sai das buscas e vendas, mas continua no historico."):
                try:
                    inativar_produto_service(p[0])
                    registrar_log(self.current_user['nome'], "Produto", f"Inativou produto {p[0]} - {p[1]}")
                    self.refresh_estoque_list()
                    if hasattr(self, "tree_v_stock"):
                        self.filtrar_vendas()
                except Exception as e:
                    messagebox.showerror("Produto", f"Erro ao inativar produto: {e}")

    def refresh_estoque_list(self):
        for i in self.tree_est.get_children():
            self.tree_est.delete(i)
        termo = self.est_busca.get().strip() if hasattr(self, 'est_busca') else ""
        res = listar_estoque_produtos(termo)
        for r in res:
            qtd = r[5] if r[5] is not None else 0
            est_min = r[6] if r[6] is not None else 0
            tag = "critico" if qtd < est_min else ("alerta" if qtd <= est_min + 2 else "")
            self.tree_est.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), f"{r[3]}%", format_moeda(r[4]), qtd, est_min, r[7]), tags=(tag,))

    def refresh_cat_list(self):
        l = listar_categorias_produto()
        self.ec.configure(values=l)
        if l:
            self.ec.set(l[0])

    def add_cat(self):
        c = self.cat_e.get().strip()
        if not c:
            messagebox.showwarning("Categoria", "Informe o nome da categoria.")
            return
        try:
            adicionar_categoria_produto(c)
            self.refresh_cat_list()
            self.cat_e.delete(0,'end')
        except Exception as e:
            messagebox.showwarning("Categoria", str(e))

    def del_cat(self):
        if self.current_user['perfil'] != 'adm':
            messagebox.showerror("Negado", "Admin apenas.")
            return
        cat = self.ec.get()
        if not cat:
            return
        uso = contar_produtos_categoria(cat)
        if uso:
            messagebox.showwarning("Categoria", f"Nao e possivel excluir: existem {uso} produto(s) nesta categoria.")
            return
        if messagebox.askyesno("Confirmar", f"Excluir categoria '{cat}'?"):
            try:
                inativar_categoria_produto(cat)
                self.refresh_cat_list()
            except Exception as e:
                messagebox.showerror("Categoria", f"Erro ao excluir categoria: {e}")

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
        dados = relatorio_lucro_liquido(mes, ano)
        texto = (
            f"Lucro liquido real aproximado de {mes}/{ano}\n\n"
            f"Faturamento recebido: {format_moeda(dados['receitas'])}\n"
            f"Custo dos produtos vendidos: -{format_moeda(dados['custos'])}\n"
            f"Despesas pagas cadastradas: -{format_moeda(dados['despesas'])}\n"
            f"Taxas registradas nas vendas: {format_moeda(dados['taxas'])}\n"
            f"Descontos concedidos: {format_moeda(dados['descontos'])}\n\n"
            f"Lucro liquido estimado: {format_moeda(dados['lucro'])}"
        )
        self.lbl_r_f.configure(text=f"Lucro liquido {mes}/{ano}: {format_moeda(dados['lucro'])}")
        messagebox.showinfo("Lucro liquido", texto)

    def cancelar_venda_selecionada(self):
        sel = self.tree_rel.selection()
        if not sel:
            messagebox.showwarning("Cancelamento", "Selecione uma venda.")
            return
        vid = self.tree_rel.item(sel[0], "values")[0]
        if not str(vid).isdigit():
            messagebox.showerror("Erro", "Venda invalida.")
            return

        venda_status = obter_resumo_venda(vid)
        if not venda_status:
            return
        if venda_status[0] == "Cancelado":
            messagebox.showwarning("Cancelamento", "Ja cancelada.")
            return

        valor_estorno = venda_status[1] or 0.0
        if messagebox.askyesno("Confirmar", f"Cancelar venda no {vid}?\nEstorno de {format_moeda(valor_estorno)} e devolucao fisica dos itens ao estoque."):
            try:
                cx_id = caixa_obter_id_ativo()
                cancelar_venda_service(vid, self.current_user['nome'], cx_id)
                registrar_log(self.current_user['nome'], "Cancelamento", f"Venda no {vid} cancelada com estorno de {format_moeda(valor_estorno)}")
                self.ver_rel("hoje")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro: {e}")

    def ver_rel(self, p):
        self.ajustar_colunas_treeview("vendas")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        filtro = datetime.now().strftime("%d/%m/%Y") if p=="hoje" else (datetime.now().strftime("/%m/%Y") if p=="mes" else datetime.now().strftime("/%Y"))
        dados = relatorio_vendas_periodo(filtro)
        self.lbl_r_f.configure(text=f"Total: {format_moeda(dados['total'])}  |  Custos: {format_moeda(dados['custo'])}  |  Lucro Real: {format_moeda(dados['lucro'])}")
        for r in dados["vendas"]:
            self.tree_rel.insert("", "end", values=(r[0], r[1], r[2], format_moeda(r[3]), r[4]))

    def ver_rel_filtrado(self):
        self.ajustar_colunas_treeview("vendas")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        mes = self.r_mes.get()
        ano = self.r_ano.get()
        dados = relatorio_vendas_periodo(f"/{mes}/{ano}")
        self.lbl_r_f.configure(text=f"Total: {format_moeda(dados['total'])}  |  Custos: {format_moeda(dados['custo'])}  |  Lucro Real: {format_moeda(dados['lucro'])}")
        for r in dados["vendas"]:
            self.tree_rel.insert("", "end", values=(r[0], r[1], r[2], format_moeda(r[3]), r[4]))

    def ver_rel_estoque(self):
        self.ajustar_colunas_treeview("estoque")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        dados = relatorio_valoracao_estoque()
        for nome, qtd, custo_total, venda_total in dados["itens"]:
            self.tree_rel.insert("", "end", values=("ESTOQUE", nome, qtd, format_moeda(custo_total), format_moeda(venda_total)))
        self.lbl_r_f.configure(text=f"Custo total: {format_moeda(dados['custo_total'])}  |  Retorno de Vendas: {format_moeda(dados['venda_total'])}  |  Lucro Estimado: {format_moeda(dados['lucro_estimado'])}")

    def ver_produtos_mais_vendidos(self):
        self.ajustar_colunas_treeview("produtos_mais")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        for r in relatorio_produtos_mais_vendidos(15):
            self.tree_rel.insert("", "end", values=(r[0], r[1], f"{r[2]} unidades", format_moeda(r[3]), "Historico"))

    def ver_ranking_clientes(self):
        self.ajustar_colunas_treeview("ranking")
        for i in self.tree_rel.get_children():
            self.tree_rel.delete(i)
        res = relatorio_ranking_clientes(10)
        self.lbl_r_f.configure(text="TOP 10 CLIENTES")
        for idx, r in enumerate(res):
            self.tree_rel.insert("", "end", values=(f"{idx+1}o", r[0], f"{r[1]} Compras", format_moeda(r[2]), "Fidelidade"))

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
        self.adicionar_barra_rolagem_tree(self.tree_logs)
        self.refresh_audit()

    # --- JANELA DE GERENCIAMENTO DE USUÁRIOS ---
    def json_gerenciar_usuarios_helper(self, win, tree, un, uc, ue, ut, ul, up, upf):
        nome_val = un.get().strip()
        login_val = ul.get().strip().lower()
        if not nome_val or not login_val:
            messagebox.showerror("Erro", "Preencha Nome e Login.")
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
            salt = secrets.token_hex(16)
            senha_hash = hash_password_pbkdf2(nova_senha, salt.encode("utf-8"))
            query_db("UPDATE usuarios SET nome=?, cpf=?, endereco=?, telefone=?, login=?, senha_hash=?, senha_salt=?, perfil=? WHERE id=?", (nome_val, uc.get(), ue.get(), ut.get(), login_val, senha_hash, salt, upf.get(), self.selected_user_id), commit=True)
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
            salt = secrets.token_hex(16)
            senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
            query_db("INSERT INTO usuarios (nome, cpf, endereco, telefone, login, senha_hash, senha_salt, perfil) VALUES (?,?,?,?,?,?,?,?)", (nome, self.uc_u.get(), self.ue_u.get(), self.ut_u.get(), login, senha_hash, salt, self.upf_u.get()), commit=True)
            self.refresh_audit()
            self.un_u.delete(0, 'end')
            self.uc_u.delete(0, 'end')
            self.ue_u.delete(0, 'end')
            self.ut_u.delete(0, 'end')
            self.ul_u.delete(0, 'end')
            self.up_u.delete(0, 'end')
        except Exception as e:
            registrar_erro_sistema("Criar usuario", e)
            messagebox.showerror("Erro", "Login em uso ou dados inválidos.")

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
        ctk.CTkButton(f_controles, text="FALAR COM ISIS", width=150, height=42, font=self.font_button, fg_color="#3c7bb9", command=self.falar_com_isis).pack(side="right", padx=(0, 8))
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
            win.after(4000, win.destroy)
        except Exception:
            pass


    def falar_com_isis(self):
        try:
            from isis.voice import reconhecer_fala_ptbr
            texto = reconhecer_fala_ptbr()
            if not texto:
                messagebox.showinfo("Isis", "Nao consegui ouvir nada agora. Voce pode digitar o pedido normalmente.")
                return
            if hasattr(self, "ent_pergunta"):
                self.ent_pergunta.delete(0, 'end')
                self.ent_pergunta.insert(0, texto)
                self.enviar_pergunta_ia()
        except Exception as e:
            messagebox.showinfo("Voz da Isis", f"Voz ainda nao configurada neste computador.\n\nDetalhe: {e}")
    
    def inserir_texto_com_links_isis(self, texto):
        import re
        import webbrowser
        texto = str(texto or "")
        urls = re.findall(r"https?://[^\s]+", texto)
        pos = 0
        for idx, url in enumerate(urls):
            inicio = texto.find(url, pos)
            if inicio < 0:
                continue
            if inicio > pos:
                self.txt_chat.insert("end", texto[pos:inicio])
            tag = f"link_isis_{idx}_{inicio}"
            self.txt_chat.insert("end", url, tag)
            self.txt_chat.tag_config(tag, foreground="#4da3ff", underline=True)
            self.txt_chat.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
            pos = inicio + len(url)
        self.txt_chat.insert("end", texto[pos:])

    def enviar_pergunta_ia(self):
        pergunta = self.ent_pergunta.get().strip()
        if not pergunta:
            return
        self.txt_chat.configure(state="normal")
        self.txt_chat.insert("end", f"Você: {pergunta}\n\n")
        resposta = self.processar_pergunta_ia(pergunta)
        try:
            self.registrar_aprendizado_issis(pergunta, resposta)
        except Exception as e:
            registrar_erro_sistema("Registrar aprendizado Isis", e)
        self.txt_chat.insert("end", "Isis a Bruxinha:\n")
        self.inserir_texto_com_links_isis(resposta)
        self.txt_chat.insert("end", "\n\n" + "-" * 56 + "\n\n")
        self.txt_chat.configure(state="disabled")
        self.txt_chat.see("end")
        self.ent_pergunta.delete(0, 'end')

    def importar_json_isis_para_sqlite(self):
        try:
            usuario_padrao = self.current_user.get("nome", "") if self.current_user else "Sistema"
            isis_importar_json_para_sqlite(ISSIS_LEARNING_PATH, usuario_padrao)
        except Exception as e:
            registrar_erro_sistema("Importar memoria Isis JSON", e)

    def carregar_aprendizado_issis(self):
        try:
            self.importar_json_isis_para_sqlite()
            return isis_carregar_aprendizado()
        except Exception as e:
            registrar_erro_sistema("Carregar memoria Isis SQLite", e)
            return {"conversas": [], "conhecimentos": {}, "pesquisas": []}

    def salvar_aprendizado_issis(self, dados):
        try:
            usuario_padrao = self.current_user.get("nome", "") if self.current_user else "Sistema"
            isis_salvar_aprendizado(dados, usuario_padrao)
        except Exception as e:
            registrar_erro_sistema("Salvar memoria Isis SQLite", e)

    def registrar_aprendizado_issis(self, pergunta, resposta):
        try:
            usuario = self.current_user.get("nome", "") if self.current_user else "Sistema"
            isis_registrar_conversa(pergunta, resposta, usuario)
        except Exception as e:
            registrar_erro_sistema("Registrar aprendizado Isis", e)

    def inserir_comando_issis(self, texto):
        if hasattr(self, "ent_pergunta"):
            self.ent_pergunta.delete(0, 'end')
            self.ent_pergunta.insert(0, texto)
            self.enviar_pergunta_ia()

    def normalizar_texto_issis(self, texto):
        return isis_normalizar_texto(texto)

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
        bloqueios = ["senha", "invadir", "hackear", "pirataria", "conteudo adulto", "porno", "porn"]
        if any(b in self.normalizar_texto_issis(consulta) for b in bloqueios):
            return "Nao posso ajudar com esse tipo de pesquisa. Posso pesquisar fornecedores, ideias de marketing, tendencias e informacoes uteis para a loja."
        consulta_lojista = consulta
        if not any(x in self.normalizar_texto_issis(consulta) for x in ["atacado", "fornecedor", "loja", "comprar", "preco", "instagram", "marketing"]):
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
                return "Tentei pesquisar online, mas nao consegui extrair resultados claros agora. Tente uma busca mais especifica."
            usuario = self.current_user.get("nome", "") if self.current_user else "Sistema"
            isis_registrar_pesquisa(consulta, salvos, usuario)
            linhas.append("\nObservacao: confirme preco, CNPJ, reputacao e prazo diretamente com o fornecedor antes de comprar.")
            return "\n".join(linhas)
        except Exception as e:
            return f"Nao consegui acessar a internet agora. Verifique a conexao do computador. Detalhe tecnico: {e}"

    def dres_sazonais_mensagens_issis(self, mes):
        return isis_dica_sazonal(mes)

    def detectar_intencao(self, pergunta):
        return isis_detectar_intencao(pergunta)

    def calcular_giro_estoque_30_dias(self):
        return isis_calcular_giro_estoque_30_dias()

    def issis_query(self, sql, params=()):
        return isis_consulta_sql(sql, params)

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
            return "Por favor, me informe o numero do ID da venda que deseja localizar (ex: 'localizar venda 5')."
        vid = numeros[0]
        v = isis_localizar_venda(vid)
        if not v:
            return f"Nao encontrei nenhuma venda registrada com o numero {vid} no banco de dados."
        return (
            f"Venda localizada!\n"
            f"- ID Venda: {v[0]}\n"
            f"- Data: {v[1]}\n"
            f"- Cliente: {v[2]}\n"
            f"- Total: {format_moeda(v[3])}\n"
            f"- Pagamento: {v[4]}\n"
            f"- Situacao: {v[5]}"
        )

    def issis_admin_reimprimir_cupom(self, pergunta):
        p_norm = self.normalizar_texto_issis(pergunta)
        numeros = re.findall(r'\d+', pergunta)
        if not numeros:
            recentes = isis_vendas_recentes(5)
            if not recentes:
                return "Nao encontrei vendas para reimprimir."
            linhas = ["Encontrei estas vendas recentes. Qual cupom voce quer reimprimir?"]
            for v in recentes:
                linhas.append(f"- Venda {v[0]} | {v[1]} | {v[2]} | {format_moeda(v[3])}")
            linhas.append("Para eu agir com seguranca, digite: confirmar reimprimir cupom NUMERO")
            return "\n".join(linhas)
        vid = numeros[0]
        v, itens = isis_cupom_venda(vid)
        if not v:
            return f"Nao localizei a venda {vid}."
        if not any(x in p_norm for x in ["confirmar", "imprimir agora", "pode imprimir", "segunda via agora"]):
            return (
                f"Encontrei a venda {v[0]} de {v[1]} para {v[2]}, total {format_moeda(v[6])}.\n"
                "Ainda nao reimprimi. Para confirmar a acao, digite:\n"
                f"confirmar reimprimir cupom {vid}"
            )
        c = f"        MISTICA PRESENTES (2 VIA)\n        Natalia Grunwald\n    CNPJ: 41.966.398/0001-00\n--------------------------------\nCUPOM N: {v[0]} | DATA: {v[1]}\nCLIENTE: {v[2]}\nVENDEDOR: {v[8]}\nPAGAMENTO: {v[7]}\n--------------------------------\n"
        for it in itens:
            c += f"{str(it[0])[:18]:<18} Qtd:{it[1]:<3} {format_moeda(it[2])}\n"
        c += f"--------------------------------\nSUBTOTAL: {format_moeda(v[3])}\nDESCONTO: -{format_moeda(v[4])}\nTAXA CARTAO: {format_moeda(v[5])}\nTOTAL FINAL: {format_moeda(v[6])}\n--------------------------------\n"
        caminho = os.path.join(DOCS_PATH, f"cupom_reimpresso_{vid}.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(c)
        registrar_log(self.current_user['nome'], "Isis", f"Reimpressao confirmada do cupom {vid}")
        try:
            os.startfile(caminho)
            return f"Pronto. Gerei a segunda via da venda {vid} e abri o arquivo."
        except Exception:
            return f"Pronto. Gerei a segunda via da venda {vid}, mas nao consegui abrir automaticamente. Arquivo: {caminho}"

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
        return isis_periodo_mes_service(pergunta)

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
        try:
            resposta_modular = isis_processar_comando_inteligente(pergunta, self.current_user)
            if resposta_modular and resposta_modular.get("handled"):
                return resposta_modular.get("texto", "")
        except Exception as e:
            registrar_erro_sistema("Isis modular inteligente", e)


        try:
            resposta_avancada = self.issis_processar_avancado(pergunta)
            if resposta_avancada is not None:
                return resposta_avancada
        except Exception as e:
            registrar_erro_sistema("Isis processar pergunta avancada", e)
            return f"Encontrei um erro ao processar esse comando avancado: {e}"

        if p_norm in ["ajuda", "help", "comandos", "o que voce faz"]:
            return self.texto_ajuda_issis()
        if any(p_norm.startswith(x) for x in ["aprenda", "aprender", "memorize", "lembre"]):
            return self.aprender_conhecimento_issis(pergunta)
        if any(p_norm.startswith(x) for x in ["esqueca", "esqueça", "apague", "remova", "delete"]):
            return self.esquecer_conhecimento_issis(pergunta)
        if any(x in p_norm for x in ["pesquise na internet", "pesquisar na internet", "buscar na internet", "busque na internet", "pesquise online", "buscar online", "google"]):
            return self.pesquisar_internet_issis(pergunta)
        if any(x in p_norm for x in ["o que voce sabe", "sua memoria", "consultar memoria"]):
            return self.consultar_conhecimento_issis(pergunta)

        cumprimentos = ["bom dia", "boa tarde", "boa noite", "oi", "ola", "olá", "tudo bem", "e ai", "e aí"]
        if p in cumprimentos or any(p.startswith(x + " ") for x in cumprimentos):
            return self.saudacao_natural_issis(pergunta)
        if any(x in p for x in ["quem e voce", "quem é voce", "quem é você", "se apresente", "fale de voce", "fale de você", "sua historia", "sua história", "issis grunwald bach", "isis grunwald bach"]):
            return self.perfil_issis()
        if any(x in p for x in ["seu pai", "sua mae", "sua mãe", "fredi", "natalia", "grunwald", "irmao", "irmão", "irma", "irmã", "familia", "família", "mike", "gato", "frajola", "peixe", "oscar", "tigre", "albino", "black", "calopsita", "madruguinha"]):
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
            lucro, faturamento, custo = isis_consulta_sql("SELECT 1,1,1")[0] if False else __import__('reports.vendas_report', fromlist=['lucro_bruto_itens_periodo']).lucro_bruto_itens_periodo(filtro)
            return (
                f"Calculei os lucros estimados para {mes}/{ano}:\n"
                f"- Faturamento em itens: {format_moeda(faturamento)}\n"
                f"- Custo dos produtos vendidos (CPV): {format_moeda(custo)}\n"
                f"- Margem Bruta Real: {format_moeda(lucro)}\n\n"
                f"{self.dres_sazonais_mensagens_issis(int(mes))}"
            )
        if intent == "faturamento":
            mes, ano, filtro = self.issis_periodo_mes(pergunta)
            qtd, total = __import__('reports.vendas_report', fromlist=['resumo_vendas_periodo']).resumo_vendas_periodo(filtro)
            media = total / max(1, datetime.now().day if mes == datetime.now().strftime("%m") and ano == datetime.now().strftime("%Y") else 30)
            return f"Em {mes}/{ano} registramos {format_moeda(total)} em {qtd} vendas. A nossa media diaria no periodo e de {format_moeda(media)}."
        if intent == "estoque":
            giros = self.calcular_giro_estoque_30_dias()
            if not giros:
                return "Analisei o estoque fisico e os niveis estao saudaveis em relacao as vendas recentes!"
            linhas = ["Minhas previsoes e sugestoes de compra para manter o estoque abastecido:"]
            for item in giros[:12]:
                ruptura = f"{item['dias_restantes']:.1f} dias" if item['dias_restantes'] != float('inf') else "Sem ruptura iminente"
                linhas.append(f"- {item['nome']}: estoque {item['qtd_atual']} un, vendeu {item['total_vendido']} un no mes. Ruptura em: {ruptura}. Sugiro comprar {item['compra_sugerida']} un.")
            return "\n".join(linhas)
        if intent == "financeiro":
            dados = isis_resumo_financeiro_service()
            cx = dados["caixa"]
            status_txt = f"Aberto com fundo de {format_moeda(cx[1])}" if cx else "Fechado"
            return f"Resumo Financeiro:\n- Caixa diario atual: {status_txt}\n- Contas a pagar pendentes: {dados['contas'][0]} lancamentos somando {format_moeda(dados['contas'][1])}."
        if intent == "clientes":
            res = isis_aniversariantes_hoje()
            niver_txt = f"Hoje temos {len(res)} aniversariantes: " + ", ".join([r[1] for r in res]) if res else "Nenhum aniversariante para hoje."
            return f"Informacoes de Fidelidade:\n- Aniversariantes: {niver_txt}\n- Lembre-se de enviar as mensagens de felicitacoes pela aba Marketing!"
        if intent == "produtos":
            campeao = __import__('reports.vendas_report', fromlist=['produto_campeao']).produto_campeao()
            return f"O produto campeao de vendas acumuladas e '{campeao[0]}', com {campeao[1]} unidades faturadas e {format_moeda(campeao[2])} de receita." if campeao else "Sem vendas registradas no historico recente."

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
        linhas = ["Diagnostico tecnico da Isis:"]
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
        problemas = []
        try:
            problemas.extend(isis_diagnostico_banco_operacional(tabelas_obrigatorias))
        except Exception as e:
            problemas.append(f"Falha ao verificar banco: {e}")
        try:
            caminho = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else __file__
            if os.path.exists(caminho):
                texto = open(caminho, "r", encoding="utf-8", errors="ignore").read()
                chamados = sorted(set(re.findall(r"command\s*=\s*self\.([a-zA-Z_][a-zA-Z0-9_]*)", texto)))
                faltando = [m for m in chamados if not hasattr(self, m)]
                for m in faltando[:20]:
                    problemas.append(f"Botao chama metodo inexistente: self.{m}")
        except Exception as e:
            problemas.append(f"Nao consegui auditar botoes: {e}")
        if problemas:
            linhas.append("Encontrei pontos que merecem atencao:")
            for p in problemas[:25]:
                linhas.append(f"- {p}")
            linhas.append("\nVoce pode pedir: 'Isis, reparar banco' para corrigir estrutura e indices seguros.")
        else:
            linhas.append("Nao encontrei erros criticos de estrutura no banco nem botoes quebrados pelo diagnostico atual.")
        linhas.append("\nTambem posso ler o arquivo de erros com: 'Isis, ultimos erros'.")
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
            return "Apenas administrador pode executar reparo estrutural do banco."
        try:
            alteracoes = isis_reparar_banco_service(init_db, realizar_backup)
            return "Reparo seguro concluido:\n- " + "\n- ".join(alteracoes)
        except Exception as e:
            registrar_erro_sistema("Isis reparar banco", e)
            return f"Nao consegui completar o reparo. Detalhe tecnico: {e}"

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
        if caixa_obter_id_ativo():
            return "O caixa ja esta aberto."
        valor = 0.0
        numeros = re.findall(r"\d+[\d\.,]*", pergunta)
        if numeros:
            valor = conv_float(numeros[0])
        try:
            operador = self.current_user.get('nome', 'Isis') if self.current_user else 'Isis'
            caixa_abrir(valor, operador, "Abertura de Caixa via Isis")
            return f"Caixa aberto com saldo inicial de {format_moeda(valor)}."
        except Exception as e:
            registrar_erro_sistema("Isis abrir caixa", e)
            return f"Nao consegui abrir o caixa. Detalhe: {e}"

    def issis_fechar_caixa_comando(self):
        resumo = caixa_resumo_fechamento()
        if not resumo:
            return "Nao ha caixa aberto para fechar."
        saldo = resumo["saldo"]
        if not messagebox.askyesno("Fechar Caixa", f"A Isis calculou o saldo em {format_moeda(saldo)}. Deseja fechar o caixa?"):
            return "Fechamento cancelado."
        try:
            caixa_fechar_simples(resumo["caixa_id"], saldo, self.current_user['nome'])
            return f"Caixa fechado com saldo final de {format_moeda(saldo)}."
        except Exception as e:
            registrar_erro_sistema("Isis fechar caixa", e)
            return f"Nao consegui fechar o caixa. Detalhe: {e}"

    def isis_alertas_operacionais(self, formato_balao=False):
        return isis_alertas_service(format_moeda, formato_balao)

    def issis_resumo_inteligente_loja(self):
        return isis_resumo_inteligente_loja_service(format_moeda)

    def issis_prioridades_do_dia(self):
        return isis_prioridades_do_dia_texto()

    def issis_produtos_sem_giro(self):
        return isis_produtos_sem_giro_texto()

    def issis_clientes_incompletos(self):
        return isis_clientes_incompletos_texto()

    def status_caixa_issis(self):
        return caixa_status_aberto()

    def montar_financeiro(self):
        for w in self.tab_fin.winfo_children():
            w.destroy()
        f = ctk.CTkFrame(self.tab_fin, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=10)

        fin_tabs = ctk.CTkTabview(f, segmented_button_selected_color=self.cor_botao)
        fin_tabs.pack(fill="both", expand=True)
        tab_caixa = fin_tabs.add("Caixa & Fluxo")
        tab_contas = fin_tabs.add("Contas a Pagar")
        tab_dre = fin_tabs.add("DRE & Projecoes")
        anos_disponiveis = [str(ano) for ano in range(datetime.now().year - 4, datetime.now().year + 2)]

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
            return caixa_obter_id_ativo()

        def atualizar_status_caixa():
            cx = caixa_status_aberto()
            if cx:
                lbl_status_cx.configure(text=f"CAIXA ABERTO\nDesde: {cx[2]}", text_color="#8fd36b")
                ent_troco.delete(0, 'end')
                ent_troco.insert(0, format_moeda(cx[1]))
                btn_abrir_cx.configure(state="disabled")
                btn_fechar_cx.configure(state="normal")
            else:
                lbl_status_cx.configure(text="CAIXA FECHADO", text_color="#ff4d4d")
                ent_troco.delete(0, 'end')
                btn_abrir_cx.configure(state="normal")
                btn_fechar_cx.configure(state="disabled")

        def abrir_caixa():
            try:
                valor_ini = conv_float(ent_troco.get())
                caixa_abrir(valor_ini, self.current_user['nome'], "Abertura de Caixa")
                atualizar_status_caixa()
                atualizar_fluxo()
            except Exception as e:
                messagebox.showerror("Caixa", f"Erro ao abrir caixa: {e}")

        def fechar_caixa():
            resumo = caixa_resumo_fechamento()
            if not resumo:
                return
            cx_id = resumo["caixa_id"]
            saldo = resumo["saldo"]
            formas = resumo["formas"]
            win = ctk.CTkToplevel(self)
            win.title("Fechamento com Conferencia")
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
                texto = "Conferencia por forma:\n"
                for k in formas:
                    texto += f"{k}: sistema {format_moeda(formas[k])} | conferido {format_moeda(informado[k])}\n"
                texto += f"\nDiferenca: {format_moeda(diferenca)}\n\nConfirmar fechamento?"
                if not messagebox.askyesno("Confirmar fechamento", texto):
                    return
                try:
                    caixa_fechar_conferido(cx_id, saldo, formas, informado, self.current_user['nome'])
                    registrar_log(self.current_user['nome'], "Fechamento caixa", f"Caixa {cx_id} fechado. Diferenca {format_moeda(diferenca)}")
                    win.destroy()
                    atualizar_status_caixa()
                    atualizar_fluxo()
                except Exception as e:
                    messagebox.showerror("Caixa", f"Erro ao fechar caixa: {e}")

            ctk.CTkButton(card, text="CONFIRMAR FECHAMENTO", height=42, font=self.font_button, fg_color="#5f7f4c", command=confirmar_fechamento).pack(fill="x", padx=20, pady=18)

        btn_abrir_cx = ctk.CTkButton(esq_cx, text="ABRIR CAIXA", height=38, font=self.font_button, fg_color="#5f7f4c", command=abrir_caixa)
        btn_abrir_cx.pack(pady=8, padx=15, fill="x")
        btn_fechar_cx = ctk.CTkButton(esq_cx, text="FECHAR CAIXA", height=38, font=self.font_button, fg_color="#7f4c4c", command=fechar_caixa)
        btn_fechar_cx.pack(pady=8, padx=15, fill="x")

        ctk.CTkLabel(esq_cx, text="Lancamento Manual", font=self.font_label).pack(pady=(15, 2))
        ent_desc_fl = ctk.CTkEntry(esq_cx, placeholder_text="Descricao", height=34, font=self.font_input)
        ent_desc_fl.pack(pady=2, padx=15, fill="x")
        ent_val_fl = ctk.CTkEntry(esq_cx, placeholder_text="Valor", height=34, font=self.font_input)
        ent_val_fl.pack(pady=2, padx=15, fill="x")
        ent_val_fl.bind("<KeyRelease>", self.mascara_moeda)

        def lancar_fluxo(tipo):
            desc = ent_desc_fl.get().strip()
            val = conv_float(ent_val_fl.get())
            cx_id = obter_caixa_id_ativo()
            if not cx_id:
                messagebox.showerror("Erro", "Abra o caixa antes de fazer lancamentos.")
                return
            if desc and val > 0:
                try:
                    rotulo = "Reforco de caixa" if tipo == "Entrada" else "Sangria"
                    caixa_lancar_fluxo(tipo, desc, val, cx_id, rotulo, operador=self.current_user['nome'])
                    registrar_log(self.current_user['nome'], rotulo, f"{desc} - {format_moeda(val)}")
                    ent_desc_fl.delete(0, 'end')
                    ent_val_fl.delete(0, 'end')
                    atualizar_fluxo()
                except Exception as e:
                    messagebox.showerror("Caixa", f"Erro ao lancar fluxo: {e}")

        ctk.CTkButton(esq_cx, text="REFORCO DE CAIXA", height=34, font=self.font_button, fg_color="#3c7bb9", command=lambda: [lancar_fluxo("Entrada")]).pack(pady=4, padx=15, fill="x")
        ctk.CTkButton(esq_cx, text="SANGRIA", height=34, font=self.font_button, fg_color="#b93c3c", command=lambda: [lancar_fluxo("Saida")]).pack(pady=4, padx=15, fill="x")

        tree_fluxo = ttk.Treeview(dir_cx, columns=("t", "d", "v", "dh"), show="headings", height=10)
        for c, h in zip(("t", "d", "v", "dh"), ("Tipo", "Descricao", "Valor", "Data/Hora")):
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
            for r in caixa_listar_fluxo(cx_id):
                tree_fluxo.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), r[3]))
        atualizar_status_caixa()
        atualizar_fluxo()

        f_cp = ctk.CTkFrame(tab_contas, fg_color="transparent")
        f_cp.pack(fill="both", expand=True, padx=10, pady=10)
        cad_cp = ctk.CTkFrame(f_cp, fg_color=self.cor_vinho, corner_radius=15)
        cad_cp.pack(fill="x", pady=5)
        ent_desc_cp = ctk.CTkEntry(cad_cp, placeholder_text="Descricao", height=38, font=self.font_input)
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
                try:
                    caixa_salvar_conta(desc, val, venc, centro)
                    ent_desc_cp.delete(0, 'end')
                    ent_val_cp.delete(0, 'end')
                    ent_venc_cp.delete(0, 'end')
                    atualizar_contas()
                except Exception as e:
                    messagebox.showerror("Contas", f"Erro ao salvar conta: {e}")

        def marcar_pago():
            sel = tree_contas.selection()
            if sel:
                id_c = tree_contas.item(sel[0], "values")[0]
                cx_id = obter_caixa_id_ativo()
                if not cx_id:
                    messagebox.showwarning("Caixa", "Abra o caixa diario primeiro.")
                    return
                try:
                    conta = caixa_marcar_conta_paga(id_c, cx_id)
                    registrar_log(self.current_user['nome'], "Conta paga", f"{conta[0]} - {format_moeda(conta[1])}")
                    atualizar_contas()
                    atualizar_fluxo()
                except Exception as e:
                    messagebox.showerror("Contas", str(e))

        def excluir_conta():
            sel = tree_contas.selection()
            if sel:
                caixa_excluir_conta(tree_contas.item(sel[0], "values")[0])
                atualizar_contas()

        ctk.CTkButton(cad_cp, text="SALVAR CONTA", command=salvar_conta, fg_color=self.cor_botao, height=38, font=self.font_button).pack(side="left", padx=5)
        ctk.CTkButton(cad_cp, text="MARCAR COMO PAGO", command=marcar_pago, fg_color="#5f7f4c", height=38, font=self.font_button).pack(side="right", padx=5)
        ctk.CTkButton(cad_cp, text="EXCLUIR", command=excluir_conta, fg_color="#7f4c4c", height=38, font=self.font_button).pack(side="right", padx=5)

        tree_contas = ttk.Treeview(f_cp, columns=("id", "d", "v", "dv", "c", "s"), show="headings")
        for c, h in zip(("id", "d", "v", "dv", "c", "s"), ("ID", "Descricao da Despesa", "Valor", "Vencimento", "Centro Custos", "Situacao")):
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
            for r in caixa_listar_contas():
                tree_contas.insert("", "end", values=(r[0], r[1], format_moeda(r[2]), r[3], r[4], r[5]))
        atualizar_contas()

        f_dre = ctk.CTkFrame(tab_dre, fg_color="transparent")
        f_dre.pack(fill="both", expand=True, padx=10, pady=10)
        filtros_dre = ctk.CTkFrame(f_dre, fg_color=self.cor_vinho, corner_radius=12)
        filtros_dre.pack(fill="x", pady=5)

        ctk.CTkLabel(filtros_dre, text="Periodo DRE:", font=self.font_label).pack(side="left", padx=10, pady=10)
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
        self.lbl_proj_viewer = ctk.CTkLabel(dir_dre_card, text="Carregando projecao...", font=("Arial", 13), justify="left", wraplength=250)
        self.lbl_proj_viewer.pack(fill="both", expand=True, padx=15, pady=15)

        def calcular_dre_projecoes():
            mes = self.dre_mes.get()
            ano = self.dre_ano.get()
            dados = calcular_dre_periodo(mes, ano)
            despesas = dados["despesas"]
            dre_texto = (
                f"--------------------------------------------------\n"
                f"      DEMONSTRATIVO DE RESULTADOS (DRE) - {mes}/{ano}\n"
                f"--------------------------------------------------\n"
                f"(+) Receitas Brutas:               {format_moeda(dados['receitas'])}\n"
                f"(-) Custo de Mercadorias (CPV):   -{format_moeda(dados['custos'])}\n"
                f"--------------------------------------------------\n"
                f"(=) LUCRO BRUTO:                   {format_moeda(dados['lucro_bruto'])}\n\n"
                f"(-) Despesas por Centro de Custo:\n"
                f"  - Aluguel:                      -{format_moeda(despesas['Aluguel'])}\n"
                f"  - Internet:                     -{format_moeda(despesas['Internet'])}\n"
                f"  - Energia:                      -{format_moeda(despesas['Energia'])}\n"
                f"  - Compras (Insumos):            -{format_moeda(despesas['Compras'])}\n"
                f"  - Marketing / Promocoes:        -{format_moeda(despesas['Marketing'])}\n"
                f"  - Outras Despesas:              -{format_moeda(despesas['Outros'])}\n"
                f"--------------------------------------------------\n"
                f"(=) LUCRO LIQUIDO DO PERIODO:      {format_moeda(dados['lucro_liquido'])}\n"
                f"--------------------------------------------------"
            )
            self.lbl_dre_viewer.configure(text=dre_texto)
            proj_texto = (
                f"PROJECAO FINANCEIRA MENSAL\n\n"
                f"Ritmo atual de faturamento previsto:\n"
                f"{format_moeda(dados['faturamento_previsto'])}\n\n"
                f"Media diaria: {format_moeda(dados['media_diaria'])}\n"
                f"Dias avaliados: {dados['dias_avaliados']}/{dados['dias_no_mes']}"
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
