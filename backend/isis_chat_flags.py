"""Feature flags do Chat Inteligente da Isis 2.0 (homologação controlada).

Independentes das quatro flags do Estúdio Inteligente de Conteúdo (Fase 3,
`backend.isis_content_flags`) -- este módulo não lê, não escreve e não
depende de nenhuma delas. O chat é só recomendação de produtos e apoio
comercial; não ativa o Estúdio, geração automática de conteúdo, geração de
imagem nem publicação automática em nenhum caminho de código.

Mesmo padrão de `backend.isis_content_flags`/`backend.api_security`: cada
flag lida só da variável de ambiente do processo (nunca de query string,
header, cookie ou hostname), nasce desligada em qualquer ambiente sem
configuração explícita -- inclusive produção -- e nenhuma rota infere uma
flag a partir de outra.
"""
from __future__ import annotations

import os

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}


def _flag_env(nome: str, default: str = "") -> bool:
    return os.environ.get(nome, default).strip().lower() in _VALORES_VERDADEIROS


def _int_env(nome: str, default: int) -> int:
    try:
        return int(os.environ.get(nome, str(default)).strip())
    except (TypeError, ValueError):
        return default


def chat_habilitado() -> bool:
    """MISTICA_ISIS_CHAT_ENABLED -- sem esta flag, o chat não aparece para
    clientes comuns (o widget não monta e as rotas públicas respondem como
    desativadas)."""
    return _flag_env("MISTICA_ISIS_CHAT_ENABLED")


def chat_homolog_habilitado() -> bool:
    """MISTICA_ISIS_CHAT_HOMOLOG_ENABLED -- com o chat geral ligado, esta
    flag restringe o uso a contas autorizadas na homologação (admin ou
    aluno na allowlist fechada, ver `backend.isis_chat_auth`). Desligada,
    nenhuma conta consegue autorização, mesmo admin."""
    return _flag_env("MISTICA_ISIS_CHAT_HOMOLOG_ENABLED")


def chat_ai_habilitado() -> bool:
    """MISTICA_ISIS_CHAT_AI_ENABLED -- desligada (default), o fluxo roda em
    modo determinístico, sem provedor de IA e sem nenhuma chamada externa
    (custo e chamadas permanecem zero)."""
    return _flag_env("MISTICA_ISIS_CHAT_AI_ENABLED")


def chat_recomendacoes_habilitadas() -> bool:
    """MISTICA_ISIS_CHAT_PRODUCT_RECOMMENDATIONS_ENABLED -- libera
    recomendações de produto usando somente dados internos do catálogo."""
    return _flag_env("MISTICA_ISIS_CHAT_PRODUCT_RECOMMENDATIONS_ENABLED")


def max_mensagens_por_sessao() -> int:
    return max(1, _int_env("MISTICA_ISIS_CHAT_MAX_MESSAGES_PER_SESSION", 20))


def max_sessoes_por_hora() -> int:
    return max(1, _int_env("MISTICA_ISIS_CHAT_MAX_SESSIONS_PER_HOUR", 5))


def tamanho_maximo_mensagem() -> int:
    return max(1, _int_env("MISTICA_ISIS_CHAT_MESSAGE_MAX_LENGTH", 1000))


def sessao_ttl_minutos() -> int:
    return max(1, _int_env("MISTICA_ISIS_CHAT_SESSION_TTL_MINUTES", 60))


def limite_diario_chamadas_ia() -> int:
    """MISTICA_ISIS_CHAT_DAILY_AI_CALL_LIMIT -- default 0 (nenhuma chamada
    de IA permitida por dia); só tem efeito prático se `chat_ai_habilitado()`
    também estiver ligada."""
    return max(0, _int_env("MISTICA_ISIS_CHAT_DAILY_AI_CALL_LIMIT", 0))


def limite_diario_custo_centavos() -> int:
    """MISTICA_ISIS_CHAT_DAILY_COST_LIMIT_CENTS -- default 0 (custo zero
    permitido por dia)."""
    return max(0, _int_env("MISTICA_ISIS_CHAT_DAILY_COST_LIMIT_CENTS", 0))


def resumo_flags() -> dict:
    return {
        "chat_enabled": chat_habilitado(),
        "chat_homolog_enabled": chat_homolog_habilitado(),
        "chat_ai_enabled": chat_ai_habilitado(),
        "chat_product_recommendations_enabled": chat_recomendacoes_habilitadas(),
        "limits": {
            "max_messages_per_session": max_mensagens_por_sessao(),
            "max_sessions_per_hour": max_sessoes_por_hora(),
            "message_max_length": tamanho_maximo_mensagem(),
            "session_ttl_minutes": sessao_ttl_minutos(),
            "daily_ai_call_limit": limite_diario_chamadas_ia(),
            "daily_cost_limit_cents": limite_diario_custo_centavos(),
        },
    }


def resumo_flags_estudio_permanece_desativado() -> dict:
    """Só para auditoria/observabilidade: confirma no painel admin que as
    quatro flags da Fase 3 (Estúdio de Conteúdo) continuam fora do escopo
    deste módulo -- nunca lidas nem alteradas por ele."""
    from backend.isis_content_flags import resumo_flags as resumo_flags_estudio

    return resumo_flags_estudio()
