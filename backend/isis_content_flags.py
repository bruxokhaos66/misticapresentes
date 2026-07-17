"""Feature flags do Estúdio Inteligente de Conteúdo (Isis 2.0 — Fase 3).

Seguem o mesmo padrão de `backend.api_security.estorno_rest_habilitado`:
cada flag é independente, lida só da variável de ambiente do processo (nunca
de query string, header ou hostname), e nasce desligada em qualquer
ambiente sem configuração explícita -- inclusive produção.

Nenhuma rota deste módulo deve inferir uma flag a partir de outra: são
quatro interruptores propositalmente separados, para permitir ligar por
etapas (primeiro o estúdio para revisão manual, só depois -- em uma fase
futura -- a geração automática, a geração de imagem e, por último, a
publicação automática, que esta fase não implementa em nenhum caminho de
código, ligada ou desligada).
"""
from __future__ import annotations

import os

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}


def _flag_env(nome: str) -> bool:
    return os.environ.get(nome, "").strip().lower() in _VALORES_VERDADEIROS


def content_studio_habilitado() -> bool:
    """MISTICA_ISIS_CONTENT_STUDIO_ENABLED — libera toda a infraestrutura do
    estúdio (tabelas já existem sempre; isto controla só as rotas/admin)."""
    return _flag_env("MISTICA_ISIS_CONTENT_STUDIO_ENABLED")


def auto_generation_habilitado() -> bool:
    """MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED — libera o job diário
    (08:00 America/Sao_Paulo) gerar os dois rascunhos automaticamente. Sem
    esta flag, a geração só ocorre por acionamento manual de um
    administrador autenticado, mesmo com o estúdio habilitado."""
    return _flag_env("MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED")


def image_generation_habilitado() -> bool:
    """MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED — libera chamar o
    ImageAIProvider de fato. Desligada, os rascunhos são gerados só com
    prompt visual salvo (sem imagem), para revisão de texto."""
    return _flag_env("MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED")


def auto_publish_habilitado() -> bool:
    """MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED — não implementada nesta
    fase: nenhuma rota ou job publica em rede social automaticamente,
    independente do valor desta variável. A flag existe só para deixar
    explícito, em qualquer auditoria de configuração, que a publicação
    automática está fora de escopo até uma fase futura que a implemente."""
    return _flag_env("MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED")


def resumo_flags() -> dict:
    return {
        "content_studio_enabled": content_studio_habilitado(),
        "auto_generation_enabled": auto_generation_habilitado(),
        "image_generation_enabled": image_generation_habilitado(),
        "auto_publish_enabled": auto_publish_habilitado(),
    }
