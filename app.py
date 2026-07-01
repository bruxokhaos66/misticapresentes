"""Entrada alternativa do sistema Mistica Presentes.

Usa caminho relativo ao proprio repositorio e aplica uma correcao segura de
indentacao conhecida antes de executar o arquivo principal.
"""
from pathlib import Path
import re
import sys

BASE_DIR = Path(__file__).resolve().parent
MAIN_FILE = BASE_DIR / "mistica_presentes.py"


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
        except Exception:
            pass
        self.txt_chat.insert("end", "Isis a Bruxinha:\\n")
        self.inserir_texto_com_links_isis(resposta)
        self.txt_chat.insert("end", "\\n\\n" + "-" * 56 + "\\n\\n")
        self.txt_chat.configure(state="disabled")
        self.txt_chat.see("end")
        self.ent_pergunta.delete(0, "end")
'''


def carregar_codigo_corrigido(caminho: Path) -> str:
    codigo = caminho.read_text(encoding="utf-8-sig")
    codigo = codigo.replace("\t", "    ")

    padrao = (
        r"\n[ \t]*def inserir_texto_com_links_isis\(self, texto\):"
        r".*?"
        r"(?=\n[ \t]*def importar_json_isis_para_sqlite\(self\):)"
    )

    def bloco_corrigido(_match):
        return "\n" + BLOCO_ISIS_CORRIGIDO.strip("\n")

    codigo, alterados = re.subn(
        padrao,
        bloco_corrigido,
        codigo,
        count=1,
        flags=re.DOTALL,
    )

    if alterados == 0:
        inicio = codigo.find("def inserir_texto_com_links_isis")
        fim = codigo.find("def importar_json_isis_para_sqlite", inicio)
        if inicio != -1 and fim != -1:
            linha_inicio = codigo.rfind("\n", 0, inicio)
            linha_fim = codigo.rfind("\n", 0, fim)
            codigo = codigo[:linha_inicio] + "\n" + BLOCO_ISIS_CORRIGIDO.strip("\n") + codigo[linha_fim:]

    return codigo


if __name__ == "__main__":
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {MAIN_FILE}")

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    fonte = carregar_codigo_corrigido(MAIN_FILE)
    globais = {
        "__name__": "__main__",
        "__file__": str(MAIN_FILE),
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(fonte, str(MAIN_FILE), "exec"), globais)
