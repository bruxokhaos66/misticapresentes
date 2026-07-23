"""Modelos configuráveis de descrição por categoria, usados apenas para
ajudar no preenchimento manual do cadastro/importação de produtos.

Nunca escrevem em um produto sozinhos: o painel só aplica o texto gerado
depois que o administrador confirma explicitamente, e o texto pode ser
editado livremente antes de salvar. Extensível: para adicionar uma nova
categoria, registre outra entrada em ``MODELOS`` com sua própria função
``gerar`` -- não é preciso espalhar textos fixos por outros arquivos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

MODO_DE_USO_ESSENCIAS_VIA_AROMA = (
    "Adicione 15 gotas no recipiente do aromatizador elétrico ou com outra "
    "fonte de calor e aproveite uma fragrância agradável e duradoura."
)


@dataclass(frozen=True)
class ModeloDescricao:
    chave: str
    titulo: str
    campos: list[str]
    gerar: Callable[[dict], dict]


def _gerar_essencias(campos: dict) -> dict:
    nome = str(campos.get("nome") or "").strip()
    aroma = str(campos.get("aroma") or "").strip()
    conteudo = str(campos.get("conteudo") or "").strip()
    marca = str(campos.get("marca") or "").strip()

    partes_curta = [p for p in (f"Essência {aroma}" if aroma else nome, conteudo) if p]
    descricao_curta = " — ".join(partes_curta) if partes_curta else ""

    linhas = []
    if nome:
        linhas.append(nome)
    if aroma:
        linhas.append(f"Aroma: {aroma}.")
    if conteudo:
        linhas.append(f"Conteúdo: {conteudo}.")
    if marca:
        linhas.append(f"Marca: {marca}.")
    descricao = " ".join(linhas)

    return {
        "descricao_curta": descricao_curta,
        "descricao": descricao,
        "destaques": aroma and f"Fragrância de {aroma}" or "",
        "modo_de_uso": MODO_DE_USO_ESSENCIAS_VIA_AROMA,
    }


def _gerar_difusores(campos: dict) -> dict:
    nome = str(campos.get("nome") or "").strip()
    aroma = str(campos.get("aroma") or "").strip()
    conteudo = str(campos.get("conteudo") or "").strip()
    marca = str(campos.get("marca") or "").strip()

    partes_curta = [p for p in (nome, aroma) if p]
    descricao_curta = " — ".join(partes_curta) if partes_curta else ""

    linhas = []
    if nome:
        linhas.append(nome)
    if aroma:
        linhas.append(f"Aroma: {aroma}.")
    if conteudo:
        linhas.append(f"Conteúdo: {conteudo}.")
    if marca:
        linhas.append(f"Marca: {marca}.")
    descricao = " ".join(linhas)

    return {
        "descricao_curta": descricao_curta,
        "descricao": descricao,
        "destaques": "Perfuma o ambiente naturalmente" if aroma else "",
        "modo_de_uso": (
            "Retire a tampa e insira as varetas no frasco. Vire as varetas após "
            "alguns dias para renovar a intensidade do aroma no ambiente."
        ),
    }


MODELOS: dict[str, ModeloDescricao] = {
    "essencias": ModeloDescricao(
        chave="essencias",
        titulo="Essências Via Aroma",
        campos=["nome", "aroma", "conteudo", "marca"],
        gerar=_gerar_essencias,
    ),
    "difusores": ModeloDescricao(
        chave="difusores",
        titulo="Difusores de aromas",
        campos=["nome", "aroma", "conteudo", "marca"],
        gerar=_gerar_difusores,
    ),
}


def listar_modelos() -> list[dict]:
    return [{"chave": m.chave, "titulo": m.titulo, "campos": m.campos} for m in MODELOS.values()]


def gerar_sugestao(chave: str, campos: dict) -> dict:
    modelo = MODELOS.get(chave)
    if not modelo:
        raise KeyError(chave)
    campos_limitados = {k: str(v)[:200] for k, v in (campos or {}).items() if k in modelo.campos}
    return modelo.gerar(campos_limitados)
