def aplicar_caixa_fechamento_avancado_runtime(fonte):
    """Mantém compatibilidade visual com fechamento avançado de caixa."""
    antigo = 'resumo["formas"]'
    novo = 'resumo.get("formas_detalhadas") or resumo["formas"]'
    fonte = fonte.replace(antigo, novo)
    return fonte
