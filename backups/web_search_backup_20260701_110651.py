import re
import urllib.parse
import urllib.request
from datetime import datetime


def pesquisar(query, limite=6):
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    links = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html, flags=re.S)
    resultados = []
    for link, titulo in links[:limite]:
        titulo = re.sub(r"<.*?>", "", titulo).replace("&amp;", "&").strip()
        link = link.replace("&amp;", "&")
        if "uddg=" in link:
            try:
                link = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("uddg", [link])[0]
                link = urllib.parse.unquote(link)
            except Exception:
                pass
        resultados.append({"titulo": titulo, "link": link, "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M")})
    return resultados
