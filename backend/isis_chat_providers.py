"""Camada de abstração de IA do Chat da Isis 2.0 -- interface desacoplada,
sem nenhum provedor real configurado nesta fase.

`IsisChatProvider` define o contrato que um futuro provedor externo teria
que implementar (`classify_intent`, `generate_answer`, `summarize_session`).
Duas implementações existem hoje:

- `DeterministicChatProvider`: usado quando `MISTICA_ISIS_CHAT_AI_ENABLED`
  está desligada (default) -- delega para as regras determinísticas
  (`backend.isis_chat_intent`), nenhuma chamada de rede, custo zero.
- `DisabledAIChatProvider`: usado quando a flag está ligada mas nenhum
  provedor real foi configurado (nenhuma chave de API existe no código) --
  falha de forma segura, registra o erro e devolve o mesmo fallback
  determinístico, sem quebrar o chat.

Nenhuma chave de API real é lida, guardada ou referenciada por este
módulo. Ativar um provedor de verdade no futuro exigiria uma terceira
implementação concreta, nunca alterar o contrato desta interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.isis_chat_flags import chat_ai_habilitado
from backend.isis_chat_intent import ResultadoIntent, detectar_intent
from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RespostaProvider:
    intent_resultado: ResultadoIntent
    chamou_ia: bool
    custo_estimado_centavos: int = 0


class IsisChatProvider(ABC):
    nome: str = "abstrato"

    @abstractmethod
    def classify_intent(self, texto: str) -> ResultadoIntent:
        ...

    @abstractmethod
    def generate_answer(self, *, intent_resultado: ResultadoIntent, contexto: dict) -> RespostaProvider:
        ...

    @abstractmethod
    def summarize_session(self, resumo_atual: str, nova_mensagem_resumo: str) -> str:
        ...


class DeterministicChatProvider(IsisChatProvider):
    """Sem provedor de IA externo: só regras + busca interna. Nenhuma
    chamada de rede é feita em nenhum método."""

    nome = "deterministico"

    def classify_intent(self, texto: str) -> ResultadoIntent:
        return detectar_intent(texto)

    def generate_answer(self, *, intent_resultado: ResultadoIntent, contexto: dict) -> RespostaProvider:
        return RespostaProvider(intent_resultado=intent_resultado, chamou_ia=False, custo_estimado_centavos=0)

    def summarize_session(self, resumo_atual: str, nova_mensagem_resumo: str) -> str:
        partes = [p for p in (resumo_atual, nova_mensagem_resumo) if p]
        resumo = " | ".join(partes)
        return resumo[-280:]


class AIProviderIndisponivelError(Exception):
    pass


class DisabledAIChatProvider(IsisChatProvider):
    """`MISTICA_ISIS_CHAT_AI_ENABLED=true` sem nenhum provedor externo
    configurado (nenhuma chave de API existe neste código): falha de
    forma segura, registra o erro e cai para o mesmo comportamento
    determinístico -- nunca quebra o chat, nunca tenta se conectar a
    nada."""

    nome = "ia_desabilitada_sem_provedor"

    def __init__(self) -> None:
        self._fallback = DeterministicChatProvider()

    def classify_intent(self, texto: str) -> ResultadoIntent:
        logger.warning(
            "isis chat: IA habilitada sem provedor configurado, usando fallback determinístico",
            extra={"evento": "isis_chat_ia_sem_provedor", "error_code": "ai_provider_unconfigured"},
        )
        return self._fallback.classify_intent(texto)

    def generate_answer(self, *, intent_resultado: ResultadoIntent, contexto: dict) -> RespostaProvider:
        logger.warning(
            "isis chat: IA habilitada sem provedor configurado, usando fallback determinístico",
            extra={"evento": "isis_chat_ia_sem_provedor", "error_code": "ai_provider_unconfigured"},
        )
        return self._fallback.generate_answer(intent_resultado=intent_resultado, contexto=contexto)

    def summarize_session(self, resumo_atual: str, nova_mensagem_resumo: str) -> str:
        return self._fallback.summarize_session(resumo_atual, nova_mensagem_resumo)


def obter_chat_provider() -> IsisChatProvider:
    """Fábrica única do provedor ativo. `MISTICA_ISIS_CHAT_AI_ENABLED=false`
    (default): sempre `DeterministicChatProvider`, sem exceção. Ligada, mas
    sem nenhum provedor externo configurado neste código: `DisabledAIChatProvider`
    (fallback seguro, nunca uma chamada de rede)."""
    if not chat_ai_habilitado():
        return DeterministicChatProvider()
    return DisabledAIChatProvider()
