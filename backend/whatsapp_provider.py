"""Abstração de provedor de WhatsApp para notificações administrativas.

Só a API oficial WhatsApp Business Platform / Cloud API (Meta) é usada em
produção (MetaWhatsAppCloudProvider). Nenhuma automação de WhatsApp Web,
Selenium, navegador controlado, link `wa.me` ou API não-oficial é
implementada aqui ou em qualquer outro módulo desta integração.

A interface WhatsAppProvider existe para permitir trocar de provedor (ex.:
um BSP terceirizado que também fale a Cloud API) sem reescrever nenhuma
regra de negócio em backend/whatsapp_outbox.py ou backend/whatsapp_worker.py
-- ambos dependem só desta interface, nunca de um provedor concreto.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx

from backend.logging_config import get_logger
from backend.whatsapp_flags import (
    whatsapp_access_token,
    whatsapp_app_secret,
    whatsapp_graph_api_version,
    whatsapp_phone_number_id,
    whatsapp_request_timeout_seconds,
)

logger = get_logger(__name__)

# Tamanho máximo aceito para o corpo de uma resposta da Graph API -- nunca
# tentamos fazer parsing de uma resposta arbitrariamente grande (proteção
# contra resposta inesperada/hostil de um proxy comprometido no meio do
# caminho, mesmo com TLS).
_LIMITE_RESPOSTA_BYTES = 1_000_000


class WhatsAppEnvioTransitorio(Exception):
    """Falha temporária (timeout, conexão, 429, 5xx) -- deve ser
    reprocessada com backoff, nunca marcada como falha permanente."""

    def __init__(self, mensagem: str, *, retry_after_seconds: Optional[float] = None, codigo: str = "transient_error"):
        super().__init__(mensagem)
        self.retry_after_seconds = retry_after_seconds
        self.codigo = codigo


class WhatsAppEnvioPermanente(Exception):
    """Falha permanente (template inexistente/rejeitado, número inválido,
    token inválido, permissão ausente, payload inválido, configuração
    incompleta) -- nunca deve ser reprocessada automaticamente."""

    def __init__(self, mensagem: str, *, codigo: str = "permanent_error"):
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass(frozen=True)
class ResultadoEnvioWhatsApp:
    ok: bool
    provider_message_id: Optional[str] = None
    status: str = "sent"


@dataclass(frozen=True)
class StatusEntregaWhatsApp:
    provider_message_id: str
    status: str  # sent | delivered | read | failed
    timestamp: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


@dataclass(frozen=True)
class ComponenteTemplate:
    """Um parâmetro de corpo do template (texto), na ordem em que aparece no
    template aprovado. Nunca contém PII além do estritamente necessário
    (ver backend/whatsapp_events.py -- quem monta os componentes decide o
    que entra aqui)."""

    texto: str


class WhatsAppProvider(ABC):
    nome: str = "abstract"

    @abstractmethod
    def send_template(
        self,
        *,
        to: str,
        template_name: str,
        language: str,
        components: list[ComponenteTemplate] = (),
    ) -> ResultadoEnvioWhatsApp:
        """Envia uma mensagem de template aprovado. Levanta
        WhatsAppEnvioTransitorio ou WhatsAppEnvioPermanente em caso de erro
        -- nunca retorna um resultado ok=True para uma falha."""
        raise NotImplementedError

    def send_text(self, *, to: str, texto: str) -> ResultadoEnvioWhatsApp:
        """Mensagem de texto livre -- só permitida oficialmente dentro da
        janela de atendimento de 24h com uma conversa iniciada pelo cliente.
        Como as notificações administrativas deste sistema podem ocorrer a
        qualquer momento (fora dessa janela), o fluxo de produção usa
        exclusivamente send_template; este método existe apenas para
        completude da interface e não é chamado pelo worker."""
        raise WhatsAppEnvioPermanente(
            "send_text não é usado pelo fluxo de notificações administrativas (fora da janela de 24h, exige template aprovado).",
            codigo="text_not_supported",
        )

    def send_inbox_text(self, *, to: str, texto: str, reply_to_meta_message_id: str | None = None) -> ResultadoEnvioWhatsApp:
        """Resposta de texto livre de um ADMINISTRADOR pela Central de
        Atendimento -- só é permitida pela Meta dentro da janela de 24h de
        uma conversa iniciada pelo cliente (backend/whatsapp_inbox_routes.py
        é quem decide, a partir de whatsapp_conversations.last_inbound_at, se
        deve chamar isto ou exigir um template). Distinto de send_text
        (reservado ao fluxo de notificações administrativas, que nunca deve
        usar texto livre)."""
        raise WhatsAppEnvioPermanente("send_inbox_text não suportado por este provedor.", codigo="text_not_supported")

    @abstractmethod
    def parse_delivery_webhook(self, payload: dict) -> list[StatusEntregaWhatsApp]:
        raise NotImplementedError

    @abstractmethod
    def validate_webhook_signature(self, payload_bruto: bytes, headers: dict) -> bool:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> dict:
        raise NotImplementedError


class DisabledWhatsAppProvider(WhatsAppProvider):
    """Provedor nulo -- permite desenvolvimento/testes sem nenhuma chamada
    externa. Usado sempre que WHATSAPP_NOTIFICATIONS_ENABLED=false ou a
    configuração está incompleta (ver backend/whatsapp_flags.py::
    whatsapp_habilitado). Nunca levanta exceção: o chamador (worker) trata o
    retorno como "não enviado, desabilitado", nunca como erro."""

    nome = "disabled"

    def send_template(self, *, to: str, template_name: str, language: str, components: list[ComponenteTemplate] = ()) -> ResultadoEnvioWhatsApp:
        return ResultadoEnvioWhatsApp(ok=False, status="skipped_disabled")

    def send_inbox_text(self, *, to: str, texto: str, reply_to_meta_message_id: str | None = None) -> ResultadoEnvioWhatsApp:
        return ResultadoEnvioWhatsApp(ok=False, status="skipped_disabled")

    def parse_delivery_webhook(self, payload: dict) -> list[StatusEntregaWhatsApp]:
        return []

    def validate_webhook_signature(self, payload_bruto: bytes, headers: dict) -> bool:
        return False

    def healthcheck(self) -> dict:
        return {"provider": self.nome, "ok": False, "reason": "disabled"}


class MetaWhatsAppCloudProvider(WhatsAppProvider):
    """WhatsApp Business Platform / Cloud API oficial da Meta.

    Endpoint: POST https://graph.facebook.com/{version}/{phone_number_id}/messages
    Autenticação: Bearer <WHATSAPP_ACCESS_TOKEN> (System User Token de longa
    duração, gerado no painel da Meta -- nunca o token de usuário de teste de
    24h em produção).
    Formato de envio: mensagem de template (`type: template`), a única forma
    suportada oficialmente para notificações fora da janela de atendimento
    de 24h.

    IMPORTANTE: confirme sempre a versão atual recomendada da Graph API, o
    formato de payload e as regras de janela de atendimento na documentação
    oficial (developers.facebook.com/docs/whatsapp/cloud-api) antes de
    ativar em produção -- ver docs/admin/WHATSAPP_NOTIFICACOES.md."""

    nome = "meta_cloud"

    def _base_url(self) -> str:
        versao = whatsapp_graph_api_version()
        phone_id = whatsapp_phone_number_id()
        return f"https://graph.facebook.com/{versao}/{phone_id}"

    def _cliente(self) -> httpx.Client:
        token = whatsapp_access_token()
        if not token or not whatsapp_phone_number_id():
            raise WhatsAppEnvioPermanente("WhatsApp Cloud API sem credenciais configuradas.", codigo="missing_configuration")
        return httpx.Client(
            timeout=whatsapp_request_timeout_seconds(),
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "MisticaPresentes-WhatsAppNotifications/1.0",
                "Content-Type": "application/json",
            },
            # Nunca segue redirects: a URL de destino é sempre fixa
            # (domínio oficial graph.facebook.com), um redirect inesperado é
            # tratado como resposta suspeita, não seguido silenciosamente.
            follow_redirects=False,
        )

    def send_template(self, *, to: str, template_name: str, language: str, components: list[ComponenteTemplate] = ()) -> ResultadoEnvioWhatsApp:
        if not template_name:
            raise WhatsAppEnvioPermanente("Nome de template ausente.", codigo="missing_template")
        if not to:
            raise WhatsAppEnvioPermanente("Destinatário ausente.", codigo="missing_recipient")

        corpo = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language or "pt_BR"},
            },
        }
        if components:
            corpo["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": comp.texto} for comp in components],
                }
            ]

        try:
            with self._cliente() as cliente:
                resposta = cliente.post(f"{self._base_url()}/messages", json=corpo)
        except httpx.TimeoutException as exc:
            raise WhatsAppEnvioTransitorio("Timeout ao chamar a Graph API.", codigo="timeout") from exc
        except httpx.TransportError as exc:
            raise WhatsAppEnvioTransitorio("Falha de conexão com a Graph API.", codigo="connection_error") from exc

        return self._interpretar_resposta(resposta)

    def send_inbox_text(self, *, to: str, texto: str, reply_to_meta_message_id: str | None = None) -> ResultadoEnvioWhatsApp:
        if not to:
            raise WhatsAppEnvioPermanente("Destinatário ausente.", codigo="missing_recipient")
        texto_limpo = str(texto or "").strip()
        if not texto_limpo:
            raise WhatsAppEnvioPermanente("Texto vazio.", codigo="empty_text")
        if len(texto_limpo) > 4096:
            raise WhatsAppEnvioPermanente("Texto excede o limite de 4096 caracteres da Cloud API.", codigo="text_too_long")

        corpo = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": texto_limpo, "preview_url": False},
        }
        if reply_to_meta_message_id:
            corpo["context"] = {"message_id": reply_to_meta_message_id}

        try:
            with self._cliente() as cliente:
                resposta = cliente.post(f"{self._base_url()}/messages", json=corpo)
        except httpx.TimeoutException as exc:
            raise WhatsAppEnvioTransitorio("Timeout ao chamar a Graph API.", codigo="timeout") from exc
        except httpx.TransportError as exc:
            raise WhatsAppEnvioTransitorio("Falha de conexão com a Graph API.", codigo="connection_error") from exc

        return self._interpretar_resposta(resposta)

    def _interpretar_resposta(self, resposta: httpx.Response) -> ResultadoEnvioWhatsApp:
        conteudo = resposta.content[:_LIMITE_RESPOSTA_BYTES]
        try:
            corpo_resposta = json.loads(conteudo or b"{}")
        except ValueError:
            corpo_resposta = {}

        if resposta.status_code == 200:
            mensagens = corpo_resposta.get("messages") or []
            msg_id = str(mensagens[0].get("id")) if mensagens and mensagens[0].get("id") else None
            return ResultadoEnvioWhatsApp(ok=True, provider_message_id=msg_id, status="sent")

        erro = corpo_resposta.get("error") or {}
        codigo_erro = erro.get("code")
        subcodigo = erro.get("error_subcode")
        # Nunca loga/propaga error_user_msg ou message inteiros para fora
        # deste módulo em texto livre não sanitizado -- o chamador
        # (whatsapp_worker.py) só recebe o resumo truncado abaixo.
        resumo = f"http_{resposta.status_code}_code_{codigo_erro}_sub_{subcodigo}"

        if resposta.status_code == 429:
            retry_after = resposta.headers.get("Retry-After")
            raise WhatsAppEnvioTransitorio(resumo, retry_after_seconds=float(retry_after) if retry_after and retry_after.isdigit() else None, codigo="rate_limited")
        if resposta.status_code in (500, 502, 503, 504):
            raise WhatsAppEnvioTransitorio(resumo, codigo=f"http_{resposta.status_code}")
        if resposta.status_code == 401:
            raise WhatsAppEnvioPermanente(resumo, codigo="invalid_token")
        if resposta.status_code == 403:
            raise WhatsAppEnvioPermanente(resumo, codigo="permission_denied")
        # 400/404/param inválido/template rejeitado -- tratado como
        # permanente por padrão (nunca reprocessa um payload inválido
        # indefinidamente); alguns subcódigos específicos de template
        # "pausado/limite temporário" poderiam ser transitórios -- ver nota
        # em docs/admin/WHATSAPP_NOTIFICACOES.md para revisão operacional
        # quando a conta estiver ativa.
        raise WhatsAppEnvioPermanente(resumo, codigo=f"http_{resposta.status_code}")

    def parse_delivery_webhook(self, payload: dict) -> list[StatusEntregaWhatsApp]:
        """Extrai os `statuses` de um payload de webhook da Cloud API
        (`entry[].changes[].value.statuses[]`). Ignora qualquer formato
        desconhecido com segurança (retorna lista vazia), nunca levanta
        exceção para um payload inesperado."""
        resultados: list[StatusEntregaWhatsApp] = []
        try:
            for entrada in payload.get("entry") or []:
                for mudanca in entrada.get("changes") or []:
                    valor = mudanca.get("value") or {}
                    for status in valor.get("statuses") or []:
                        msg_id = str(status.get("id") or "").strip()
                        status_nome = str(status.get("status") or "").strip().lower()
                        if not msg_id or status_nome not in {"sent", "delivered", "read", "failed"}:
                            continue
                        erros = status.get("errors") or []
                        primeiro_erro = erros[0] if erros else {}
                        resultados.append(
                            StatusEntregaWhatsApp(
                                provider_message_id=msg_id,
                                status=status_nome,
                                timestamp=str(status.get("timestamp") or "") or None,
                                error_code=str(primeiro_erro.get("code")) if primeiro_erro.get("code") is not None else None,
                                error_summary=(str(primeiro_erro.get("title") or "")[:200] or None),
                            )
                        )
        except (AttributeError, TypeError):
            return []
        return resultados

    def validate_webhook_signature(self, payload_bruto: bytes, headers: dict) -> bool:
        """Segue o algoritmo documentado pela Meta para webhooks da
        plataforma (Graph API Webhooks -- "Validating Payloads"):
        X-Hub-Signature-256: sha256=<HMAC-SHA256(corpo_bruto, app_secret)>,
        comparado em tempo constante."""
        segredo = whatsapp_app_secret()
        if not segredo:
            return False
        cabecalhos = {str(k).lower(): v for k, v in (headers or {}).items()}
        assinatura = str(cabecalhos.get("x-hub-signature-256", ""))
        if not assinatura.startswith("sha256="):
            return False
        assinatura_recebida = assinatura[len("sha256="):].strip()
        esperado = hmac.new(segredo.encode("utf-8"), payload_bruto or b"", hashlib.sha256).hexdigest()
        return hmac.compare_digest(esperado, assinatura_recebida)

    def healthcheck(self) -> dict:
        token = whatsapp_access_token()
        phone_id = whatsapp_phone_number_id()
        if not token or not phone_id:
            return {"provider": self.nome, "ok": False, "reason": "missing_configuration"}
        try:
            with self._cliente() as cliente:
                resposta = cliente.get(f"{self._base_url()}", params={"fields": "id"})
        except httpx.HTTPError as exc:
            return {"provider": self.nome, "ok": False, "reason": f"request_failed:{type(exc).__name__}"}
        return {"provider": self.nome, "ok": resposta.status_code == 200, "http_status": resposta.status_code}


def construir_provider(nome_provider: str) -> WhatsAppProvider:
    """Fábrica única do provedor efetivo -- nunca instancia o provedor Meta
    diretamente fora daqui, para que trocar de provedor no futuro (ex.: um
    novo BSP) seja uma mudança de configuração, não de código chamador."""
    if nome_provider == "meta_cloud":
        return MetaWhatsAppCloudProvider()
    return DisabledWhatsAppProvider()
