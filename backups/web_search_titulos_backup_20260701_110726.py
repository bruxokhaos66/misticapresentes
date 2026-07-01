import html
import re
import urllib.parse
import urllib.request
from datetime import datetime


def _limpar_titulo(titulo):
    titulo = re.sub(r"<.*?>", "", titulo or "", flags=re.S)
    return html.unescape(titulo).strip()


def _limpar_link(link):
    link = html.unescape(link or "").strip()
    if "uddg=" in link:
        try:
            link = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("uddg", [link])[0]
            link = urllib.parse.unquote(link)
        except Exception:
            pass
    if link.startswith("//"):
        link = "https:" + link
    return link


def _abrir(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _pesquisar_duckduckgo_lite(query, limite):
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    pagina = _abrir(url)
    padroes = [
        r'<a rel="nofollow" href="(.*?)">(.*?)</a>',
        r'<a[^>]+class="result-link"[^>]+href="(.*?)"[^>]*>(.*?)</a>',
    ]
    resultados = []
    for padrao in padroes:
        for link, titulo in re.findall(padrao, pagina, flags=re.S | re.I):
            titulo = _limpar_titulo(titulo)
            link = _limpar_link(link)
            if titulo and link and link.startswith("http"):
                resultados.append({"titulo": titulo, "link": link, "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M")})
            if len(resultados) >= limite:
                return resultados
    return resultados


def _pesquisar_bing(query, limite):
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
    pagina = _abrir(url)
    resultados = []
    blocos = re.findall(r'<li class="b_algo".*?</li>', pagina, flags=re.S | re.I)
    for bloco in blocos:
        m = re.search(r'<a href="(http.*?)"[^>]*>(.*?)</a>', bloco, flags=re.S | re.I)
        if not m:
            continue
        link = _limpar_link(m.group(1))
        titulo = _limpar_titulo(m.group(2))
        if titulo and link:
            resultados.append({"titulo": titulo, "link": link, "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M")})
        if len(resultados) >= limite:
            break
    return resultados


def _remover_duplicados(resultados, limite):
    vistos = set()
    limpos = []
    for item in resultados:
        chave = item.get("link", "")
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        limpos.append(item)
        if len(limpos) >= limite:
            break
    return limpos


def pesquisar(query, limite=6):
    resultados = []
    erros = []
    for func in (_pesquisar_duckduckgo_lite, _pesquisar_bing):
        try:
            resultados.extend(func(query, limite))
            resultados = _remover_duplicados(resultados, limite)
            if len(resultados) >= limite:
                return resultados
        except Exception as e:
            erros.append(str(e))
    return _remover_duplicados(resultados, limite)
