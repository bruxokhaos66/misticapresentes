from isis import music_control, smart_home

def processar(texto):
    for modulo in (smart_home, music_control):
        try:
            resp = modulo.executar(texto)
            if resp:
                return resp
        except Exception as e:
            return f"Recebi o comando, mas a automação encontrou erro: {e}"
    return None
