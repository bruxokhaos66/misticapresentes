"""Orquestrador do Estúdio Inteligente de Conteúdo (Isis 2.0 — Fase 3).

Gera diariamente dois rascunhos (nunca publica): "Bom dia" e "Produto do
dia". Cada chamada é idempotente por dia (`isis_content_jobs.data_referencia`
é UNIQUE) -- reexecutar no mesmo dia sem `forcar=True` devolve o job já
existente em vez de duplicar rascunhos.

Este módulo nunca é acionado por um agendador embutido nesta fase: a
geração diária automática só é implementada quando
`MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED` estiver ligada E algo
externo (cron do provedor de hospedagem, GitHub Actions, etc.) chamar a
rota administrativa correspondente às 08:00 America/Sao_Paulo -- ver
`backend/isis_content_routes.py`. Sem isso, mesmo com a flag ligada, nada
roda por conta própria.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta

from backend.database import conectar
from backend.isis_ai_providers import (
    AIProviderIndisponivelError,
    TextAIProvider,
    obter_image_provider,
    obter_text_provider,
)
from backend.isis_content_flags import content_studio_habilitado, image_generation_habilitado
from backend.isis_content_scoring import selecionar_produto_do_dia
from backend.isis_content_storage import VARIANTES_PERMITIDAS, IsisContentStorageError, salvar_asset
from backend.isis_trend_research import PesquisaTendencias
from backend.logging_config import get_logger

logger = get_logger(__name__)

FRASES_BASE = [
    "Cada amanhecer é um convite silencioso para recomeçar com leveza.",
    "A calma que você procura já habita dentro de você, esperando espaço.",
    "Onde a atenção pousa com carinho, a vida floresce devagar.",
    "Respirar fundo é o primeiro ritual de qualquer dia bem vivido.",
    "A luz da manhã lembra que todo ciclo novo merece um gesto de gratidão.",
    "Ancorar-se no presente é o jeito mais simples de tocar o sagrado.",
    "Um coração em paz encontra sentido até no silêncio mais comum.",
]


class ContentStudioDesativadoError(Exception):
    pass


def _hoje() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def sanitizar_texto(valor: str | None, *, limite: int = 2200) -> str:
    """Remove marcação HTML e normaliza espaços. Todo texto vindo de um
    provedor de IA (ou digitado por um administrador) passa por aqui antes
    de ser persistido -- evita XSS armazenado quando o rascunho é
    renderizado depois no painel administrativo."""
    texto = str(valor or "")
    texto = re.sub(r"<[^>]*>", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:limite]


def _frase_original(indice: int) -> str:
    return FRASES_BASE[indice % len(FRASES_BASE)]


def _gerar_texto_bom_dia(text_provider: TextAIProvider, *, indice_dia: int) -> tuple[dict, str]:
    """Devolve (campos_de_texto, provedor_usado). Nunca copia frases
    conhecidas nem atribui autoria -- a frase é sempre originada do
    template local ou de uma reescrita do provedor de IA, sem citação."""
    frase_local = _frase_original(indice_dia)
    provedor_usado = "template_local"
    frase = frase_local
    try:
        resultado = text_provider.gerar_texto(
            "Reescreva, em português do Brasil, uma frase curta e original de bom dia inspirada no tema a seguir, "
            "sem citar autores nem usar frases célebres conhecidas, com tom espiritual equilibrado e elegante: "
            f"'{frase_local}'"
        )
        if resultado.texto.strip():
            frase = sanitizar_texto(resultado.texto, limite=280)
            provedor_usado = text_provider.nome
    except AIProviderIndisponivelError:
        logger.info("isis_content_texto_fallback", extra={"evento": "isis_content_texto_fallback", "tipo": "bom_dia"})

    legenda = f"{frase}\n\nQue esse dia seja guiado por presença e leveza. 🌙✨"
    legenda_curta = frase if len(frase) <= 140 else frase[:137] + "..."
    hashtags = "#MísticaEsotéricos #BomDia #Espiritualidade #Presença #EnergiaPositiva"
    texto_alternativo = f"Fotografia cinematográfica de natureza em tons profundos com a frase: {frase}"
    prompt_visual = (
        "Fotografia cinematográfica premium, elegante, espiritualidade equilibrada, elementos da natureza, "
        "tons profundos e quentes, luz suave de amanhecer, sem marcas d'água, sem aparência artificial ou de IA genérica, "
        f"composição inspirada no sentimento de: {frase}"
    )
    return (
        {
            "frase_original": frase,
            "legenda": sanitizar_texto(legenda),
            "legenda_curta": sanitizar_texto(legenda_curta, limite=280),
            "hashtags": sanitizar_texto(hashtags, limite=500),
            "texto_alternativo": sanitizar_texto(texto_alternativo, limite=500),
            "prompt_visual": sanitizar_texto(prompt_visual, limite=1000),
        },
        provedor_usado,
    )


def _criar_job(conn, data_referencia: str) -> int:
    agora = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO isis_content_jobs (data_referencia, status, iniciado_em, criado_em) VALUES (?,?,?,?)",
        (data_referencia, "em_andamento", agora, agora),
    )
    return int(cur.lastrowid)


def _job_existente(conn, data_referencia: str) -> dict | None:
    linha = conn.execute("SELECT * FROM isis_content_jobs WHERE data_referencia=?", (data_referencia,)).fetchone()
    return dict(linha) if linha else None


def _inserir_draft(conn, *, job_id: int, data_referencia: str, tipo: str, campos: dict, provedor_texto: str) -> int:
    agora = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO isis_content_drafts (
            job_id, data_referencia, tipo, frase_original, legenda, legenda_curta, hashtags,
            texto_alternativo, prompt_visual, produto_id, produto_codigo, produto_nome, justificativa,
            provedor_texto, status, criado_em, atualizado_em
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job_id,
            data_referencia,
            tipo,
            campos.get("frase_original"),
            campos.get("legenda"),
            campos.get("legenda_curta"),
            campos.get("hashtags"),
            campos.get("texto_alternativo"),
            campos.get("prompt_visual"),
            campos.get("produto_id"),
            campos.get("produto_codigo"),
            campos.get("produto_nome"),
            campos.get("justificativa"),
            provedor_texto,
            "rascunho",
            agora,
            agora,
        ),
    )
    return int(cur.lastrowid)


def _gerar_assets_para_draft(conn, draft_id: int, prompt_visual: str) -> None:
    if not image_generation_habilitado():
        return
    image_provider = obter_image_provider()
    for variante, (largura, altura) in VARIANTES_PERMITIDAS.items():
        try:
            resultado_imagem = image_provider.gerar_imagem(prompt_visual, largura=largura, altura=altura)
            asset = salvar_asset(resultado_imagem.dados, draft_id=draft_id, variante=variante, content_type=resultado_imagem.mime_type)
        except (AIProviderIndisponivelError, IsisContentStorageError) as exc:
            logger.warning(
                "isis_content_asset_falhou",
                extra={"evento": "isis_content_asset_falhou", "draft_id": draft_id, "variante": variante, "erro_tipo": type(exc).__name__},
            )
            continue
        conn.execute(
            """
            INSERT INTO isis_content_assets (draft_id, variante, largura, altura, arquivo, mime_type, tamanho_bytes, hash_sha256, criado_em)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                draft_id,
                variante,
                asset["largura"],
                asset["altura"],
                asset["arquivo"],
                asset["mime_type"],
                asset["tamanho_bytes"],
                asset["hash_sha256"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def _carregar_sinais_produtos(conn, produtos: list[dict]) -> dict[int, dict]:
    desde_vendas = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    sinais: dict[int, dict] = {}
    tendencias = PesquisaTendencias()
    pesos_categoria = tendencias.pesos_por_categoria(conn=conn)
    for produto in produtos:
        produto_id = produto.get("id")
        codigo = produto.get("codigo_p")
        vendas_linha = conn.execute(
            """
            SELECT COUNT(*) AS total FROM vendas_itens vi
            JOIN vendas v ON v.id = vi.venda_id
            WHERE vi.codigo_p=? AND COALESCE(v.data_iso,'') >= ?
            """,
            (codigo, desde_vendas),
        ).fetchone()
        ultima_divulgacao = conn.execute(
            "SELECT MAX(divulgado_em) AS ultima FROM isis_content_product_history WHERE produto_id=?",
            (produto_id,),
        ).fetchone()
        dias_desde_ultima = None
        if ultima_divulgacao and ultima_divulgacao["ultima"]:
            try:
                data_ultima = datetime.fromisoformat(ultima_divulgacao["ultima"])
                dias_desde_ultima = (datetime.now() - data_ultima).days
            except ValueError:
                dias_desde_ultima = None

        preco = float(produto.get("preco") or 0)
        custo = float(produto.get("custo") or 0)
        margem_percentual = ((preco - custo) / preco * 100) if preco > 0 else None

        sinais[produto_id] = {
            "vendas_recentes": int(vendas_linha["total"] or 0),
            "visualizacoes": 0,
            "favoritos": 0,
            "carrinhos": 0,
            "campanhas_anteriores": 0,
            "dias_desde_ultima_divulgacao": dias_desde_ultima,
            "dias_desde_cadastro": None,
            "margem_percentual": margem_percentual,
            "tendencia_categoria": pesos_categoria.get((produto.get("categoria") or "").lower(), 0.0),
        }
    return sinais


def _gerar_draft_produto_do_dia(conn, *, job_id: int, data_referencia: str, text_provider: TextAIProvider) -> int | None:
    produtos = [dict(row) for row in conn.execute("SELECT * FROM produtos").fetchall()]
    sinais = _carregar_sinais_produtos(conn, produtos)
    escolhido = selecionar_produto_do_dia(produtos, sinais)
    if escolhido is None:
        logger.warning("isis_content_sem_produto_elegivel", extra={"evento": "isis_content_sem_produto_elegivel", "data_referencia": data_referencia})
        return None

    produto = escolhido.produto
    justificativa = "; ".join(escolhido.motivos)
    nome_produto = str(produto.get("nome") or "").strip()

    legenda_base = f"Hoje a Mística Esotéricos destaca: {nome_produto}."
    provedor_usado = "template_local"
    try:
        resultado = text_provider.gerar_texto(
            f"Escreva uma legenda curta, elegante e sem inventar preço ou desconto, para divulgar o produto "
            f"'{nome_produto}' de uma loja esotérica premium, tom espiritual equilibrado, sem emojis em excesso."
        )
        if resultado.texto.strip():
            legenda_base = sanitizar_texto(resultado.texto, limite=800)
            provedor_usado = text_provider.nome
    except AIProviderIndisponivelError:
        logger.info("isis_content_texto_fallback", extra={"evento": "isis_content_texto_fallback", "tipo": "produto_do_dia"})

    legenda = f"{legenda_base}\n\nConheça mais na nossa loja. 🌙"
    hashtags = "#MísticaEsotéricos #ProdutoDoDia #Espiritualidade #Ritual"
    texto_alternativo = f"Foto premium do produto {nome_produto}, fotografia cinematográfica, tons profundos, sem marcas d'água."
    prompt_visual = (
        f"Fotografia cinematográfica premium do produto '{nome_produto}', baseada na foto oficial do produto, "
        "elegante, espiritualidade equilibrada, tons profundos, aparência premium, sem marcas d'água, sem aparência artificial."
    )

    campos = {
        "frase_original": None,
        "legenda": sanitizar_texto(legenda),
        "legenda_curta": sanitizar_texto(legenda_base, limite=280),
        "hashtags": sanitizar_texto(hashtags, limite=500),
        "texto_alternativo": sanitizar_texto(texto_alternativo, limite=500),
        "prompt_visual": sanitizar_texto(prompt_visual, limite=1000),
        "produto_id": produto.get("id"),
        "produto_codigo": produto.get("codigo_p"),
        "produto_nome": sanitizar_texto(nome_produto, limite=200),
        "justificativa": sanitizar_texto(justificativa, limite=500),
    }
    draft_id = _inserir_draft(conn, job_id=job_id, data_referencia=data_referencia, tipo="produto_do_dia", campos=campos, provedor_texto=provedor_usado)

    for fonte in ["historico_interno"]:
        conn.execute(
            "INSERT INTO isis_content_sources (draft_id, tipo, descricao, url, confiavel, criado_em) VALUES (?,?,?,?,?,?)",
            (draft_id, "tendencia", f"Sinal interno: {fonte}", None, 1, datetime.now().isoformat(timespec="seconds")),
        )
    conn.execute(
        "INSERT INTO isis_content_product_history (produto_id, draft_id, divulgado_em, motivo) VALUES (?,?,?,?)",
        (produto.get("id"), draft_id, datetime.now().isoformat(timespec="seconds"), justificativa),
    )
    _gerar_assets_para_draft(conn, draft_id, campos["prompt_visual"])
    return draft_id


def _apagar_job_em_cascata(conn, job_id: int) -> None:
    """Remove um job e tudo que depende dele (drafts, assets, fontes,
    aprovações, histórico de produto), nesta ordem, para nunca deixar
    rascunho/asset órfão apontando para um job inexistente -- o SQLite
    aqui não tem `ON DELETE CASCADE` configurado nas FKs existentes, então
    a cascata é feita explicitamente."""
    draft_ids = [row["id"] for row in conn.execute("SELECT id FROM isis_content_drafts WHERE job_id=?", (job_id,)).fetchall()]
    for draft_id in draft_ids:
        conn.execute("DELETE FROM isis_content_assets WHERE draft_id=?", (draft_id,))
        conn.execute("DELETE FROM isis_content_sources WHERE draft_id=?", (draft_id,))
        conn.execute("DELETE FROM isis_content_approvals WHERE draft_id=?", (draft_id,))
        conn.execute("DELETE FROM isis_content_product_history WHERE draft_id=?", (draft_id,))
    conn.execute("DELETE FROM isis_content_drafts WHERE job_id=?", (job_id,))
    conn.execute("DELETE FROM isis_content_jobs WHERE id=?", (job_id,))


def gerar_conteudos_do_dia(data_referencia: str | None = None, *, forcar: bool = False) -> dict:
    """Gera (idempotentemente) os dois rascunhos do dia. Levanta
    `ContentStudioDesativadoError` se `MISTICA_ISIS_CONTENT_STUDIO_ENABLED`
    estiver desligada -- quem chama nunca deve contornar essa checagem.

    Concorrência: `isis_content_jobs.data_referencia` é `UNIQUE`, então duas
    chamadas concorrentes para o mesmo dia (ex.: dois admins clicando "gerar"
    ao mesmo tempo, ou um retry de rede) nunca duplicam o job -- a segunda a
    tentar inserir recebe `IntegrityError` do SQLite, que é tratado abaixo
    reaproveitando o job que a primeira já criou, em vez de vazar um erro
    500 para quem chamou."""
    if not content_studio_habilitado():
        raise ContentStudioDesativadoError("Estúdio de Conteúdo da Isis está desativado.")

    data_referencia = data_referencia or _hoje()
    with conectar() as conn:
        job_atual = _job_existente(conn, data_referencia)
        if job_atual and not forcar:
            drafts = conn.execute("SELECT id, tipo FROM isis_content_drafts WHERE job_id=?", (job_atual["id"],)).fetchall()
            return {"job_id": job_atual["id"], "data_referencia": data_referencia, "reaproveitado": True, "drafts": [dict(d) for d in drafts]}

        if job_atual and forcar:
            _apagar_job_em_cascata(conn, job_atual["id"])

        try:
            job_id = _criar_job(conn, data_referencia)
        except sqlite3.IntegrityError:
            # Outra chamada concorrente já criou o job para este dia entre o
            # SELECT acima e este INSERT -- reaproveita o que ela criou (ou
            # está criando) em vez de propagar o erro de UNIQUE constraint.
            job_existente_da_corrida = _job_existente(conn, data_referencia)
            drafts = conn.execute(
                "SELECT id, tipo FROM isis_content_drafts WHERE job_id=?",
                (job_existente_da_corrida["id"],),
            ).fetchall()
            return {
                "job_id": job_existente_da_corrida["id"],
                "data_referencia": data_referencia,
                "reaproveitado": True,
                "drafts": [dict(d) for d in drafts],
            }

        text_provider = obter_text_provider()
        indice_dia = datetime.now().timetuple().tm_yday

        try:
            campos_bom_dia, provedor_texto = _gerar_texto_bom_dia(text_provider, indice_dia=indice_dia)
            draft_bom_dia_id = _inserir_draft(conn, job_id=job_id, data_referencia=data_referencia, tipo="bom_dia", campos=campos_bom_dia, provedor_texto=provedor_texto)
            _gerar_assets_para_draft(conn, draft_bom_dia_id, campos_bom_dia["prompt_visual"])

            draft_produto_id = _gerar_draft_produto_do_dia(conn, job_id=job_id, data_referencia=data_referencia, text_provider=text_provider)

            conn.execute(
                "UPDATE isis_content_jobs SET status=?, concluido_em=? WHERE id=?",
                ("concluido", datetime.now().isoformat(timespec="seconds"), job_id),
            )
        except Exception as exc:
            conn.execute(
                "UPDATE isis_content_jobs SET status=?, erro=?, concluido_em=? WHERE id=?",
                ("falhou", type(exc).__name__, datetime.now().isoformat(timespec="seconds"), job_id),
            )
            raise

        return {
            "job_id": job_id,
            "data_referencia": data_referencia,
            "reaproveitado": False,
            "drafts": [d for d in [draft_bom_dia_id, draft_produto_id] if d is not None],
        }
