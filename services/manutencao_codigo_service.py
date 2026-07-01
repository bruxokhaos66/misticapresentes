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

    Aceita formatos comuns:
    - 18
    - 18,00
    - R$ 18,00
    - 1.250,50
    - 1250.50
    """
    if texto is None:
        return 0.0
    txt = str(texto).strip()
    if not txt:
        return 0.0
    txt = txt.replace("R$", "").replace("r$", "").strip()
    txt = txt.replace(" ", "")

    try:
        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        limpo = re.sub(r"[^0-9]", "", str(texto))
        return float(limpo) / 100 if limpo else 0.0
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


def _substituir_conv_float(codigo: str) -> tuple[str, bool]:
    padrao = r"\ndef conv_float\(texto\):\n.*?(?=\ndef carregar_mensagem_dashboard\(\):)"
    novo, qtd = re.subn(padrao, "\n" + CONV_FLOAT_CORRIGIDA.strip("\n") + "\n", codigo, count=1, flags=re.DOTALL)
    return novo, qtd > 0


def _substituir_bloco_isis(codigo: str) -> tuple[str, bool]:
    padrao = (
        r"\n[ \t]*def inserir_texto_com_links_isis\(self, texto\):"
        r".*?"
        r"(?=\n[ \t]*def importar_json_isis_para_sqlite\(self\):)"
    )
    novo, qtd = re.subn(
        padrao,
        "\n" + BLOCO_ISIS_CORRIGIDO.strip("\n"),
        codigo,
        count=1,
        flags=re.DOTALL,
    )
    return novo, qtd > 0


def _substituir_caminho_fixo(codigo: str) -> tuple[str, bool]:
    antigo = 'PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "mistica_presentes")\nif PROJECT_DIR not in sys.path:\n    sys.path.insert(0, PROJECT_DIR)'
    novo_bloco = 'PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))\nif PROJECT_DIR not in sys.path:\n    sys.path.insert(0, PROJECT_DIR)'
    if antigo in codigo:
        return codigo.replace(antigo, novo_bloco, 1), True
    return codigo, False


def limpar_mistica_presentes(caminho: Path) -> dict:
    caminho = Path(caminho)
    resultado = {"alterou": False, "acoes": []}
    codigo = caminho.read_text(encoding="utf-8-sig")
    codigo = codigo.replace("\t", "    ")

    codigo, alterou = _substituir_caminho_fixo(codigo)
    if alterou:
        resultado["alterou"] = True
        resultado["acoes"].append("Caminho fixo antigo trocado por caminho relativo ao arquivo.")

    codigo, alterou = _substituir_conv_float(codigo)
    if alterou:
        resultado["alterou"] = True
        resultado["acoes"].append("conv_float corrigida para formatos monetarios comuns.")

    codigo, alterou = _substituir_bloco_isis(codigo)
    if alterou:
        resultado["alterou"] = True
        resultado["acoes"].append("Bloco de chat da Isis corrigido definitivamente.")

    if resultado["alterou"]:
        caminho.write_text(codigo, encoding="utf-8")

    return resultado
