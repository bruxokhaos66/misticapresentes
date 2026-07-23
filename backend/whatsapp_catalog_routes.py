"""Catálogo Comercial na Central de Atendimento WhatsApp (PR #408) --
pesquisa de produtos reais e envio comercial (imagem + nome + preço + link)
pelo WhatsApp. Mesmo padrão de segurança de
backend/whatsapp_inbox_routes.py: toda rota exige sessão administrativa real
(backend.panel_sessions.exigir_perfis) e revalida no banco, a cada chamada,
se o usuário pode operar a Central (backend.atendimento_repository.
exigir_atendente) e se tem acesso à conversa (autorizado_para_conversa).

Com ATENDIMENTO_CATALOG_ENABLED=false (padrão), toda rota deste módulo
devolve 503 e nenhuma chamada extra de catálogo deve ocorrer no frontend."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from backend.atendimento_repository import autorizado_para_conversa, exigir_atendente
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
from backend.whatsapp_catalog_flags import (
    atendimento_catalog_habilitado,
    atendimento_catalog_max_produtos_por_envio,
)
from backend.whatsapp_catalog_repository import (
    PAGE_SIZE_MAXIMO,
    PAGE_SIZE_PADRAO,
    RECENTES_LIMITE_MAXIMO,
    RECENTES_LIMITE_PADRAO,
    RegistroEnvioProduto,
    buscar_produtos_catalogo,
    listar_produtos_recentes,
    montar_texto_comercial,
    obter_produto_catalogo,
    registrar_envio_produto,
)
from backend.whatsapp_flags import whatsapp_cloud_inbox_habilitado
from backend.whatsapp_inbox_repository import (
    atualizar_status_mensagem_enviada,
    obter_conversa,
    registrar_mensagem_enviada,
)
from backend.whatsapp_provider import WhatsAppEnvioPermanente, WhatsAppEnvioTransitorio, construir_provider
from backend.whatsapp_flags import whatsapp_provider_nome

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/whatsapp", tags=["admin-whatsapp-catalogo-comercial"])

limitar_busca = limitar_requisicoes("whatsapp_catalog_busca", limite=60, janela_segundos=60)
limitar_envio_produto = limitar_requisicoes("whatsapp_catalog_enviar", limite=30, janela_segundos=60)

JANELA_ATENDIMENTO_HORAS = 24
IDS_MAXIMO_POR_LOTE_ABSOLUTO = 10


def _exigir_habilitado() -> None:
    if not whatsapp_cloud_inbox_habilitado() or not atendimento_catalog_habilitado():
        raise HTTPException(status_code=503, detail="Catálogo Comercial da Central de Atendimento desabilitado.")


def _sem_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _base_url(request: Request) -> str:
    """Domínio público usado para montar o link do produto -- sempre um
    domínio da nossa allowlist (nunca o Host informado pela requisição),
    mesmo padrão de backend/isis_chat_routes.py::_base_url."""
    from backend.api_security import ORIGENS_PERMITIDAS

    origem = request.headers.get("origin") or ""
    if origem in ORIGENS_PERMITIDAS:
        return origem
    return ORIGENS_PERMITIDAS[0] if ORIGENS_PERMITIDAS else ""


def _obter_conversa_ou_404(conn, conversation_id: int) -> dict:
    conversa = obter_conversa(conn, conversation_id)
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return conversa


def _exigir_atendente_com_acesso(conn, sessao: dict, conversa: dict) -> dict:
    usuario = exigir_atendente(conn, sessao)
    if not autorizado_para_conversa(usuario, conversa):
        raise HTTPException(status_code=403, detail="Você não tem acesso a esta conversa.")
    return usuario


def _dentro_da_janela_atendimento(conversa: dict) -> bool:
    if not conversa.get("last_inbound_at"):
        return False
    try:
        ultimo_inbound = datetime.fromisoformat(str(conversa["last_inbound_at"]))
    except ValueError:
        return False
    return (datetime.now() - ultimo_inbound) <= timedelta(hours=JANELA_ATENDIMENTO_HORAS)


def _hash_chave(chave: str | None) -> str | None:
    if not chave:
        return None
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


@router.get("/catalog/products")
def rota_buscar_produtos(
    response: Response,
    q: str = Query(default="", max_length=160),
    categoria: str | None = Query(default=None, max_length=100),
    marca: str | None = Query(default=None, max_length=100),
    ativo: bool = Query(default=True),
    em_estoque: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=PAGE_SIZE_PADRAO, ge=1, le=PAGE_SIZE_MAXIMO),
    request: Request = None,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
    _rl=Depends(limitar_busca),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        produtos, total = buscar_produtos_catalogo(
            conn,
            base_url=_base_url(request),
            q=q,
            categoria=categoria,
            marca=marca,
            apenas_ativos=ativo,
            apenas_em_estoque=em_estoque,
            page=page,
            page_size=page_size,
        )
    return {"ok": True, "total": total, "page": page, "page_size": page_size, "products": produtos}


@router.get("/catalog/recent-products")
def rota_produtos_recentes(
    response: Response,
    limit: int = Query(default=RECENTES_LIMITE_PADRAO, ge=1, le=RECENTES_LIMITE_MAXIMO),
    request: Request = None,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        produtos = listar_produtos_recentes(conn, usuario_id=usuario["id"], base_url=_base_url(request), limite=limit)
    return {"ok": True, "products": produtos}


class EnviarProdutoBody(BaseModel):
    product_id: int = Field(gt=0)
    assignment_version: int | None = None


class EnviarProdutosBody(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=IDS_MAXIMO_POR_LOTE_ABSOLUTO)
    assignment_version: int | None = None

    @field_validator("product_ids")
    @classmethod
    def _ids_unicos_e_positivos(cls, valores: list[int]) -> list[int]:
        vistos: set[int] = set()
        for valor in valores:
            if valor <= 0:
                raise ValueError("IDs de produto devem ser positivos.")
            if valor in vistos:
                raise ValueError("IDs de produto duplicados no lote.")
            vistos.add(valor)
        return valores


def _validar_produto_para_envio(conn, produto_id: int, *, base_url: str) -> dict:
    """Busca o produto de novo pelo ID (nunca confia em nome/preço/imagem/
    estoque/URL vindos do frontend -- item 9) e valida que pode ser enviado
    agora. Levanta HTTPException se o produto não existir ou estiver
    indisponível -- por padrão o envio de produto indisponível é bloqueado
    (item 9, 'prefira bloquear nesta PR')."""
    produto = obter_produto_catalogo(conn, produto_id, base_url=base_url)
    if not produto:
        raise HTTPException(status_code=404, detail=f"Produto {produto_id} não encontrado.")
    if not produto["ativo"]:
        raise HTTPException(status_code=422, detail=f"Produto {produto_id} está inativo.")
    if not produto["disponivel"]:
        raise HTTPException(status_code=409, detail=f"Produto {produto_id} está indisponível no momento.")
    if not produto["url_publica"]:
        raise HTTPException(status_code=422, detail=f"Produto {produto_id} sem link público válido.")
    return produto


def _enviar_produto_via_provider(provider, *, destinatario: str, produto: dict) -> tuple[bool, str | None]:
    texto = montar_texto_comercial(produto)
    if produto.get("imagem_url"):
        try:
            resultado = provider.send_inbox_image(to=destinatario, image_url=produto["imagem_url"], caption=texto)
        except (WhatsAppEnvioTransitorio, WhatsAppEnvioPermanente):
            # Nunca bloqueia o envio de texto por falta/erro de imagem
            # (item 8 -- 'não bloquear o envio de texto quando a imagem
            # estiver ausente'); tenta o texto puro como alternativa.
            resultado = provider.send_inbox_text(to=destinatario, texto=texto)
    else:
        resultado = provider.send_inbox_text(to=destinatario, texto=texto)
    return resultado.ok, ("sent" if resultado.ok else "failed")


@router.post("/conversations/{conversation_id}/send-product", dependencies=[Depends(limitar_envio_produto)])
def rota_enviar_produto(
    conversation_id: int,
    body: EnviarProdutoBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    usuario_nome = str(sessao.get("nome") or sessao.get("login") or "Admin")
    escopo = "whatsapp_catalog_send_product"
    payload_idempotencia = {"conversation_id": conversation_id, "product_id": body.product_id}

    resposta_existente = reivindicar_chave_idempotente(conectar, escopo, idempotency_key, payload_idempotencia)
    if resposta_existente is not None:
        return resposta_existente

    try:
        with conectar() as conn:
            conversa = _obter_conversa_ou_404(conn, conversation_id)
            usuario = _exigir_atendente_com_acesso(conn, sessao, conversa)

            if (
                body.assignment_version is not None
                and int(body.assignment_version) != int(conversa.get("assignment_version") or 0)
            ):
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise HTTPException(status_code=409, detail="Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

            destinatario = conversa.get("phone_e164") or conversa.get("wa_id")
            if not destinatario:
                raise HTTPException(status_code=409, detail="Conversa sem destinatário válido.")
            if not _dentro_da_janela_atendimento(conversa):
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise HTTPException(
                    status_code=422,
                    detail="Esta conversa está fora da janela de atendimento de 24h da Meta.",
                )

            try:
                produto = _validar_produto_para_envio(conn, body.product_id, base_url=_base_url(request))
            except HTTPException as exc:
                registrar_envio_produto(
                    conn,
                    RegistroEnvioProduto(
                        conversation_id=conversation_id,
                        product_id=body.product_id,
                        message_id=None,
                        performed_by_user_id=usuario.get("id"),
                        action="unavailable_product_blocked",
                        price_at_send=0.0,
                        status="blocked",
                        idempotency_key_hash=_hash_chave(idempotency_key),
                    ),
                )
                conn.commit()
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise exc

            provider = construir_provider(whatsapp_provider_nome())
            texto = montar_texto_comercial(produto)
            mensagem_id = registrar_mensagem_enviada(
                conn,
                conversation_id=conversation_id,
                message_type="product",
                text_body=texto,
                template_name=None,
                sent_by_admin=usuario_nome,
            )

            try:
                ok, status = _enviar_produto_via_provider(provider, destinatario=destinatario, produto=produto)
            except (WhatsAppEnvioTransitorio, WhatsAppEnvioPermanente) as exc:
                atualizar_status_mensagem_enviada(
                    conn, mensagem_id, meta_message_id=None, status="failed",
                    error_code=getattr(exc, "codigo", None), error_message_sanitized="Falha ao enviar produto.",
                )
                registrar_envio_produto(
                    conn,
                    RegistroEnvioProduto(
                        conversation_id=conversation_id, product_id=produto["id"], message_id=mensagem_id,
                        performed_by_user_id=usuario.get("id"), action="product_send_failed",
                        price_at_send=produto["preco"], status="failed",
                        idempotency_key_hash=_hash_chave(idempotency_key),
                    ),
                )
                registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_produto_falhou", usuario_nome, depois={"product_id": produto["id"]})
                conn.commit()
                resposta = {"ok": False, "message_id": mensagem_id, "status": "failed", "product_id": produto["id"]}
                concluir_chave_idempotente(conn, escopo, idempotency_key, resposta)
                conn.commit()
                return resposta

            atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=None, status="sent" if ok else "failed")
            registrar_envio_produto(
                conn,
                RegistroEnvioProduto(
                    conversation_id=conversation_id, product_id=produto["id"], message_id=mensagem_id,
                    performed_by_user_id=usuario.get("id"), action="product_sent",
                    price_at_send=produto["preco"], status=status,
                    idempotency_key_hash=_hash_chave(idempotency_key),
                ),
            )
            registrar_auditoria(conn, "whatsapp_conversation", conversation_id, "enviar_produto", usuario_nome, depois={"product_id": produto["id"], "preco": produto["preco"]})
            conn.execute(
                "UPDATE whatsapp_conversations SET last_agent_activity_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), conversation_id),
            )
            resposta = {"ok": ok, "message_id": mensagem_id, "status": status, "product_id": produto["id"]}
            concluir_chave_idempotente(conn, escopo, idempotency_key, resposta)
            conn.commit()
            return resposta
    except HTTPException:
        liberar_chave_idempotente(conectar, escopo, idempotency_key)
        raise
    except Exception:
        liberar_chave_idempotente(conectar, escopo, idempotency_key)
        logger.exception("whatsapp_catalog_envio_falha_inesperada", extra={"evento": "whatsapp_catalog_envio_falha_inesperada"})
        raise HTTPException(status_code=500, detail="Falha inesperada ao enviar produto.")


@router.post("/conversations/{conversation_id}/send-products", dependencies=[Depends(limitar_envio_produto)])
def rota_enviar_produtos(
    conversation_id: int,
    body: EnviarProdutosBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    usuario_nome = str(sessao.get("nome") or sessao.get("login") or "Admin")
    escopo = "whatsapp_catalog_send_products_batch"
    payload_idempotencia = {"conversation_id": conversation_id, "product_ids": body.product_ids}

    limite_lote = atendimento_catalog_max_produtos_por_envio()
    if len(body.product_ids) > limite_lote:
        raise HTTPException(status_code=422, detail=f"No máximo {limite_lote} produtos por envio em lote.")

    resposta_existente = reivindicar_chave_idempotente(conectar, escopo, idempotency_key, payload_idempotencia)
    if resposta_existente is not None:
        return resposta_existente

    try:
        with conectar() as conn:
            conversa = _obter_conversa_ou_404(conn, conversation_id)
            usuario = _exigir_atendente_com_acesso(conn, sessao, conversa)

            if (
                body.assignment_version is not None
                and int(body.assignment_version) != int(conversa.get("assignment_version") or 0)
            ):
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise HTTPException(status_code=409, detail="Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

            destinatario = conversa.get("phone_e164") or conversa.get("wa_id")
            if not destinatario:
                raise HTTPException(status_code=409, detail="Conversa sem destinatário válido.")
            if not _dentro_da_janela_atendimento(conversa):
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise HTTPException(status_code=422, detail="Esta conversa está fora da janela de atendimento de 24h da Meta.")

            base_url = _base_url(request)
            # Falha total antes de iniciar qualquer chamada externa: todo
            # produto do lote é revalidado no backend antes do primeiro
            # envio (item 10 -- nunca deixa metade enviada por erro de
            # validação de outro item do mesmo lote).
            try:
                produtos = [_validar_produto_para_envio(conn, pid, base_url=base_url) for pid in body.product_ids]
            except HTTPException as exc:
                liberar_chave_idempotente(conectar, escopo, idempotency_key)
                raise exc

            provider = construir_provider(whatsapp_provider_nome())
            resultados = []
            for produto in produtos:
                texto = montar_texto_comercial(produto)
                mensagem_id = registrar_mensagem_enviada(
                    conn, conversation_id=conversation_id, message_type="product",
                    text_body=texto, template_name=None, sent_by_admin=usuario_nome,
                )
                try:
                    ok, status = _enviar_produto_via_provider(provider, destinatario=destinatario, produto=produto)
                except (WhatsAppEnvioTransitorio, WhatsAppEnvioPermanente) as exc:
                    ok, status = False, "failed"
                    atualizar_status_mensagem_enviada(
                        conn, mensagem_id, meta_message_id=None, status="failed",
                        error_code=getattr(exc, "codigo", None), error_message_sanitized="Falha ao enviar produto.",
                    )
                else:
                    atualizar_status_mensagem_enviada(conn, mensagem_id, meta_message_id=None, status="sent" if ok else "failed")

                registrar_envio_produto(
                    conn,
                    RegistroEnvioProduto(
                        conversation_id=conversation_id, product_id=produto["id"], message_id=mensagem_id,
                        performed_by_user_id=usuario.get("id"), action="product_batch_sent",
                        price_at_send=produto["preco"], status=status,
                        idempotency_key_hash=_hash_chave(idempotency_key),
                    ),
                )
                resultados.append({"product_id": produto["id"], "message_id": mensagem_id, "ok": ok, "status": status})

            registrar_auditoria(
                conn, "whatsapp_conversation", conversation_id, "enviar_produtos_lote", usuario_nome,
                depois={"product_ids": [p["id"] for p in produtos]},
            )
            conn.execute(
                "UPDATE whatsapp_conversations SET last_agent_activity_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), conversation_id),
            )
            resposta = {"ok": all(r["ok"] for r in resultados), "results": resultados}
            concluir_chave_idempotente(conn, escopo, idempotency_key, resposta)
            conn.commit()
            return resposta
    except HTTPException:
        liberar_chave_idempotente(conectar, escopo, idempotency_key)
        raise
    except Exception:
        liberar_chave_idempotente(conectar, escopo, idempotency_key)
        logger.exception("whatsapp_catalog_envio_lote_falha_inesperada", extra={"evento": "whatsapp_catalog_envio_lote_falha_inesperada"})
        raise HTTPException(status_code=500, detail="Falha inesperada ao enviar produtos.")
