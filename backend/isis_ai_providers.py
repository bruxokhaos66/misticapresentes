"""Interfaces de provedor de IA para o Estúdio de Conteúdo (Isis 2.0 — Fase 3).

Contratos estáveis (`TextAIProvider`, `ImageAIProvider`, `TrendResearchProvider`)
para que o provedor concreto seja trocável sem alterar o orquestrador
(`backend.isis_content_studio`). A implementação inicial é OpenAI, mas
nenhuma chave de API é exposta ao frontend -- toda chamada acontece aqui,
no backend, e só quando as feature flags do estúdio (ver
`backend.isis_content_flags`) estiverem ligadas.

Disciplina aplicada a qualquer provedor concreto:
- timeout curto e explícito por chamada (`ISIS_CONTENT_AI_TIMEOUT_SECONDS`);
- número limitado de tentativas (`ISIS_CONTENT_AI_MAX_RETRIES`), sem retry
  em erros de validação/autenticação (só em timeout/5xx/instabilidade);
- orçamento diário (`ISIS_CONTENT_AI_DAILY_BUDGET_USD`) verificado *antes*
  de qualquer chamada de rede -- ver `orcamento_diario_disponivel`;
- todo consumo é registrado em `isis_content_ai_usage` (custo estimado,
  não o conteúdo gerado);
- logs nunca incluem o prompt nem a resposta -- só metadados (provedor,
  tipo, duração, sucesso/falha, classe do erro).
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from backend.database import conectar
from backend.logging_config import get_logger

logger = get_logger(__name__)


class AIProviderIndisponivelError(Exception):
    """Falha operacional (timeout, indisponibilidade, orçamento esgotado).

    Quem chama deve tratar esta exceção como "não gerar agora" -- nunca
    deve inventar conteúdo de fallback silencioso que pareça gerado com
    sucesso."""


class OrcamentoDiarioExcedidoError(AIProviderIndisponivelError):
    pass


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


TIMEOUT_SEGUNDOS = _env_float("ISIS_CONTENT_AI_TIMEOUT_SECONDS", 20.0)
MAX_TENTATIVAS = max(1, _env_int("ISIS_CONTENT_AI_MAX_RETRIES", 2))
ORCAMENTO_DIARIO_USD = _env_float("ISIS_CONTENT_AI_DAILY_BUDGET_USD", 2.0)


def _hoje() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def custo_consumido_hoje() -> float:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT COALESCE(SUM(custo_estimado), 0) AS total FROM isis_content_ai_usage WHERE data_referencia=?",
            (_hoje(),),
        ).fetchone()
    return float(linha["total"] or 0.0)


def orcamento_diario_disponivel(custo_estimado_chamada: float = 0.0) -> bool:
    if ORCAMENTO_DIARIO_USD <= 0:
        return False
    return (custo_consumido_hoje() + max(0.0, custo_estimado_chamada)) <= ORCAMENTO_DIARIO_USD


def registrar_consumo(*, provedor: str, tipo: str, custo_estimado: float, unidades: float = 0.0, sucesso: bool = True) -> None:
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO isis_content_ai_usage (data_referencia, provedor, tipo, custo_estimado, unidades, sucesso, criado_em)
            VALUES (?,?,?,?,?,?,?)
            """,
            (_hoje(), provedor, tipo, max(0.0, custo_estimado), unidades, 1 if sucesso else 0, datetime.now().isoformat(timespec="seconds")),
        )


def _com_retry(nome_operacao: str, provedor: str, chamada):
    """Executa `chamada()` com timeout implícito (o provedor concreto deve
    respeitar `TIMEOUT_SEGUNDOS` internamente) e retry limitado. Erros de
    configuração (`ValueError`) nunca são reprocessados -- só falhas de
    rede/indisponibilidade, sinalizadas como `AIProviderIndisponivelError`
    ou `TimeoutError` pelo provedor concreto."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        inicio = time.monotonic()
        try:
            resultado = chamada()
            logger.info(
                "isis_content_ai_chamada_ok",
                extra={
                    "evento": "isis_content_ai_chamada",
                    "provedor": provedor,
                    "operacao": nome_operacao,
                    "tentativa": tentativa,
                    "duracao_ms": int((time.monotonic() - inicio) * 1000),
                },
            )
            return resultado
        except ValueError:
            raise
        except Exception as exc:  # timeout, indisponibilidade, erro de rede
            ultimo_erro = exc
            logger.warning(
                "isis_content_ai_chamada_falhou",
                extra={
                    "evento": "isis_content_ai_chamada",
                    "provedor": provedor,
                    "operacao": nome_operacao,
                    "tentativa": tentativa,
                    "erro_tipo": type(exc).__name__,
                    "duracao_ms": int((time.monotonic() - inicio) * 1000),
                },
            )
    raise AIProviderIndisponivelError(f"{provedor}.{nome_operacao} indisponível após {MAX_TENTATIVAS} tentativa(s)") from ultimo_erro


@dataclass(frozen=True)
class TextGenerationResult:
    texto: str
    custo_estimado: float = 0.0
    unidades: float = 0.0


@dataclass(frozen=True)
class ImageGenerationResult:
    dados: bytes
    mime_type: str
    custo_estimado: float = 0.0


class TextAIProvider(ABC):
    nome: str = "base"

    @abstractmethod
    def gerar_texto(self, prompt: str, *, contexto: dict | None = None) -> TextGenerationResult:
        ...


class ImageAIProvider(ABC):
    nome: str = "base"

    @abstractmethod
    def gerar_imagem(self, prompt: str, *, largura: int, altura: int) -> ImageGenerationResult:
        ...


class TrendResearchProvider(ABC):
    """Ver `backend.isis_trend_research` para a camada desacoplada completa
    (múltiplos provedores combinados). Esta interface é o contrato mínimo
    que cada fonte de tendência individual deve implementar."""

    nome: str = "base"
    confiavel: bool = False

    @abstractmethod
    def pesquisar(self, *, categorias: list[str] | None = None) -> list[dict]:
        ...


class NullTextProvider(TextAIProvider):
    """Provedor padrão (sem chamada de rede): nunca deve ser usado para
    gerar o conteúdo final publicável, só como sinal de indisponibilidade
    explícita quando nenhuma chave de IA está configurada."""

    nome = "null"

    def gerar_texto(self, prompt: str, *, contexto: dict | None = None) -> TextGenerationResult:
        raise AIProviderIndisponivelError("Nenhum TextAIProvider configurado (defina OPENAI_API_KEY).")


class NullImageProvider(ImageAIProvider):
    nome = "null"

    def gerar_imagem(self, prompt: str, *, largura: int, altura: int) -> ImageGenerationResult:
        raise AIProviderIndisponivelError("Nenhum ImageAIProvider configurado (defina OPENAI_API_KEY).")


class OpenAITextProvider(TextAIProvider):
    nome = "openai"

    def __init__(self, *, api_key: str | None = None, modelo: str | None = None):
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.modelo = modelo or os.environ.get("ISIS_CONTENT_OPENAI_TEXT_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada.")

    def _client(self):
        from openai import OpenAI  # import tardio: dependência opcional

        return OpenAI(api_key=self.api_key, timeout=TIMEOUT_SEGUNDOS)

    def gerar_texto(self, prompt: str, *, contexto: dict | None = None) -> TextGenerationResult:
        if not orcamento_diario_disponivel():
            raise OrcamentoDiarioExcedidoError("Orçamento diário de IA (texto) esgotado.")

        def _chamada():
            cliente = self._client()
            resposta = cliente.chat.completions.create(
                model=self.modelo,
                messages=[{"role": "user", "content": prompt}],
                timeout=TIMEOUT_SEGUNDOS,
            )
            return resposta.choices[0].message.content or ""

        texto = _com_retry("gerar_texto", self.nome, _chamada)
        custo_estimado = _env_float("ISIS_CONTENT_OPENAI_TEXT_CUSTO_ESTIMADO", 0.01)
        registrar_consumo(provedor=self.nome, tipo="texto", custo_estimado=custo_estimado)
        return TextGenerationResult(texto=texto.strip(), custo_estimado=custo_estimado)


class OpenAIImageProvider(ImageAIProvider):
    nome = "openai"

    def __init__(self, *, api_key: str | None = None, modelo: str | None = None):
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.modelo = modelo or os.environ.get("ISIS_CONTENT_OPENAI_IMAGE_MODEL", "gpt-image-1")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada.")

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.api_key, timeout=TIMEOUT_SEGUNDOS)

    def gerar_imagem(self, prompt: str, *, largura: int, altura: int) -> ImageGenerationResult:
        import base64

        custo_estimado = _env_float("ISIS_CONTENT_OPENAI_IMAGE_CUSTO_ESTIMADO", 0.08)
        if not orcamento_diario_disponivel(custo_estimado):
            raise OrcamentoDiarioExcedidoError("Orçamento diário de IA (imagem) esgotado.")

        tamanho = f"{largura}x{altura}"

        def _chamada():
            cliente = self._client()
            resposta = cliente.images.generate(model=self.modelo, prompt=prompt, size=tamanho, n=1)
            b64 = resposta.data[0].b64_json
            return base64.b64decode(b64)

        dados = _com_retry("gerar_imagem", self.nome, _chamada)
        registrar_consumo(provedor=self.nome, tipo="imagem", custo_estimado=custo_estimado)
        return ImageGenerationResult(dados=dados, mime_type="image/png", custo_estimado=custo_estimado)


def obter_text_provider() -> TextAIProvider:
    try:
        return OpenAITextProvider()
    except ValueError:
        return NullTextProvider()


def obter_image_provider() -> ImageAIProvider:
    try:
        return OpenAIImageProvider()
    except ValueError:
        return NullImageProvider()
