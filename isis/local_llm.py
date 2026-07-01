import json
import os
import urllib.request


def _carregar_env_local():
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(app_dir, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip().strip('"').strip("'")
                if chave and chave not in os.environ:
                    os.environ[chave] = valor
    except Exception:
        pass


def gerar_resposta(prompt):
    _carregar_env_local()
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    system = os.environ.get(
        "OLLAMA_SYSTEM",
        (
            "Voce e Isis a Bruxinha, assistente virtual da loja Mistica Presentes. "
            "Fale sempre em portugues do Brasil, com clareza, simpatia e objetividade. "
            "Ajude em vendas, estoque, clientes, ideias de atendimento e organizacao da loja. "
            "Nao invente numeros do sistema: se precisar de dado real, diga que pode consultar o sistema. "
            "Nao execute acoes perigosas sem confirmacao."
        ),
    )
    body = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.35, "num_predict": 220},
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    return data.get("response", "").strip()
