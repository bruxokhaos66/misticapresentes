import json, random
from datetime import datetime
from pathlib import Path
from config import DOCS_PATH

ARQ = Path(DOCS_PATH) / "mistica_frajola_pet.json"

PADRAO = {
    "nome": "Frajola", "fase": "bebê", "idade_dias": 0,
    "fome": 80, "felicidade": 75, "saude": 90,
    "limpeza": 85, "energia": 80, "disciplina": 55,
    "xp": 0, "ativo": True, "dormindo": False,
    "doente": False, "chamado": "",
    "ultimo_evento": "Frajola chegou na Mística Presentes.",
    "created_at": "", "last_update": ""
}

CHAMADOS = [
    "Miau! Estou com fome.",
    "Miau! Quero brincar.",
    "Minha caixinha precisa de limpeza.",
    "Quero carinho e atenção.",
    "Será que já é hora de dormir?"
]

SPRITES = {
    "normal": " /\\_/\\\\\n( o.o )\n > ^ <",
    "feliz": " /\\_/\\\\\n( ^.^ )\n > ᆺ <",
    "fome": " /\\_/\\\\\n( o.o )\n > 🍚 <",
    "sono": " /\\_/\\\\\n( -.- )z\n > ^ <",
    "sujo": " /\\_/\\\\\n( o.o )\n > 🚽 <",
    "cuidado": " /\\_/\\\\\n( o_o )\n > + <",
}

def clamp(v):
    return int(max(0, min(100, round(float(v)))))

def fase_por_idade(d):
    if d < 1: return "bebê"
    if d < 3: return "criança"
    if d < 7: return "adolescente"
    return "adulto"

def salvar_estado(e):
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
    return e

def carregar_estado():
    e = dict(PADRAO)
    if ARQ.exists():
        try:
            dados = json.loads(ARQ.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                e.update(dados)
        except Exception:
            pass
    agora = datetime.now().isoformat(timespec="seconds")
    if not e.get("created_at"): e["created_at"] = agora
    if not e.get("last_update"): e["last_update"] = agora
    return atualizar_passagem_tempo(e)

def atualizar_passagem_tempo(e):
    agora = datetime.now()
    try:
        ultimo = datetime.fromisoformat(str(e.get("last_update")))
    except Exception:
        ultimo = agora
    minutos = max(0, int((agora - ultimo).total_seconds() // 60))
    if minutos <= 0:
        e["last_update"] = agora.isoformat(timespec="seconds")
        return e

    horas = minutos / 60
    if e.get("ativo", True):
        dormindo = bool(e.get("dormindo"))
        e["fome"] = clamp(e.get("fome", 80) - horas * 3)
        e["limpeza"] = clamp(e.get("limpeza", 85) - horas * 2)
        e["felicidade"] = clamp(e.get("felicidade", 75) - horas * (1 if dormindo else 2.4))
        e["energia"] = clamp(e.get("energia", 80) + horas * 8 if dormindo else e.get("energia", 80) - horas * 2)

        if e["fome"] < 15 or e["limpeza"] < 15:
            e["saude"] = clamp(e.get("saude", 90) - horas * 4)
        else:
            e["saude"] = clamp(e.get("saude", 90) + horas)

        e["doente"] = e["saude"] < 35

        if not e.get("chamado") and random.random() < min(0.65, horas * 0.14):
            e["chamado"] = random.choice(CHAMADOS)

        try:
            criado = datetime.fromisoformat(str(e.get("created_at")))
            idade = max(0, (agora.date() - criado.date()).days)
        except Exception:
            idade = 0
        e["idade_dias"] = idade
        e["fase"] = fase_por_idade(idade)

        if e["saude"] <= 0 or (e["fome"] <= 0 and e["felicidade"] <= 0):
            e["ativo"] = False
            e["ultimo_evento"] = "Frajola ficou inativo por falta de cuidado. Reinicie para começar novamente."

    e["last_update"] = agora.isoformat(timespec="seconds")
    return salvar_estado(e)

def status_resumo(e):
    if not e.get("ativo", True): return "Inativo"
    if e.get("dormindo"): return "Dormindo"
    if e.get("doente"): return "Precisando de cuidado"
    if e.get("fome", 0) < 30: return "Com fome"
    if e.get("limpeza", 0) < 30: return "Ambiente sujo"
    if e.get("felicidade", 0) > 80: return "Feliz"
    return "Normal"

def sprite_atual(e):
    s = status_resumo(e)
    if s == "Dormindo": return SPRITES["sono"]
    if s == "Precisando de cuidado" or s == "Inativo": return SPRITES["cuidado"]
    if s == "Com fome": return SPRITES["fome"]
    if s == "Ambiente sujo": return SPRITES["sujo"]
    if s == "Feliz": return SPRITES["feliz"]
    return SPRITES["normal"]

def executar_acao(acao):
    e = carregar_estado()
    acao = (acao or "").lower()

    if acao == "reiniciar":
        e = dict(PADRAO)
        agora = datetime.now().isoformat(timespec="seconds")
        e["created_at"] = agora
        e["last_update"] = agora
        return salvar_estado(e), "Frajola foi reiniciado como bebê."

    if not e.get("ativo", True):
        return e, "Frajola está inativo. Use Reiniciar."

    if acao == "alimentar":
        e["fome"] = clamp(e["fome"] + 28); e["saude"] = clamp(e["saude"] + 5); e["xp"] += 2
        msg = "Você alimentou o Frajola."
    elif acao == "lanche":
        e["fome"] = clamp(e["fome"] + 12); e["felicidade"] = clamp(e["felicidade"] + 10); e["disciplina"] = clamp(e["disciplina"] - 2); e["xp"] += 1
        msg = "Frajola ganhou um lanchinho."
    elif acao == "brincar":
        ganho = random.randint(8, 18)
        e["felicidade"] = clamp(e["felicidade"] + ganho); e["energia"] = clamp(e["energia"] - 10); e["xp"] += 4
        msg = f"Minijogo: Frajola brincou e ganhou {ganho} de felicidade."
    elif acao == "cuidar":
        e["saude"] = clamp(e["saude"] + 32); e["doente"] = e["saude"] < 35; e["xp"] += 3
        msg = "Você cuidou da saúde do Frajola."
    elif acao == "limpar":
        e["limpeza"] = clamp(e["limpeza"] + 45); e["saude"] = clamp(e["saude"] + 6); e["xp"] += 2
        msg = "Você limpou o ambiente do Frajola."
    elif acao == "dormir":
        e["dormindo"] = not bool(e.get("dormindo"))
        msg = "Frajola foi dormir." if e["dormindo"] else "Frajola acordou."
    elif acao == "disciplinar":
        e["disciplina"] = clamp(e["disciplina"] + 12); e["felicidade"] = clamp(e["felicidade"] - 3); e["xp"] += 1
        msg = "Frajola ficou mais disciplinado."
    elif acao == "atender":
        e["chamado"] = ""; e["felicidade"] = clamp(e["felicidade"] + 8); e["xp"] += 2
        msg = "Você respondeu ao chamado do Frajola."
    else:
        msg = "Ação não reconhecida."

    e["ultimo_evento"] = msg
    e["last_update"] = datetime.now().isoformat(timespec="seconds")
    return salvar_estado(e), msg
