"""API administrativa da Central de Atendimento WhatsApp -- todas as rotas
exigem sessão administrativa real (backend.panel_sessions.exigir_perfis,
que também valida Origin/Referer em métodos mutáveis -- proteção CSRF de
defesa em profundidade além do cookie SameSite=Lax). Desde a Central
Multiatendente, perfis adm/supervisor_atendimento/vendedor podem acessar as
rotas de conversa individual (nunca a listagem geral, restrita a
adm/supervisor) -- a autorização fina por conversa é sempre revalidada no
banco por backend.atendimento_repository.exigir_atendente/
autorizado_para_conversa. Nunca aceita chave de API estática aqui (diferente
de outras integrações servidor-a-servidor): esta é uma ferramenta de
atendimento operado por humanos.

Nunca devolve token, app secret, verify token, caminho de disco (media_path)
ou payload bruto do provedor em nenhuma resposta."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from backend.atendimento_flags import atendimento_exige_assuncao_para_admin, atendimento_sellers_habilitado
from backend.atendimento_repository import (
    autorizado_para_conversa,
    exigir_atendente,
    registrar_atividade_atendente,
    registrar_historico_atendimento,
)
from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.idempotency import (
    concluir_chave_idempotente,
    liberar_chave_idempotente,
    reivindicar_chave_idempotente,
)
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_perfis
from backend.rate_limit import limitar_requisicoes
from backend.whatsapp_flags import (
    diagnostico_configuracao_whatsapp_cloud_inbox,
    whatsapp_cloud_inbox_habilitado,
    whatsapp_provider_nome,
    whatsapp_template_language,
)
from backend.whatsapp_inbox_repository import (
    STATUS_CONVERSA_VALIDOS,
    atualizar_conversa,
    atualizar_status_mensagem_enviada,
    linha_conversa_publica,
    linha_mensagem_publica,
    listar_conversas,
    listar_mensagens,
    marcar_conversa_lida,
    obter_conversa,
    registrar_mensagem_enviada,
    vincular_cliente,
    vincular_pedido,
)
from backend.whatsapp_media_service import WhatsAppMediaError, baixar_midia, extensao_para_mime, salvar_midia_local
from backend.whatsapp_provider import ComponenteTemplate, WhatsAppEnvioPermanente, WhatsAppEnvioTransitorio, construir_provider

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/whatsapp", tags=["admin-whatsapp-central-atendimento"])

limitar_envio = limitar_requisicoes("whatsapp_inbox_enviar", limite=30, janela_segundos=60)
limitar_listagem = limitar_requisicoes("whatsapp_inbox_listar", limite=120, janela_segundos=60)

JANELA_ATENDIMENTO_HORAS = 24
TAMANHO_PAGINA_PADRAO = 30
TAMANHO_PAGINA_MAXIMO = 100
LIMITE_MENSAGENS_PADRAO = 50
LIMITE_MENSAGENS_MAXIMO = 200


def _exigir_habilitado() -> None:
    if not whatsapp_cloud_inbox_habilitado():
        raise HTTPException(status_code=503, detail="Central de Atendimento WhatsApp desabilitada ou mal configurada.")


def _sem_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


class AtualizarConversaBody(BaseModel):
    status: str | None = Field(default=None)
    assigned_admin: str | None = Field(default=None, max_length=120)


class EnviarMensagemBody(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    template_name: str | None = Field(default=None, max_length=120)
    template_language: str | None = Field(default=None, max_length=20)
    template_params: list[str] = Field(default_factory=list)
    reply_to_meta_message_id: str | None = Field(default=None, max_length=200)
    assignment_version: int | None = Field(default=None)


class VincularClienteBody(BaseModel):
    customer_id: int


class VincularPedidoBody(BaseModel):
    order_id: int


@router.get("/status")
def status_central_atendimento(response: Response, sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento"))):
    _sem_cache(response)
    diagnostico = diagnostico_configuracao_whatsapp_cloud_inbox()
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        pendentes = conn.execute(
            "SELECT COUNT(*) AS n FROM whatsapp_webhook_events WHERE processing_status='pending'"
        ).fetchone()
        ultimo_evento = conn.execute("SELECT MAX(received_at) AS v FROM whatsapp_webhook_events").fetchone()
        ultimo_sucesso = conn.execute(
            "SELECT MAX(processed_at) AS v FROM whatsapp_webhook_events WHERE processing_status='processed'"
        ).fetchone()
        ultimo_erro = conn.execute(
            "SELECT MAX(processed_at) AS v FROM whatsapp_webhook_events WHERE processing_status='failed'"
        ).fetchone()
    return {
        "ok": True,
        **diagnostico,
        "provider": whatsapp_provider_nome(),
        "pending_events": int(pendentes["n"] if pendentes else 0),
        "last_event_at": ultimo_evento["v"] if ultimo_evento else None,
        "last_success_at": ultimo_sucesso["v"] if ultimo_sucesso else None,
        "last_error_at": ultimo_erro["v"] if ultimo_erro else None,
    }


@router.get("/conversations", dependencies=[Depends(limitar_listagem)])
def rota_listar_conversas(
    response: Response,
    status: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    q: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=TAMANHO_PAGINA_PADRAO, ge=1, le=TAMANHO_PAGINA_MAXIMO),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento")),
):
    """Listagem geral ('Todas' no frontend) -- só adm/supervisor_atendimento.
    Vendedor usa GET /api/admin/whatsapp/queue (fila) e /my-conversations
    (só as próprias) em vez desta rota."""
    _sem_cache(response)
    _exigir_habilitado()
    if status and status not in STATUS_CONVERSA_VALIDOS:
        raise HTTPException(status_code=422, detail="Filtro de status inválido.")
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        linhas, total = listar_conversas(conn, status=status, apenas_nao_lidas=unread_only, busca=q, pagina=page, tamanho_pagina=page_size)
    return {
        "ok": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "conversations": [linha_conversa_publica(row) for row in linhas],
    }


def _obter_conversa_ou_404(conn, conversation_id: int) -> dict:
    conversa = obter_conversa(conn, conversation_id)
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return conversa


def _exigir_atendente_com_acesso(conn, sessao: dict, conversa: dict) -> dict:
    """Combina exigir_atendente (usuário habilitado/ativo/não suspenso) com a
    autorização horizontal por conversa (vendedor só na sua própria -- ver
    backend/atendimento_repository.autorizado_para_conversa). Sempre
    revalidado no banco a cada chamada."""
    usuario = exigir_atendente(conn, sessao)
    if not autorizado_para_conversa(usuario, conversa):
        raise HTTPException(status_code=403, detail="Você não tem acesso a esta conversa.")
    return usuario


@router.get("/conversations/{conversation_id}")
def rota_obter_conversa(
    conversation_id: int,
    response: Response,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        _exigir_atendente_com_acesso(conn, sessao, conversa)
    detalhe = linha_conversa_publica(conversa)
    detalhe["contact"]["phone_last4"] = conversa.get("phone_last4")
    detalhe["assigned_user_id"] = conversa.get("assigned_user_id")
    detalhe["assignment_version"] = conversa.get("assignment_version")
    detalhe["queue_status"] = conversa.get("queue_status")
    return {"ok": True, "conversation": detalhe}


@router.get("/conversations/{conversation_id}/messages")
def rota_listar_mensagens(
    conversation_id: int,
    response: Response,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=LIMITE_MENSAGENS_PADRAO, ge=1, le=LIMITE_MENSAGENS_MAXIMO),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        _exigir_atendente_com_acesso(conn, sessao, conversa)
        linhas = listar_mensagens(conn, conversation_id, antes_de_id=before_id, limite=limit)
    return {"ok": True, "messages": [linha_mensagem_publica(row) for row in linhas]}


@router.post("/conversations/{conversation_id}/messages", dependencies=[Depends(limitar_envio)])
def rota_enviar_mensagem(
    conversation_id: int,
    body: EnviarMensagemBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    escopo_idempotencia = "whatsapp_inbox_send"

    payload_idempotencia = {
        "conversation_id": conversation_id,
        "text": body.text,
        "template_name": body.template_name,
        "reply_to": body.reply_to_meta_message_id,
    }
    resposta_existente = reivindicar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key, payload_idempotencia)
    if resposta_existente is not None:
        return resposta_existente

    try:
        with conectar() as conn:
            conversa = _obter_conversa_ou_404(conn, conversation_id)
            usuario_atendente = exigir_atendente(conn, sessao)
            registrar_atividade_atendente(conn, usuario_atendente.get("id"))
            conn.execute(
                "UPDATE whatsapp_conversations SET last_agent_activity_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), conversation_id),
            )

            # Controle de envio da Central Multiatendente (item 11 da
            # especificação): com a flag desligada, preserva o fluxo legado
            # (só adm, sem exigir assunção -- exigir_atendente já barra
            # qualquer outro perfil quando a flag está desligada). Com a
            # flag ligada, vendedor só responde conversa própria; adm/
            # supervisor só respondem sem assumir quando
            # ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN=false.
            if atendimento_sellers_habilitado():
                exige_assuncao = usuario_atendente.get("perfil") == "vendedor" or atendimento_exige_assuncao_para_admin()
                if exige_assuncao and not autorizado_para_conversa(usuario_atendente, conversa):
                    registrar_historico_atendimento(
                        conn, conversation_id=conversation_id, action="send_denied",
                        performed_by_user_id=usuario_atendente.get("id"),
                        reason="Tentativa de envio sem assumir a conversa.",
                    )
                    conn.commit()
                    liberar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key)
                    raise HTTPException(status_code=403, detail="Assuma esta conversa antes de responder.")
                if (
                    body.assignment_version is not None
                    and int(body.assignment_version) != int(conversa.get("assignment_version") or 0)
                ):
                    liberar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key)
                    raise HTTPException(status_code=409, detail="Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

            destinatario = conversa.get("phone_e164") or conversa.get("wa_id")
            if not destinatario:
                raise HTTPException(status_code=409, detail="Conversa sem destinatário válido.")

            dentro_da_janela = False
            if conversa.get("last_inbound_at"):
                try:
                    ultimo_inbound = datetime.fromisoformat(str(conversa["last_inbound_at"]))
                    dentro_da_janela = (datetime.now() - ultimo_inbound) <= timedelta(hours=JANELA_ATENDIMENTO_HORAS)
                except ValueError:
                    dentro_da_janela = False

            provider = construir_provider(whatsapp_provider_nome())

            if body.template_name:
                mensagem_id = registrar_mensagem_enviada(
                    conn,
                    conversation_id=conversation_id,
                    message_type="template",
                    text_body=None,
                    template_name=body.template_name,
                    sent_by_admin=usuario,
                    reply_to_meta_message_id=body.reply_to_meta_message_id,
                )
                try:
                    resultado = provider.send_template(
                        to=destinatario,
                        template_name=body.template_name,
                        language=body.template_language or whatsapp_template_language(),
                        components=[ComponenteTemplate(texto=p) for p in body.template_params],
                    )
                except (WhatsAppEnvioTransitorio, WhatsAppEnvioPermanente) as exc:
                    atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=None, status="failed", error_code=getattr(exc, "codigo", None), error_message_sanitized="Falha ao enviar template.")
                    registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_template_falhou", usuario, depois={"template_name": body.template_name, "codigo": getattr(exc, "codigo", None)})
                    conn.commit()
                    resposta = {"ok": False, "message_id": mensagem_id, "status": "failed"}
                    concluir_chave_idempotente(conn, escopo_idempotencia, idempotency_key, resposta)
                    conn.commit()
                    return resposta
                atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=resultado.provider_message_id, status="sent" if resultado.ok else "failed")
                registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_template", usuario, depois={"template_name": body.template_name})
                resposta = {"ok": resultado.ok, "message_id": mensagem_id, "status": "sent" if resultado.ok else "failed"}
                concluir_chave_idempotente(conn, escopo_idempotencia, idempotency_key, resposta)
                conn.commit()
                return resposta

            if not body.text or not body.text.strip():
                raise HTTPException(status_code=422, detail="Informe um texto ou selecione um template aprovado.")

            if not dentro_da_janela:
                liberar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key)
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Esta conversa está fora da janela de atendimento de 24h da Meta. "
                        "Envie um template aprovado (campo template_name) em vez de texto livre."
                    ),
                )

            mensagem_id = registrar_mensagem_enviada(
                conn,
                conversation_id=conversation_id,
                message_type="text",
                text_body=body.text,
                template_name=None,
                sent_by_admin=usuario,
                reply_to_meta_message_id=body.reply_to_meta_message_id,
            )
            try:
                resultado = provider.send_inbox_text(to=destinatario, texto=body.text, reply_to_meta_message_id=body.reply_to_meta_message_id)
            except (WhatsAppEnvioTransitorio, WhatsAppEnvioPermanente) as exc:
                atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=None, status="failed", error_code=getattr(exc, "codigo", None), error_message_sanitized="Falha ao enviar mensagem.")
                registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_texto_falhou", usuario)
                conn.commit()
                resposta = {"ok": False, "message_id": mensagem_id, "status": "failed"}
                concluir_chave_idempotente(conn, escopo_idempotencia, idempotency_key, resposta)
                conn.commit()
                return resposta

            atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=resultado.provider_message_id, status="sent" if resultado.ok else "failed")
            registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_texto", usuario)
            resposta = {"ok": resultado.ok, "message_id": mensagem_id, "status": "sent" if resultado.ok else "failed"}
            concluir_chave_idempotente(conn, escopo_idempotencia, idempotency_key, resposta)
            conn.commit()
            return resposta
    except HTTPException:
        liberar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key)
        raise
    except Exception:
        liberar_chave_idempotente(conectar, escopo_idempotencia, idempotency_key)
        logger.exception("whatsapp_inbox_envio_falha_inesperada", extra={"evento": "whatsapp_inbox_envio_falha_inesperada"})
        raise HTTPException(status_code=500, detail="Falha inesperada ao enviar mensagem.")


@router.post("/conversations/{conversation_id}/read")
def rota_marcar_lida(conversation_id: int, sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor"))):
    _exigir_habilitado()
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    with conectar() as conn:
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        _exigir_atendente_com_acesso(conn, sessao, conversa)
        marcar_conversa_lida(conn, conversation_id)
        registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "marcar_lida", usuario)
        conn.commit()
    return {"ok": True}


@router.patch("/conversations/{conversation_id}")
def rota_atualizar_conversa(conversation_id: int, body: AtualizarConversaBody, sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento"))):
    """Edição legada de status/assigned_admin (texto livre) -- só adm/
    supervisor. Vendedor usa claim/release/transfer/resolve/reopen em vez
    desta rota. Mantém queue_status coerente quando o status legado muda
    para/de um estado encerrado."""
    _exigir_habilitado()
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    if body.status and body.status not in STATUS_CONVERSA_VALIDOS:
        raise HTTPException(status_code=422, detail="Status inválido.")
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        try:
            atualizar_conversa(conn, conversation_id, status=body.status, assigned_admin=body.assigned_admin)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        if body.status in ("resolved", "archived") and conversa.get("queue_status") != "resolved":
            conn.execute(
                "UPDATE whatsapp_conversations SET queue_status='resolved', resolved_at=?, resolved_by=?, assignment_version=assignment_version+1 WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), usuario, conversation_id),
            )
        elif body.status in ("open", "pending") and conversa.get("queue_status") == "resolved":
            conn.execute(
                "UPDATE whatsapp_conversations SET queue_status='waiting', resolved_at=NULL, resolved_by=NULL, assignment_version=assignment_version+1 WHERE id=?",
                (conversation_id,),
            )
        registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "atualizar", usuario, depois={"status": body.status, "assigned_admin": body.assigned_admin})
        conn.commit()
    return {"ok": True}


@router.post("/conversations/{conversation_id}/link-customer")
def rota_vincular_cliente(
    conversation_id: int,
    body: VincularClienteBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    with conectar() as conn:
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        _exigir_atendente_com_acesso(conn, sessao, conversa)
        cliente = conn.execute("SELECT id FROM clientes WHERE id=?", (body.customer_id,)).fetchone()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado.")
        vincular_cliente(conn, conversation_id, body.customer_id)
        registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "vincular_cliente", usuario, depois={"customer_id": body.customer_id})
        conn.commit()
    return {"ok": True}


@router.post("/conversations/{conversation_id}/link-order")
def rota_vincular_pedido(
    conversation_id: int,
    body: VincularPedidoBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    with conectar() as conn:
        conversa = _obter_conversa_ou_404(conn, conversation_id)
        _exigir_atendente_com_acesso(conn, sessao, conversa)
        pedido = conn.execute("SELECT id FROM pedidos WHERE id=?", (body.order_id,)).fetchone()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        vincular_pedido(conn, conversation_id, body.order_id)
        registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "vincular_pedido", usuario, depois={"order_id": body.order_id})
        conn.commit()
    return {"ok": True}


@router.get("/media/{message_id}")
def rota_obter_midia(message_id: int, sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor"))):
    _exigir_habilitado()
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM whatsapp_messages WHERE id=?", (message_id,)).fetchone()
        if not linha:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
        mensagem = dict(linha)
        conversa_da_midia = _obter_conversa_ou_404(conn, mensagem["conversation_id"])
        _exigir_atendente_com_acesso(conn, sessao, conversa_da_midia)
        if not mensagem.get("media_id"):
            raise HTTPException(status_code=404, detail="Esta mensagem não possui mídia.")

        if not mensagem.get("media_path"):
            # Reivindicação atômica: só uma requisição concorrente baixa a
            # mesma mídia da Meta. Se outra já está baixando (ou já
            # terminou entre o SELECT acima e este UPDATE), não repetimos o
            # download -- ver migração de whatsapp_messages.media_status.
            claim = conn.execute(
                "UPDATE whatsapp_messages SET media_status='downloading' "
                "WHERE id=? AND media_path IS NULL AND media_status!='downloading'",
                (message_id,),
            )
            conn.commit()
            if claim.rowcount == 0:
                atual = conn.execute("SELECT media_path, media_mime_type, media_status FROM whatsapp_messages WHERE id=?", (message_id,)).fetchone()
                if atual and atual["media_path"]:
                    mensagem["media_path"] = atual["media_path"]
                    mensagem["media_mime_type"] = atual["media_mime_type"]
                else:
                    raise HTTPException(status_code=409, detail="Mídia ainda sendo baixada por outra requisição, tente novamente em instantes.")
            else:
                try:
                    conteudo, extensao, mime_canonico = baixar_midia(mensagem["media_id"])
                except WhatsAppMediaError as exc:
                    conn.execute("UPDATE whatsapp_messages SET media_status='failed' WHERE id=?", (message_id,))
                    conn.commit()
                    raise HTTPException(status_code=502, detail="Não foi possível obter a mídia da Meta no momento.") from exc
                caminho = salvar_midia_local(conteudo, extensao)
                conn.execute(
                    "UPDATE whatsapp_messages SET media_path=?, media_mime_type=?, media_size=?, media_status='available' WHERE id=?",
                    (caminho, mime_canonico, len(conteudo), message_id),
                )
                conn.commit()
                mensagem["media_path"] = caminho
                mensagem["media_mime_type"] = mime_canonico

    try:
        with open(mensagem["media_path"], "rb") as arquivo:
            conteudo_arquivo = arquivo.read()
    except OSError:
        raise HTTPException(status_code=404, detail="Arquivo de mídia não encontrado no armazenamento.")

    mime = mensagem.get("media_mime_type") or "application/octet-stream"
    extensao = extensao_para_mime(mime)
    return Response(
        content=conteudo_arquivo,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="midia-{message_id}.{extensao}"',
            "Content-Length": str(len(conteudo_arquivo)),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/templates")
def rota_listar_templates(response: Response, sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor"))):
    """Lista só os NOMES dos templates configurados para a Central de
    Atendimento (WHATSAPP_INBOX_TEMPLATES, formato `nome:idioma,nome2:idioma2`)
    -- nunca consulta a Graph API em tempo real (evita depender de rede numa
    rota de listagem simples) e nunca inclui nenhum segredo."""
    _sem_cache(response)
    import os

    with conectar() as conn:
        exigir_atendente(conn, sessao)

    bruto = os.environ.get("WHATSAPP_INBOX_TEMPLATES", "").strip()
    templates = []
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        nome, _, idioma = pedaco.partition(":")
        templates.append({"name": nome.strip(), "language": (idioma.strip() or whatsapp_template_language())})
    return {"ok": True, "templates": templates}
