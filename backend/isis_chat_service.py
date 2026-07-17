"""Camadas 7 e 8 — orquestração, limites de custo e observabilidade.

Ponto único que combina sessão + intenção + catálogo + ranqueamento +
provedor de IA (desligado por padrão) para montar a resposta segura
devolvida ao cliente. Nunca expõe SQL, stack trace, prompt interno, dado
privado, custo interno detalhado, tokens, segredos ou campos
administrativos.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime

from backend.isis_chat_catalog import (
    buscar_cursos_ativos,
    buscar_produtos_ativos,
    curso_url,
    produto_url,
)
from backend.isis_chat_flags import chat_recomendacoes_habilitadas, tamanho_maximo_mensagem
from backend.isis_chat_providers import obter_chat_provider
from backend.isis_chat_ranking import comparar_produtos, montar_kit, rankear_produtos
from backend.isis_chat_session import SessaoChat, atualizar_estado_sessao, registrar_mensagem
from backend.logging_config import get_logger

logger = get_logger(__name__)

_LIMITE_RESULTADOS_CONSULTADOS = 100
_INFORMACOES_SENSIVEIS = re.compile(
    r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{11}|\d{4}\s?\d{4}\s?\d{4}\s?\d{4})\b"
)
_PADRAO_IGNORAR_REGRAS = re.compile(
    r"ignor[ea]\s+(as\s+)?(regras|instru[çc][õo]es)|voc[êe]\s+([ée]|agora\s+[ée])\s+livre|esque[çc]a\s+tudo",
    re.IGNORECASE,
)


def sanitizar_entrada(texto: str) -> str:
    """Corta no tamanho máximo configurado e remove caracteres de controle;
    a saída ainda passa por escape no widget antes de qualquer renderização
    HTML (defesa em profundidade, não confia só nesta camada)."""
    limite = tamanho_maximo_mensagem()
    texto = (texto or "")[:limite]
    texto = "".join(ch for ch in texto if ch >= " " or ch in "\n\t")
    return texto.strip()


def contem_tentativa_prompt_injection(texto: str) -> bool:
    return bool(_PADRAO_IGNORAR_REGRAS.search(texto or ""))


def contem_dado_sensivel(texto: str) -> bool:
    return bool(_INFORMACOES_SENSIVEIS.search(texto or ""))


def _registrar_metrica(conn, evento: str, *, intent: str | None = None) -> None:
    conn.execute(
        "INSERT INTO isis_chat_metrics (evento, intent, valor, criado_em) VALUES (?,?,1,?)",
        (evento, intent, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )


def processar_mensagem(conn, sessao: SessaoChat, texto_bruto: str, *, base_url: str = "") -> dict:
    texto = sanitizar_entrada(texto_bruto)

    if contem_tentativa_prompt_injection(texto):
        _registrar_metrica(conn, "prompt_injection_bloqueado")
        logger.info(
            "isis chat: tentativa de prompt injection bloqueada",
            extra={"evento": "isis_chat_prompt_injection", "session_id": sessao.session_id[:8]},
        )
        return _resposta_segura(
            "Não posso ignorar as regras de segurança da Isis. Posso te ajudar a encontrar produtos, "
            "kits ou cursos da Mística -- em que posso ajudar?",
            intent="desconhecida",
            restantes=_restantes(sessao),
        )

    if contem_dado_sensivel(texto):
        _registrar_metrica(conn, "dado_sensivel_orientado")
        return _resposta_segura(
            "Por segurança, não guardo nem repito documentos, dados de cartão ou informações bancárias. "
            "Evite enviar esse tipo de dado por aqui -- posso te ajudar a encontrar produtos, kits ou cursos.",
            intent="desconhecida",
            restantes=_restantes(sessao),
        )

    provider = obter_chat_provider()
    intent_resultado = provider.classify_intent(texto)
    provider.generate_answer(intent_resultado=intent_resultado, contexto={"session_id": sessao.session_id})

    resposta = _montar_resposta(conn, sessao, intent_resultado, base_url=base_url)

    registrar_mensagem(conn, sessao, papel="usuario", intent=intent_resultado.intent, resumo_curto=intent_resultado.termo_busca[:100])
    novo_resumo = provider.summarize_session(sessao.resumo, f"{intent_resultado.intent}:{intent_resultado.termo_busca[:60]}")
    atualizar_estado_sessao(
        conn,
        sessao.session_id,
        intent_atual=intent_resultado.intent,
        resumo=novo_resumo,
        preco_min=intent_resultado.preco_min,
        preco_max=intent_resultado.preco_max,
        produtos_sugeridos=[item["id"] for item in resposta.get("recommendations", [])],
    )
    _registrar_metrica(conn, "mensagem_recebida", intent=intent_resultado.intent)
    if resposta.get("recommendations"):
        _registrar_metrica(conn, "recomendacoes_exibidas", intent=intent_resultado.intent)
    if resposta.get("suggested_kit"):
        _registrar_metrica(conn, "kit_sugerido", intent=intent_resultado.intent)
    if not resposta.get("recommendations") and not resposta.get("suggested_kit") and intent_resultado.intent not in ("saudacao",):
        _registrar_metrica(conn, "fallback_sem_resultado", intent=intent_resultado.intent)

    resposta["remaining_messages"] = _restantes(sessao, incrementado=True)
    return resposta


def _restantes(sessao: SessaoChat, *, incrementado: bool = False) -> int:
    from backend.isis_chat_flags import max_mensagens_por_sessao

    usado = sessao.contador_mensagens + (1 if incrementado else 0)
    return max(0, max_mensagens_por_sessao() - usado)


def _resposta_segura(mensagem: str, *, intent: str, restantes: int) -> dict:
    return {
        "message": mensagem,
        "intent": intent,
        "recommendations": [],
        "complementary_items": [],
        "suggested_kit": None,
        "remaining_messages": restantes,
    }


def _produto_publico(produto: dict, motivo: str, *, base_url: str) -> dict:
    return {
        "id": produto["id"],
        "name": produto["nome"],
        "price": produto["preco"],
        "image_url": produto.get("imagem_url") or "",
        "product_url": produto_url(produto, base_url=base_url),
        "reason": motivo,
    }


def _montar_resposta(conn, sessao: SessaoChat, intent_resultado, *, base_url: str) -> dict:
    intent = intent_resultado.intent

    if intent == "saudacao":
        return _resposta_segura(
            "Olá! Sou a Isis. Posso ajudar você a encontrar produtos, kits e cursos da Mística. "
            "Me conta o que você procura.",
            intent=intent,
            restantes=_restantes(sessao),
        )

    if intent == "buscar_curso":
        cursos = buscar_cursos_ativos(conn, termo=intent_resultado.termo_busca)
        if not cursos:
            return _resposta_segura(
                "Não encontrei nenhum curso ativo correspondente na Escola Mística no momento.",
                intent=intent,
                restantes=_restantes(sessao),
            )
        texto_cursos = "; ".join(f"{c['titulo']}" for c in cursos[:3])
        mensagem = f"Encontrei estes cursos ativos na Escola Mística: {texto_cursos}."
        resposta = _resposta_segura(mensagem, intent=intent, restantes=_restantes(sessao))
        resposta["recommendations"] = [
            {
                "id": None,
                "name": c["titulo"],
                "price": c["preco"],
                "image_url": "",
                "product_url": curso_url(c, base_url=base_url),
                "reason": "Curso ativo da Escola Mística correspondente à sua busca.",
            }
            for c in cursos[:3]
        ]
        return resposta

    if not chat_recomendacoes_habilitadas():
        return _resposta_segura(
            "As recomendações de produto estão temporariamente desativadas nesta homologação. "
            "Posso te ajudar com cursos da Escola Mística.",
            intent=intent,
            restantes=_restantes(sessao),
        )

    # Busca ampla (limitada) no catálogo ativo: o filtro por relevância real
    # acontece no ranqueamento (`rankear_produtos`), que pontua por palavra
    # -- filtrar aqui pela frase inteira do usuário (via LIKE) descartaria
    # produtos relevantes cujo nome/categoria não contém a frase completa.
    produtos = buscar_produtos_ativos(conn, termo="", limite=_LIMITE_RESULTADOS_CONSULTADOS)

    if intent == "comparar_produtos":
        candidatos = rankear_produtos(produtos, termo_busca=intent_resultado.termo_busca, limite=3)
        if len(candidatos) < 2:
            return _resposta_segura(
                "Não consegui confirmar dois produtos correspondentes no catálogo para comparar. "
                "Pode me dizer os nomes exatos?",
                intent=intent,
                restantes=_restantes(sessao),
            )
        comparacao = comparar_produtos([c.produto for c in candidatos[:3]])
        mensagem = "Aqui está a comparação com os dados cadastrados de cada produto."
        resposta = _resposta_segura(mensagem, intent=intent, restantes=_restantes(sessao))
        resposta["recommendations"] = [_produto_publico(c.produto, c.motivo, base_url=base_url) for c in candidatos]
        resposta["comparison"] = comparacao
        return resposta

    if intent == "montar_kit":
        orcamento = intent_resultado.preco_max or 100.0
        candidatos = [p for p in produtos if p.get("disponivel")]
        kit = montar_kit(candidatos, orcamento_max=orcamento)
        if not kit:
            return _resposta_segura(
                f"Não encontrei produtos ativos suficientes para montar um kit dentro de R$ {orcamento:.2f}.",
                intent=intent,
                restantes=_restantes(sessao),
            )
        resposta = _resposta_segura(
            f"Montei uma sugestão de kit totalizando R$ {kit['valor_total']:.2f}, dentro do seu orçamento.",
            intent=intent,
            restantes=_restantes(sessao),
        )
        resposta["suggested_kit"] = {
            "items": [
                {
                    "id": item["id"],
                    "name": item["nome"],
                    "price": item["preco"],
                    "product_url": produto_url(item, base_url=base_url),
                }
                for item in kit["itens"]
            ],
            "total_price": kit["valor_total"],
            "budget": orcamento,
        }
        return resposta

    if intent == "perguntar_disponibilidade":
        candidatos = rankear_produtos(produtos, termo_busca=intent_resultado.termo_busca, limite=1)
        if not candidatos:
            return _resposta_segura(
                "Não consegui confirmar esse produto no catálogo. Pode me dizer o nome exato?",
                intent=intent,
                restantes=_restantes(sessao),
            )
        produto = candidatos[0].produto
        status = "está disponível" if produto["disponivel"] else "não está disponível no momento"
        resposta = _resposta_segura(f"{produto['nome']} {status}, segundo nosso estoque atual.", intent=intent, restantes=_restantes(sessao))
        resposta["recommendations"] = [_produto_publico(produto, candidatos[0].motivo, base_url=base_url)]
        return resposta

    if intent == "perguntar_preco":
        candidatos = rankear_produtos(produtos, termo_busca=intent_resultado.termo_busca, limite=1)
        if not candidatos:
            return _resposta_segura(
                "Não consegui confirmar o preço porque não encontrei esse produto no catálogo ativo.",
                intent=intent,
                restantes=_restantes(sessao),
            )
        produto = candidatos[0].produto
        resposta = _resposta_segura(f"{produto['nome']} custa R$ {produto['preco']:.2f} no catálogo atual.", intent=intent, restantes=_restantes(sessao))
        resposta["recommendations"] = [_produto_publico(produto, candidatos[0].motivo, base_url=base_url)]
        return resposta

    if intent == "perguntar_modo_uso":
        candidatos = rankear_produtos(produtos, termo_busca=intent_resultado.termo_busca, limite=1)
        if not candidatos or not candidatos[0].produto.get("descricao"):
            return _resposta_segura(
                "Não consegui confirmar o modo de uso cadastrado para esse produto. "
                "Você pode conferir a descrição completa na página do produto.",
                intent=intent,
                restantes=_restantes(sessao),
            )
        produto = candidatos[0].produto
        resposta = _resposta_segura(
            f"Sobre {produto['nome']}: {produto['descricao'][:300]}",
            intent=intent,
            restantes=_restantes(sessao),
        )
        resposta["recommendations"] = [_produto_publico(produto, candidatos[0].motivo, base_url=base_url)]
        return resposta

    # buscar_produto, pedir_recomendacao, informar_finalidade, informar_aroma,
    # informar_faixa_preco, produto_complementar -> mesmo fluxo de
    # recomendação ranqueada, variando só a mensagem introdutória.
    principais = rankear_produtos(
        produtos,
        termo_busca=intent_resultado.termo_busca,
        aroma=intent_resultado.aroma,
        finalidade=intent_resultado.finalidade,
        preco_min=intent_resultado.preco_min,
        preco_max=intent_resultado.preco_max,
        limite=3,
    )
    if not principais:
        return _resposta_segura(
            "Não encontrei nenhuma opção correspondente no catálogo ativo agora. "
            "Pode tentar descrever de outra forma ou me contar um orçamento?",
            intent=intent,
            restantes=_restantes(sessao),
        )

    ids_principais = {c.produto["id"] for c in principais}
    complementares_pool = [p for p in produtos if p["id"] not in ids_principais]
    complementares = rankear_produtos(
        complementares_pool,
        termo_busca=intent_resultado.termo_busca,
        aroma=intent_resultado.aroma,
        finalidade=intent_resultado.finalidade,
        limite=3,
    )

    mensagem = "Encontrei algumas opções no nosso catálogo que combinam com o que você procura."
    resposta = _resposta_segura(mensagem, intent=intent, restantes=_restantes(sessao))
    resposta["recommendations"] = [_produto_publico(c.produto, c.motivo, base_url=base_url) for c in principais]
    resposta["complementary_items"] = [_produto_publico(c.produto, c.motivo, base_url=base_url) for c in complementares]
    return resposta
