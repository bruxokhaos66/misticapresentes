"""Pesquisa pública simples, sem API paga, para a Isis.
Usa DuckDuckGo HTML como fallback gratuito. Ideal para pesquisa inicial; o operador
sempre deve confirmar preço, reputação, CNPJ e prazo antes de comprar.
"""
import html
import re
import urllib.parse
import urllib.request

BLOQUEIOS = ["senha", "hackear", "invadir", "pirataria", "porn", "conteudo adulto", "arma", "droga"]


def _limpar(txt):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", "", str(txt or "")))).strip()


def pesquisar_produto(consulta, limite=8):
    consulta = str(consulta or "").strip()
    if not consulta:
        return {"ok": False, "erro": "Consulta vazia.", "resultados": []}
    if any(b in consulta.lower() for b in BLOQUEIOS):
        return {"ok": False, "erro": "Consulta bloqueada por segurança.", "resultados": []}

    consulta_final = consulta
    base = consulta.lower()
    if not any(x in base for x in ["preço", "preco", "comprar", "fornecedor", "atacado", "shopee", "mercado livre"]):
        consulta_final += " fornecedor atacado preço loja esotérica"

    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(consulta_final)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        texto = resp.read().decode("utf-8", errors="ignore")

    encontrados = re.findall(r'<a[^>]+class="result__a"[^>]+href="(.*?)"[^>]*>(.*?)</a>', texto, flags=re.I | re.S)
    resultados = []
    for link, titulo in encontrados:
        titulo = _limpar(titulo)
        link = html.unescape(link).replace("&amp;", "&")
        if "uddg=" in link:
            try:
                link = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("uddg", [link])[0]
                link = urllib.parse.unquote(link)
            except Exception:
                pass
        if titulo and link and not any(r.get("link") == link for r in resultados):
            resultados.append({"titulo": titulo[:180], "link": link})
        if len(resultados) >= int(limite):
            break
    return {"ok": bool(resultados), "consulta": consulta, "consulta_final": consulta_final, "resultados": resultados}
