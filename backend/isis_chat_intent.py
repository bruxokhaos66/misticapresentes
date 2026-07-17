"""Camada 3 — interpretação de intenção (modo determinístico, sem IA).

Reconhece as intenções mínimas pedidas pelo briefing usando regras e
palavras-chave em PT-BR (sem provedor de IA externo, sem embeddings). Cada
mensagem gera no máximo uma intenção primária + sinais auxiliares
(orçamento, aroma, nomes de produto citados) -- nunca inventa uma intenção
fora da lista fechada abaixo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENTS = (
    "buscar_produto",
    "pedir_recomendacao",
    "informar_finalidade",
    "informar_aroma",
    "informar_faixa_preco",
    "comparar_produtos",
    "montar_kit",
    "produto_complementar",
    "buscar_curso",
    "perguntar_disponibilidade",
    "perguntar_preco",
    "perguntar_modo_uso",
    "saudacao",
    "desconhecida",
)

_PADRAO_PRECO = re.compile(r"(?:r\$\s*)?(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:reais|r\$)?", re.IGNORECASE)
_PADRAO_ATE = re.compile(r"at[ée]\s+(?:r\$\s*)?(\d{1,4}(?:[.,]\d{1,2})?)", re.IGNORECASE)
_PADRAO_ENTRE = re.compile(
    r"entre\s+(?:r\$\s*)?(\d{1,4}(?:[.,]\d{1,2})?)\s+e\s+(?:r\$\s*)?(\d{1,4}(?:[.,]\d{1,2})?)", re.IGNORECASE
)

_AROMAS_CONHECIDOS = (
    "lavanda", "lavanda francesa", "baunilha", "sândalo", "sandalo", "capim santo",
    "alecrim", "jasmim", "rosa", "canela", "cravo", "citronela", "eucalipto",
    "patchouli", "amadeirado", "cítrico", "citrico", "floral",
)

_PALAVRAS_KIT = ("kit", "montar um kit", "monte um kit", "combo", "conjunto")
_PALAVRAS_COMPARACAO = ("diferença", "diferenca", "compare", "comparar", "qual a diferença", "versus", " x ")
_PALAVRAS_DISPONIBILIDADE = ("disponível", "disponivel", "tem estoque", "ainda tem", "está disponível")
_PALAVRAS_PRECO = ("quanto custa", "qual o preço", "qual o valor", "preço", "preco", "valor")
_PALAVRAS_MODO_USO = ("como usar", "modo de uso", "como aplicar", "como funciona o uso")
_PALAVRAS_COMPLEMENTAR = ("mais alguma coisa", "além disso", "algo para acompanhar", "complementar", "junto com")
_PALAVRAS_CURSO = ("curso", "aula", "escola mística", "escola mistica", "aprender", "xamanismo", "workshop")
_PALAVRAS_FINALIDADE = (
    "relaxar", "dormir", "ansiedade", "presente", "presentear", "meditar", "meditação",
    "energia", "proteção", "protecao", "amor", "prosperidade", "limpeza espiritual",
)
_PALAVRAS_RECOMENDACAO = ("recomend", "sugir", "sugest", "indica", "qual voc", "o que voc")
_PALAVRAS_SAUDACAO = ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "oii", "eae")


@dataclass
class ResultadoIntent:
    intent: str
    termo_busca: str = ""
    aroma: str | None = None
    preco_min: float | None = None
    preco_max: float | None = None
    finalidade: str | None = None
    sinais: dict = field(default_factory=dict)


def _normalizar(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def _extrair_preco(texto: str) -> tuple[float | None, float | None]:
    m_entre = _PADRAO_ENTRE.search(texto)
    if m_entre:
        valores = sorted(float(v.replace(",", ".")) for v in m_entre.groups())
        return valores[0], valores[1]
    m_ate = _PADRAO_ATE.search(texto)
    if m_ate:
        return None, float(m_ate.group(1).replace(",", "."))
    return None, None


def _extrair_aroma(texto: str) -> str | None:
    for aroma in _AROMAS_CONHECIDOS:
        if aroma in texto:
            return aroma
    return None


def _extrair_finalidade(texto: str) -> str | None:
    for palavra in _PALAVRAS_FINALIDADE:
        if palavra in texto:
            return palavra
    return None


def detectar_intent(texto_bruto: str) -> ResultadoIntent:
    texto = _normalizar(texto_bruto)
    if not texto:
        return ResultadoIntent(intent="desconhecida")

    preco_min, preco_max = _extrair_preco(texto)
    aroma = _extrair_aroma(texto)
    finalidade = _extrair_finalidade(texto)

    if any(palavra in texto for palavra in _PALAVRAS_KIT):
        return ResultadoIntent(intent="montar_kit", preco_min=preco_min, preco_max=preco_max, aroma=aroma, finalidade=finalidade, termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_COMPARACAO):
        return ResultadoIntent(intent="comparar_produtos", termo_busca=texto, aroma=aroma)

    if any(palavra in texto for palavra in _PALAVRAS_CURSO):
        return ResultadoIntent(intent="buscar_curso", termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_DISPONIBILIDADE):
        return ResultadoIntent(intent="perguntar_disponibilidade", termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_MODO_USO):
        return ResultadoIntent(intent="perguntar_modo_uso", termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_PRECO):
        return ResultadoIntent(intent="perguntar_preco", termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_COMPLEMENTAR):
        return ResultadoIntent(intent="produto_complementar", termo_busca=texto)

    if preco_min is not None or preco_max is not None:
        return ResultadoIntent(intent="informar_faixa_preco", preco_min=preco_min, preco_max=preco_max, termo_busca=texto)

    if aroma and not finalidade:
        return ResultadoIntent(intent="informar_aroma", aroma=aroma, termo_busca=texto)

    if finalidade:
        return ResultadoIntent(intent="informar_finalidade", finalidade=finalidade, aroma=aroma, termo_busca=texto)

    if any(palavra in texto for palavra in _PALAVRAS_RECOMENDACAO):
        return ResultadoIntent(intent="pedir_recomendacao", termo_busca=texto, aroma=aroma, finalidade=finalidade)

    if any(texto == palavra or texto.startswith(palavra + " ") for palavra in _PALAVRAS_SAUDACAO):
        return ResultadoIntent(intent="saudacao")

    if len(texto.split()) <= 6:
        return ResultadoIntent(intent="buscar_produto", termo_busca=texto)

    return ResultadoIntent(intent="pedir_recomendacao", termo_busca=texto, aroma=aroma, finalidade=finalidade)
