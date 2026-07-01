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
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return ""
    body = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
