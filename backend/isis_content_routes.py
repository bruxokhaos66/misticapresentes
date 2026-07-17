"""Rotas administrativas do Estúdio de Conteúdo (Isis 2.0 — Fase 3).

Todas as rotas (exceto `GET /status`) exigem sessão de administrador
(`exigir_perfil("adm")`) e checam `content_studio_habilitado()` *antes* de
qualquer leitura/escrita -- com a flag desligada, respondem 404 genérico,
sem side effects, seguindo o mesmo padrão de
`backend.api_security.estorno_rest_habilitado` usado pela rota de estorno.

Nenhuma rota publica em rede social: "publicar" aqui é só
`marcar_publicado_manualmente`, que apenas registra que um administrador
publicou por fora do sistema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.isis_ai_providers import AIProviderIndisponivelError, obter_image_provider, obter_text_provider
from backend.isis_content_flags import resumo_flags, content_studio_habilitado
from backend.isis_content_storage import VARIANTES_PERMITIDAS, IsisContentStorageError, salvar_asset
from backend.isis_content_studio import ContentStudioDesativadoError, gerar_conteudos_do_dia, sanitizar_texto
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_perfil

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/isis-conteudo", tags=["isis-content-studio"])
exigir_admin = exigir_perfil("adm")

STATUS_VALIDOS = {"rascunho", "aprovado", "rejeitado", "publicado"}
HASHTAGS_MAX = 500
LEGENDA_MAX = 2200


def _bloquear_se_desativado() -> None:
    if not content_studio_habilitado():
        raise HTTPException(status_code=404, detail="Não encontrado.")


class DraftEdicaoIn(BaseModel):
    legenda: Optional[str] = Field(default=None, max_length=LEGENDA_MAX)
    legenda_curta: Optional[str] = Field(default=None, max_length=280)
    hashtags: Optional[str] = Field(default=None, max_length=HASHTAGS_MAX)
    texto_alternativo: Optional[str] = Field(default=None, max_length=500)


class RejeicaoIn(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class GeracaoDiariaIn(BaseModel):
    data_referencia: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    forcar: bool = False


def _draft_ou_404(conn, draft_id: int) -> dict:
    linha = conn.execute("SELECT * FROM isis_content_drafts WHERE id=?", (draft_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Rascunho não encontrado.")
    return dict(linha)


def _usuario(sessao: dict) -> str:
    return str(sessao.get("login") or sessao.get("nome") or "adm")


@router.get("/status")
def status_estudio(sessao: dict = Depends(exigir_admin)):
    return resumo_flags()


@router.get("/drafts")
def listar_drafts(
    data_referencia: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    status: Optional[str] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    sessao: dict = Depends(exigir_admin),
):
    _bloquear_se_desativado()
    condicoes, parametros = [], []
    if data_referencia:
        condicoes.append("data_referencia=?")
        parametros.append(data_referencia)
    if status:
        if status not in STATUS_VALIDOS:
            raise HTTPException(status_code=400, detail="Status inválido.")
        condicoes.append("status=?")
        parametros.append(status)
    if tipo:
        if tipo not in {"bom_dia", "produto_do_dia"}:
            raise HTTPException(status_code=400, detail="Tipo inválido.")
        condicoes.append("tipo=?")
        parametros.append(tipo)
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    with conectar() as conn:
        linhas = conn.execute(
            f"SELECT * FROM isis_content_drafts {where} ORDER BY data_referencia DESC, id DESC LIMIT 200",
            tuple(parametros),
        ).fetchall()
        drafts = [dict(linha) for linha in linhas]
        for draft in drafts:
            assets = conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft["id"],)).fetchall()
            draft["assets"] = [dict(a) for a in assets]
    return {"drafts": drafts, "total": len(drafts)}


@router.get("/drafts/{draft_id}")
def obter_draft(draft_id: int, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        draft["assets"] = [dict(a) for a in conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft_id,)).fetchall()]
        draft["fontes"] = [dict(f) for f in conn.execute("SELECT * FROM isis_content_sources WHERE draft_id=?", (draft_id,)).fetchall()]
    return draft


@router.put("/drafts/{draft_id}")
def editar_draft(draft_id: int, payload: DraftEdicaoIn, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] != "rascunho":
            raise HTTPException(status_code=409, detail="Só é possível editar enquanto o conteúdo estiver em rascunho.")

        campos, valores = [], []
        for campo, limite in (("legenda", LEGENDA_MAX), ("legenda_curta", 280), ("hashtags", HASHTAGS_MAX), ("texto_alternativo", 500)):
            valor = getattr(payload, campo)
            if valor is not None:
                campos.append(f"{campo}=?")
                valores.append(sanitizar_texto(valor, limite=limite))
        if not campos:
            raise HTTPException(status_code=400, detail="Nenhum campo informado.")
        valores.append(datetime.now().isoformat(timespec="seconds"))
        campos.append("atualizado_em=?")
        valores.append(draft_id)
        conn.execute(f"UPDATE isis_content_drafts SET {', '.join(campos)} WHERE id=?", tuple(valores))
        registrar_auditoria(conn, "isis_content_draft", draft_id, "editar", _usuario(sessao), antes=draft)
    return {"ok": True}


@router.post("/drafts/{draft_id}/regenerar-texto")
def regenerar_texto(draft_id: int, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    text_provider = obter_text_provider()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] != "rascunho":
            raise HTTPException(status_code=409, detail="Só é possível regenerar enquanto o conteúdo estiver em rascunho.")
        base = draft.get("frase_original") or draft.get("produto_nome") or "conteúdo da Mística Esotéricos"
        try:
            resultado = text_provider.gerar_texto(
                f"Reescreva de forma original, elegante e sem citar autores, uma legenda de Instagram sobre: {base}"
            )
        except AIProviderIndisponivelError as exc:
            raise HTTPException(status_code=503, detail="Provedor de IA de texto indisponível agora. Tente novamente em instantes.") from exc
        nova_legenda = sanitizar_texto(resultado.texto, limite=LEGENDA_MAX) or draft["legenda"]
        conn.execute(
            "UPDATE isis_content_drafts SET legenda=?, provedor_texto=?, atualizado_em=? WHERE id=?",
            (nova_legenda, text_provider.nome, datetime.now().isoformat(timespec="seconds"), draft_id),
        )
        registrar_auditoria(conn, "isis_content_draft", draft_id, "regenerar_texto", _usuario(sessao))
    return {"ok": True, "legenda": nova_legenda}


@router.post("/drafts/{draft_id}/regenerar-imagem")
def regenerar_imagem(draft_id: int, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] != "rascunho":
            raise HTTPException(status_code=409, detail="Só é possível regenerar enquanto o conteúdo estiver em rascunho.")
    from backend.isis_content_flags import image_generation_habilitado

    if not image_generation_habilitado():
        raise HTTPException(status_code=409, detail="Geração de imagem está desativada (MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED).")

    image_provider = obter_image_provider()
    novos_assets = []
    with conectar() as conn:
        conn.execute("DELETE FROM isis_content_assets WHERE draft_id=?", (draft_id,))
        for variante, (largura, altura) in VARIANTES_PERMITIDAS.items():
            try:
                resultado_imagem = image_provider.gerar_imagem(draft["prompt_visual"] or "", largura=largura, altura=altura)
                asset = salvar_asset(resultado_imagem.dados, draft_id=draft_id, variante=variante, content_type=resultado_imagem.mime_type)
            except (AIProviderIndisponivelError, IsisContentStorageError) as exc:
                raise HTTPException(status_code=503, detail="Provedor de IA de imagem indisponível agora. Tente novamente em instantes.") from exc
            conn.execute(
                """
                INSERT INTO isis_content_assets (draft_id, variante, largura, altura, arquivo, mime_type, tamanho_bytes, hash_sha256, criado_em)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (draft_id, variante, asset["largura"], asset["altura"], asset["arquivo"], asset["mime_type"], asset["tamanho_bytes"], asset["hash_sha256"], datetime.now().isoformat(timespec="seconds")),
            )
            novos_assets.append(asset)
        registrar_auditoria(conn, "isis_content_draft", draft_id, "regenerar_imagem", _usuario(sessao))
    return {"ok": True, "assets": novos_assets}


@router.post("/drafts/{draft_id}/aprovar")
def aprovar_draft(draft_id: int, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] != "rascunho":
            raise HTTPException(status_code=409, detail="Só é possível aprovar um conteúdo em rascunho.")
        agora = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE isis_content_drafts SET status='aprovado', aprovado_por=?, aprovado_em=?, atualizado_em=? WHERE id=?",
            (_usuario(sessao), agora, agora, draft_id),
        )
        conn.execute(
            "INSERT INTO isis_content_approvals (draft_id, acao, usuario, criado_em) VALUES (?,?,?,?)",
            (draft_id, "aprovar", _usuario(sessao), agora),
        )
        registrar_auditoria(conn, "isis_content_draft", draft_id, "aprovar", _usuario(sessao))
    return {"ok": True}


@router.post("/drafts/{draft_id}/rejeitar")
def rejeitar_draft(draft_id: int, payload: RejeicaoIn, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] not in {"rascunho", "aprovado"}:
            raise HTTPException(status_code=409, detail="Este conteúdo não pode mais ser rejeitado.")
        agora = datetime.now().isoformat(timespec="seconds")
        motivo = sanitizar_texto(payload.motivo, limite=500)
        conn.execute(
            "UPDATE isis_content_drafts SET status='rejeitado', rejeitado_por=?, rejeitado_em=?, motivo_rejeicao=?, atualizado_em=? WHERE id=?",
            (_usuario(sessao), agora, motivo, agora, draft_id),
        )
        conn.execute(
            "INSERT INTO isis_content_approvals (draft_id, acao, usuario, detalhe, criado_em) VALUES (?,?,?,?,?)",
            (draft_id, "rejeitar", _usuario(sessao), motivo, agora),
        )
        registrar_auditoria(conn, "isis_content_draft", draft_id, "rejeitar", _usuario(sessao), depois={"motivo": motivo})
    return {"ok": True}


@router.post("/drafts/{draft_id}/publicar-manual")
def marcar_publicado_manualmente(draft_id: int, sessao: dict = Depends(exigir_admin)):
    """Registra que um administrador publicou este conteúdo por fora do
    sistema (Instagram, etc.) -- esta rota nunca chama nenhuma API de rede
    social; é só um registro manual, exigido pelo fluxo de aprovação."""
    _bloquear_se_desativado()
    with conectar() as conn:
        draft = _draft_ou_404(conn, draft_id)
        if draft["status"] != "aprovado":
            raise HTTPException(status_code=409, detail="Só é possível marcar como publicado um conteúdo já aprovado.")
        agora = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE isis_content_drafts SET status='publicado', publicado_por=?, publicado_em=?, atualizado_em=? WHERE id=?",
            (_usuario(sessao), agora, agora, draft_id),
        )
        conn.execute(
            "INSERT INTO isis_content_approvals (draft_id, acao, usuario, criado_em) VALUES (?,?,?,?)",
            (draft_id, "publicado_manual", _usuario(sessao), agora),
        )
        registrar_auditoria(conn, "isis_content_draft", draft_id, "publicar_manual", _usuario(sessao))
    return {"ok": True}


@router.get("/drafts/{draft_id}/assets/{asset_id}/download")
def baixar_asset(draft_id: int, asset_id: int, sessao: dict = Depends(exigir_admin)):
    _bloquear_se_desativado()
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM isis_content_assets WHERE id=? AND draft_id=?", (asset_id, draft_id)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    asset = dict(linha)
    return {"url": asset["arquivo"], "mime_type": asset["mime_type"], "hash_sha256": asset["hash_sha256"]}


@router.post("/gerar-diario")
def gerar_diario(payload: GeracaoDiariaIn, sessao: dict = Depends(exigir_admin)):
    """Aciona manualmente a geração dos dois rascunhos do dia. Não publica
    nada -- só cria/reaproveita os rascunhos. Sem acionamento externo (cron
    fora deste processo), esta rota é o único jeito de gerar conteúdo,
    mesmo com `MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED` ligada."""
    _bloquear_se_desativado()
    try:
        resultado = gerar_conteudos_do_dia(payload.data_referencia, forcar=payload.forcar)
    except ContentStudioDesativadoError as exc:
        raise HTTPException(status_code=404, detail="Não encontrado.") from exc
    with conectar() as conn:
        registrar_auditoria(conn, "isis_content_job", resultado.get("job_id"), "gerar_diario", _usuario(sessao), depois=resultado)
    return resultado
