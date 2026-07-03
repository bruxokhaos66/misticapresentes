import json
import os
import threading
from datetime import datetime

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents")
CACHE_PATH = os.path.join(DOCS_PATH, "mistica_mensagens_isis_dashboard.json")
FIXO_PATH = os.path.join(DOCS_PATH, "mistica_mensagem_dashboard.txt")

MENSAGENS = [
    "Hoje é dia de vender com calma, atenção e boa energia. Cliente bem atendido sempre lembra de voltar.",
    "A Isis lembra: loja organizada, sorriso no rosto e produto bem apresentado já fazem metade da venda.",
    "Foco no atendimento: primeiro escute, depois ofereça. A venda certa nasce de uma boa conversa.",
    "Aviso da Isis: confira vitrine, balcão e etiquetas. Pequenos detalhes evitam dúvidas e melhoram a experiência.",
    "Bruxaria boa do comércio: simpatia, organização e constância. O resto aparece no caixa.",
    "Piada rápida da Isis: por que o incenso foi promovido? Porque ele sempre elevava o clima da loja.",
    "Hoje, transforme cada atendimento em acolhimento. Produto vendido passa, experiência boa fica.",
    "Aviso importante: estoque alinhado e preço conferido evitam retrabalho na hora da venda.",
    "A meta fica mais leve quando cada cliente recebe atenção verdadeira, mesmo quando não compra na hora.",
    "Piada da Isis: o cristal não fofoca, mas vive refletindo sobre tudo.",
    "Energia do turno: menos pressa, mais presença. Atendimento tranquilo vende melhor.",
    "Aviso da Isis: mantenha o balcão limpo e os produtos fáceis de encontrar. Isso ajuda você e o cliente.",
    "Vender não é empurrar produto; é ajudar alguém a escolher melhor.",
    "Piada rápida: a vela entrou na loja triste, mas saiu iluminada.",
    "Hoje é um bom dia para encantar no simples: cumprimento, atenção, explicação clara e carinho.",
    "Aviso operacional: se notar produto com baixo estoque, já registre para reposição antes de faltar.",
]


def slot_atual():
    agora = datetime.now()
    return f"{agora.strftime('%Y%m%d')}-{agora.hour // 3}", ((agora.timetuple().tm_yday * 8) + (agora.hour // 3)) % len(MENSAGENS)


def _cache():
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                dados = json.load(f)
            return dados if isinstance(dados, dict) else {}
    except Exception:
        pass
    return {}


def _salvar(dados):
    try:
        os.makedirs(DOCS_PATH, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def mensagem_atual():
    try:
        if os.path.exists(FIXO_PATH):
            with open(FIXO_PATH, "r", encoding="utf-8") as f:
                texto = f.read().strip()
            if texto.upper().startswith("FIXO:"):
                return texto.split(":", 1)[1].strip() or MENSAGENS[0]
    except Exception:
        pass
    chave, idx = slot_atual()
    dados = _cache()
    return str(dados.get(chave) or MENSAGENS[idx]).strip()


def buscar_online_e_salvar():
    chave, idx = slot_atual()
    dados = _cache()
    if dados.get(chave):
        return dados[chave]
    consultas = [
        "frase motivacional curta atendimento vendas loja",
        "dica importante atendimento comercio varejo loja",
        "piada curta leve para ambiente de trabalho",
    ]
    try:
        from isis.web_search import pesquisar
        resultados = pesquisar(consultas[idx % len(consultas)], limite=3)
        for item in resultados:
            titulo = str(item.get("titulo", "")).strip()
            if 35 <= len(titulo) <= 150:
                msg = f"Isis pesquisou agora: {titulo}"
                dados[chave] = msg
                _salvar(dados)
                return msg
    except Exception:
        pass
    return None


def buscar_online_em_background(callback=None):
    def run():
        msg = buscar_online_e_salvar()
        if msg and callback:
            try:
                callback(msg)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()
