"""Download seguro de mídia recebida via WhatsApp Cloud API, sob demanda
(nunca automático no recebimento do webhook -- só quando um administrador
autenticado abre a mídia no painel, ver backend/whatsapp_inbox_routes.py).

Regras (Fase 6 da Central de Atendimento):
- o token de acesso (WHATSAPP_ACCESS_TOKEN) nunca é exposto ao navegador --
  toda chamada à Graph API/CDN de mídia acontece aqui, no backend;
- timeout explícito, sem seguir redirect para fora do domínio da Meta;
- limite de tamanho aplicado ENQUANTO baixa (streaming), nunca só depois;
- validação por magic bytes -- o mime_type informado pela Meta nunca é
  aceito sozinho;
- allowlist fechada de tipos (imagens JPEG/PNG/WebP, PDF, áudio e vídeo
  compatíveis com WhatsApp) -- SVG, HTML, JavaScript e executáveis são
  sempre rejeitados;
- nome de arquivo sempre gerado pelo servidor (uuid4 + extensão derivada do
  mime validado) -- nunca o nome/extensão informado pela Meta ou pelo
  cliente, o que também elimina path traversal e extensão dupla maliciosa.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.logging_config import get_logger
from backend.whatsapp_flags import (
    whatsapp_access_token,
    whatsapp_graph_api_version,
    whatsapp_media_max_bytes,
    whatsapp_media_storage_dir,
    whatsapp_request_timeout_seconds,
)

logger = get_logger(__name__)


class WhatsAppMediaError(Exception):
    def __init__(self, mensagem: str, *, codigo: str = "media_error"):
        super().__init__(mensagem)
        self.codigo = codigo


# (assinatura de magic bytes, extensão, mime canônico) -- checada nesta
# ordem; a primeira que bater com o início do arquivo define o tipo real,
# independentemente do mime_type declarado pela Meta.
_ASSINATURAS: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"RIFF", "webp", "image/webp"),  # confirmado abaixo pelos bytes 8-12 == 'WEBP'
    (b"%PDF-", "pdf", "application/pdf"),
    (b"OggS", "ogg", "audio/ogg"),
    (b"ID3", "mp3", "audio/mpeg"),
    (b"\xff\xfb", "mp3", "audio/mpeg"),
]

_MIME_FTYP = {
    b"ftypmp42": ("mp4", "video/mp4"),
    b"ftypisom": ("mp4", "video/mp4"),
    b"ftypM4A ": ("m4a", "audio/mp4"),
    b"ftyp3gp5": ("3gp", "video/3gpp"),
}

# Domínios oficiais da Meta usados pela Graph API/CDN de mídia do WhatsApp
# Cloud API. A URL temporária devolvida pelos metadados só é seguida se o
# host bater com um destes (exato ou subdomínio) -- nunca seguimos redirect
# nem baixamos de um host arbitrário injetado numa resposta adulterada.
_DOMINIOS_MIDIA_PERMITIDOS = ("fbcdn.net", "fbsbx.com", "facebook.com", "whatsapp.net")


def extensao_para_mime(mime_type: str | None) -> str:
    """Extensão de arquivo segura para um mime canônico já validado por
    magic bytes -- usada só para nomear o download (Content-Disposition),
    nunca para decidir o tipo real do conteúdo."""
    mapa = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "application/pdf": "pdf",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "video/mp4": "mp4",
        "audio/mp4": "m4a",
        "video/3gpp": "3gp",
    }
    return mapa.get((mime_type or "").lower(), "bin")


def _host_permitido(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    return any(host == dominio or host.endswith("." + dominio) for dominio in _DOMINIOS_MIDIA_PERMITIDOS)


def _identificar_por_magic_bytes(cabecalho: bytes) -> tuple[str, str] | None:
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return "webp", "image/webp"
    for assinatura, extensao, mime in _ASSINATURAS:
        if assinatura != b"RIFF" and cabecalho.startswith(assinatura):
            return extensao, mime
    if len(cabecalho) >= 12:
        caixa = cabecalho[4:12]
        if caixa in _MIME_FTYP:
            return _MIME_FTYP[caixa]
    return None


def _diretorio_destino() -> Path:
    caminho = Path(whatsapp_media_storage_dir())
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def _cliente_http() -> httpx.Client:
    token = whatsapp_access_token()
    if not token:
        raise WhatsAppMediaError("WhatsApp Cloud API sem token configurado.", codigo="missing_configuration")
    return httpx.Client(
        timeout=whatsapp_request_timeout_seconds(),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "MisticaPresentes-WhatsAppInbox/1.0"},
        follow_redirects=False,
    )


def baixar_midia(media_id: str) -> tuple[bytes, str, str]:
    """Baixa a mídia identificada por `media_id` da Meta. Retorna
    (conteudo, extensao, mime_canonico). Levanta WhatsAppMediaError em
    qualquer falha (configuração ausente, tipo não permitido, tamanho
    excedido, resposta inesperada) -- nunca retorna dado parcial."""
    if not media_id:
        raise WhatsAppMediaError("media_id ausente.", codigo="missing_media_id")

    limite = whatsapp_media_max_bytes()
    versao = whatsapp_graph_api_version()

    with _cliente_http() as cliente:
        try:
            meta_resposta = cliente.get(f"https://graph.facebook.com/{versao}/{media_id}")
        except httpx.HTTPError as exc:
            raise WhatsAppMediaError(f"Falha ao consultar metadados da mídia: {type(exc).__name__}", codigo="metadata_request_failed") from exc
        if meta_resposta.status_code != 200:
            raise WhatsAppMediaError(f"Metadados da mídia indisponíveis (http {meta_resposta.status_code}).", codigo="metadata_unavailable")

        try:
            dados_meta = meta_resposta.json()
        except ValueError as exc:
            raise WhatsAppMediaError("Resposta de metadados da mídia não é JSON válido.", codigo="metadata_invalid") from exc
        url_arquivo = str(dados_meta.get("url") or "")
        tamanho_informado = int(dados_meta.get("file_size") or 0)
        if not url_arquivo.lower().startswith("https://"):
            raise WhatsAppMediaError("URL de mídia inválida (não-HTTPS).", codigo="invalid_media_url")
        if not _host_permitido(url_arquivo):
            raise WhatsAppMediaError("URL de mídia fora dos domínios permitidos da Meta.", codigo="invalid_media_domain")
        if tamanho_informado and tamanho_informado > limite:
            raise WhatsAppMediaError("Mídia excede o tamanho máximo permitido.", codigo="media_too_large")

        try:
            with cliente.stream("GET", url_arquivo) as resposta_arquivo:
                if resposta_arquivo.is_redirect:
                    destino = resposta_arquivo.headers.get("location", "")
                    if not _host_permitido(destino):
                        raise WhatsAppMediaError("Redirecionamento de mídia para domínio não permitido.", codigo="invalid_redirect_domain")
                    raise WhatsAppMediaError("Redirecionamento de mídia não suportado.", codigo="unsupported_redirect")
                if resposta_arquivo.status_code != 200:
                    raise WhatsAppMediaError(f"Download da mídia falhou (http {resposta_arquivo.status_code}).", codigo="download_failed")
                content_type_recebido = (resposta_arquivo.headers.get("content-type") or "").split(";")[0].strip().lower()
                pedacos = bytearray()
                for pedaco in resposta_arquivo.iter_bytes():
                    pedacos.extend(pedaco)
                    if len(pedacos) > limite:
                        raise WhatsAppMediaError("Mídia excede o tamanho máximo permitido durante o download.", codigo="media_too_large")
        except httpx.HTTPError as exc:
            raise WhatsAppMediaError(f"Falha de rede ao baixar mídia: {type(exc).__name__}", codigo="download_network_error") from exc

    if not pedacos:
        raise WhatsAppMediaError("Mídia baixada está vazia.", codigo="empty_media")

    conteudo = bytes(pedacos)
    identificado = _identificar_por_magic_bytes(conteudo[:64])
    if not identificado:
        raise WhatsAppMediaError("Tipo de arquivo não reconhecido/permitido (magic bytes).", codigo="unsupported_media_type")
    extensao, mime_canonico = identificado
    if content_type_recebido and not content_type_recebido.startswith(mime_canonico.split("/")[0]):
        logger.warning(
            "whatsapp_media_content_type_divergente",
            extra={"evento": "whatsapp_media_content_type_divergente", "detectado": mime_canonico},
        )
    return conteudo, extensao, mime_canonico


# ---------------------------------------------------------------------------
# Validação de mídia ENVIADA pelo painel (compose da Central de Atendimento
# -- item 8 da especificação de envio avançado). Distinto da validação de
# mídia RECEBIDA acima: aqui a allowlist é fechada por finalidade
# (media_kind="image"|"audio"), sempre por magic bytes -- o content_type
# declarado pelo navegador NUNCA é aceito sozinho. Imagem passa ainda pelo
# Pillow (Image.open(...).verify()) em backend/whatsapp_inbox_routes.py, a
# defesa adicional contra bytes que só imitam o cabeçalho magic mas não são
# uma imagem genuína (SVG/HTML/JS disfarçados nunca passam nas duas
# checagens juntas).
# ---------------------------------------------------------------------------

_ASSINATURAS_IMAGEM_SAIDA: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
]

# EBML (WebM), OggS (Ogg) e o box `ftyp` de MP4/M4A -- os formatos que o
# MediaRecorder do navegador tipicamente produz, mais mp3/wav por
# compatibilidade com upload manual de um áudio já gravado.
_ASSINATURAS_AUDIO_SAIDA: list[tuple[bytes, str, str]] = [
    (b"\x1a\x45\xdf\xa3", "webm", "audio/webm"),
    (b"OggS", "ogg", "audio/ogg"),
    (b"ID3", "mp3", "audio/mpeg"),
    (b"\xff\xfb", "mp3", "audio/mpeg"),
    (b"\xff\xf3", "mp3", "audio/mpeg"),
    (b"\xff\xf2", "mp3", "audio/mpeg"),
]


def identificar_imagem_saida(cabecalho: bytes) -> tuple[str, str] | None:
    """Identifica JPEG/PNG/WEBP reais pelos magic bytes -- allowlist fechada
    para mídia de SAÍDA (envio pelo painel). Nunca aceita SVG, HTML,
    JavaScript ou qualquer outro tipo, mesmo que o navegador declare
    ``image/*`` no content-type."""
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return "webp", "image/webp"
    for assinatura, extensao, mime in _ASSINATURAS_IMAGEM_SAIDA:
        if cabecalho.startswith(assinatura):
            return extensao, mime
    return None


def identificar_audio_saida(cabecalho: bytes) -> tuple[str, str] | None:
    """Identifica webm/ogg/mp3/mp4(m4a)/wav reais pelos magic bytes --
    allowlist fechada para áudio/nota de voz enviado pelo painel."""
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WAVE":
        return "wav", "audio/wav"
    if len(cabecalho) >= 12 and cabecalho[4:8] == b"ftyp":
        return "m4a", "audio/mp4"
    for assinatura, extensao, mime in _ASSINATURAS_AUDIO_SAIDA:
        if cabecalho.startswith(assinatura):
            return extensao, mime
    return None


def salvar_midia_local(conteudo: bytes, extensao: str) -> str:
    """Grava o conteúdo com um nome gerado pelo servidor (uuid4 -- nunca
    derivado de entrada do cliente/Meta), sempre dentro do diretório
    configurado (sem possibilidade de path traversal, já que nem diretório
    nem nome vêm de fora). Escreve num arquivo temporário no mesmo
    diretório, dá fsync e só então renomeia atomicamente para o nome final
    -- assim um leitor concorrente nunca vê um arquivo parcialmente
    escrito, e uma falha no meio da escrita nunca deixa um arquivo corrompido
    com o nome definitivo."""
    destino = _diretorio_destino()
    nome_arquivo = f"{uuid.uuid4().hex}.{extensao}"
    caminho = destino / nome_arquivo
    caminho_temp = destino / f".tmp-{uuid.uuid4().hex}"
    try:
        with open(caminho_temp, "wb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.chmod(caminho_temp, 0o600)
        os.replace(caminho_temp, caminho)
    finally:
        if caminho_temp.exists():
            try:
                caminho_temp.unlink()
            except OSError:
                pass
    return str(caminho)
