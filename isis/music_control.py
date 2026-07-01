import webbrowser

PLAYLISTS = {
    "relaxar": "https://www.youtube.com/results?search_query=musica+relaxante+loja",
    "loja": "https://www.youtube.com/results?search_query=musica+ambiente+loja+relaxante",
    "xamanica": "https://www.youtube.com/results?search_query=musica+xamanica+ambiente",
}

def executar(texto):
    p = str(texto or "").lower()
    if any(x in p for x in ["musica", "música", "playlist", "som"]):
        chave = "loja"
        if "relax" in p:
            chave = "relaxar"
        elif "xaman" in p:
            chave = "xamanica"
        webbrowser.open(PLAYLISTS[chave])
        return f"Abri uma busca de música ambiente para {chave}."
    return None
