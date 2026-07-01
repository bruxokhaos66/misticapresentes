"""Manutencao segura do arquivo principal.

Este modulo faz migracoes pontuais no mistica_presentes.py antes de executar.
A ideia e deixar o arquivo principal limpo fisicamente e remover a dependencia
do antigo patch em tempo de execucao.
"""
from pathlib import Path
import re


CONV_FLOAT_CORRIGIDA = '''
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
'''


AUTENTICAR_CORRIGIDO = '''
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
'''


FORCAR_TROCA_SENHA_CORRIGIDA = '''
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
'''


GERENCIAR_USUARIOS_HELPER_CORRIGIDO = '''
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
'''


SALVAR_USUARIO_CORRIGIDO = '''
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
'''


BLOCO_ISIS_CORRIGIDO = '''
    def inserir_texto_com_links_isis(self, texto):
        import re
        import webbrowser
        texto = str(texto or "")
        urls = re.findall(r"https?://[^\\s]+", texto)
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
        self.txt_chat.insert("end", f"Você: {pergunta}\\n\\n")
        resposta = self.processar_pergunta_ia(pergunta)
        try:
            self.registrar_aprendizado_issis(pergunta, resposta)
        except Exception as e:
            registrar_erro_sistema("Registrar aprendizado Isis", e)
        self.txt_chat.insert("end", "Isis a Bruxinha:\\n")
        self.inserir_texto_com_links_isis(resposta)
        self.txt_chat.insert("end", "\\n\\n" + "-" * 56 + "\\n\\n")
        self.txt_chat.configure(state="disabled")
        self.txt_chat.see("end")
        self.ent_pergunta.delete(0, 'end')
'''


def _replace_regex(codigo: str, padrao: str, bloco: str) -> tuple[str, bool]:
    substituto = "\n" + bloco.strip("\n") + "\n"
    novo, qtd = re.subn(padrao, lambda _match: substituto, codigo, count=1, flags=re.DOTALL)
    return novo, qtd > 0


def _substituir_conv_float(codigo: str) -> tuple[str, bool]:
    return _replace_regex(codigo, r"\ndef conv_float\(texto\):\n.*?(?=\ndef carregar_mensagem_dashboard\(\):)", CONV_FLOAT_CORRIGIDA)


def _substituir_bloco_isis(codigo: str) -> tuple[str, bool]:
    return _replace_regex(codigo, r"\n[ \t]*def inserir_texto_com_links_isis\(self, texto\):.*?(?=\n[ \t]*def importar_json_isis_para_sqlite\(self\):)", BLOCO_ISIS_CORRIGIDO)


def _substituir_caminho_fixo(codigo: str) -> tuple[str, bool]:
    antigo = 'PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "mistica_presentes")\nif PROJECT_DIR not in sys.path:\n    sys.path.insert(0, PROJECT_DIR)'
    novo_bloco = 'PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))\nif PROJECT_DIR not in sys.path:\n    sys.path.insert(0, PROJECT_DIR)'
    if antigo in codigo:
        return codigo.replace(antigo, novo_bloco, 1), True
    return codigo, False


def _substituir_autenticacao(codigo: str) -> tuple[str, bool]:
    alterou = False
    codigo, a = _replace_regex(codigo, r"\n    def autenticar\(self\):\n.*?(?=\n    def forcar_troca_senha_inicial\(self, login_usuario\):)", AUTENTICAR_CORRIGIDO)
    alterou = alterou or a
    codigo, a = _replace_regex(codigo, r"\n    def forcar_troca_senha_inicial\(self, login_usuario\):\n.*?(?=\n    def montar_abas\(self\):)", FORCAR_TROCA_SENHA_CORRIGIDA)
    alterou = alterou or a
    codigo, a = _replace_regex(codigo, r"\n    def json_gerenciar_usuarios_helper\(self, win, tree, un, uc, ue, ut, ul, up, upf\):\n.*?(?=\n    def janela_gerenciar_usuarios\(self\):)", GERENCIAR_USUARIOS_HELPER_CORRIGIDO)
    alterou = alterou or a
    codigo, a = _replace_regex(codigo, r"\n    def salvar_usuario_full\(self\):\n.*?(?=\n    def refresh_audit\(self, filtrar=False\):)", SALVAR_USUARIO_CORRIGIDO)
    alterou = alterou or a
    return codigo, alterou


def limpar_mistica_presentes(caminho: Path) -> dict:
    caminho = Path(caminho)
    resultado = {"alterou": False, "acoes": []}
    codigo = caminho.read_text(encoding="utf-8-sig").replace("\t", "    ")
    for func, msg in [
        (_substituir_caminho_fixo, "Caminho fixo antigo trocado por caminho relativo ao arquivo."),
        (_substituir_conv_float, "conv_float corrigida para formatos monetarios comuns."),
        (_substituir_autenticacao, "Autenticacao migrada para salt individual por usuario."),
        (_substituir_bloco_isis, "Bloco de chat da Isis corrigido definitivamente."),
    ]:
        codigo, alterou = func(codigo)
        if alterou:
            resultado["alterou"] = True
            resultado["acoes"].append(msg)
    if resultado["alterou"]:
        caminho.write_text(codigo, encoding="utf-8")
    return resultado
