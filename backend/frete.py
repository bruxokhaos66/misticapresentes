from __future__ import annotations

"""Cálculo centralizado de frete (Fase 3 — entrega ou retirada no checkout).

Única fonte de verdade para a regra comercial de frete. Nunca duplicar esta
regra em outro arquivo — todo ponto que grava um pedido (checkout público,
pedido sob encomenda) deve importar `calcular_frete` daqui.

Regra:
- retirada na loja: sempre R$ 0,00;
- entrega em Pinhalzinho/SC: R$ 0,00;
- entrega em outra cidade de SC: R$ 30,00;
- entrega fora de SC: R$ 50,00;
- campanha/cupom com frete grátis vigente zera o frete de qualquer entrega
  (retirada já é zero por definição).

O valor nunca é aceito do navegador: o servidor sempre recalcula a partir de
`forma_recebimento`/`endereco_cidade`/`endereco_uf` já persistidos/validados.
"""

import unicodedata

FRETE_RETIRADA = 0.0
FRETE_MESMA_CIDADE = 0.0
FRETE_OUTRA_CIDADE_SC = 30.0
FRETE_FORA_SC = 50.0

CIDADE_LOJA_NORMALIZADA = "pinhalzinho"
UF_LOJA_NORMALIZADA = "sc"

PRAZO_ENTREGA_DIAS_UTEIS = "5 a 10 dias úteis"

UF_BRASIL = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}


def normalizar_texto(valor: str | None) -> str:
    """Remove acentos, colapsa espaços e passa para minúsculas — para que
    "São Paulo", " sao   paulo ", "SÃO PAULO" e "Sao Paulo" sejam tratados
    como o mesmo valor na hora de classificar o frete."""
    texto = str(valor or "").strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = " ".join(texto.split())
    return texto.lower()


def normalizar_uf(valor: str | None) -> str:
    return normalizar_texto(valor).upper()


def calcular_frete(
    forma_recebimento: str | None,
    cidade: str | None,
    uf: str | None,
    *,
    frete_gratis: bool = False,
) -> float:
    """Calcula o valor de frete, em reais, no servidor.

    - `forma_recebimento` "retirada" (ou qualquer valor diferente de
      "entrega") sempre resulta em frete zero.
    - Para "entrega", cidade/UF normalizadas (sem acento, sem diferença de
      caixa, sem espaços extras) decidem a faixa de frete.
    - `frete_gratis=True` (cupom/campanha vigente) zera o frete de qualquer
      entrega — retirada já é zero por definição.
    """
    forma = normalizar_texto(forma_recebimento)
    if forma != "entrega":
        return FRETE_RETIRADA
    if frete_gratis:
        return 0.0
    uf_norm = normalizar_uf(uf)
    if uf_norm != UF_LOJA_NORMALIZADA.upper():
        return FRETE_FORA_SC
    cidade_norm = normalizar_texto(cidade)
    if cidade_norm == CIDADE_LOJA_NORMALIZADA:
        return FRETE_MESMA_CIDADE
    return FRETE_OUTRA_CIDADE_SC
