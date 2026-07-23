"""Feature flags da Central Multiatendente (fila, assunção e transferência de
conversas). Mesmo padrão de backend/whatsapp_flags.py: cada flag é lida só da
variável de ambiente do processo, nasce desligada/no valor mais conservador
em qualquer ambiente sem configuração explícita -- inclusive produção.

Com ATENDIMENTO_SELLERS_ENABLED=false (padrão), o comportamento é idêntico ao
da Central de Atendimento anterior a esta funcionalidade: qualquer
administrador continua respondendo qualquer conversa sem assumir fila."""
from __future__ import annotations

import os

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}


def _flag_env(nome: str, default: str = "") -> bool:
    return os.environ.get(nome, default).strip().lower() in _VALORES_VERDADEIROS


def _int_env(nome: str, default: int, *, minimo: int = 0, maximo: int | None = None) -> int:
    bruto = os.environ.get(nome, "").strip()
    if not bruto:
        return default
    try:
        valor = int(bruto)
    except ValueError:
        return default
    if valor < minimo:
        return minimo
    if maximo is not None and valor > maximo:
        return maximo
    return valor


def atendimento_sellers_habilitado() -> bool:
    """ATENDIMENTO_SELLERS_ENABLED -- interruptor mestre da fila
    multiatendente. Desligada (padrão): a Central continua funcionando como
    antes desta PR, só para administradores, sem exigir assunção. Ligada:
    perfis vendedor/supervisor_atendimento passam a poder acessar a Central
    e as regras de fila/limite/assunção entram em vigor para todo mundo."""
    return _flag_env("ATENDIMENTO_SELLERS_ENABLED", "false")


def atendimento_max_conversas_padrao() -> int:
    """Limite padrão de conversas ativas por atendente -- pode ser
    sobrescrito por usuário (usuarios.atendimento_max_active_conversations)."""
    return _int_env("ATENDIMENTO_MAX_ACTIVE_CONVERSATIONS", 5, minimo=1, maximo=1000)


def atendimento_presence_timeout_segundos() -> int:
    """Depois de quanto tempo sem atividade um atendente 'online' deixa de
    ser considerado presente para fins de exibição -- nunca decide sozinho se
    alguém pode assumir conversa (isso depende sempre de atendimento_enabled/
    suspensão/sessão válida, nunca só deste timeout no navegador)."""
    return _int_env("ATENDIMENTO_PRESENCE_TIMEOUT_SECONDS", 120, minimo=15, maximo=3600)


def atendimento_permite_transferencia_por_vendedor() -> bool:
    """ATENDIMENTO_ALLOW_SELLER_TRANSFER -- permite que um vendedor
    transfira uma conversa PRÓPRIA para outro vendedor ativo. Sempre
    reavaliado no backend a cada chamada; nunca basta o botão existir no
    frontend."""
    return _flag_env("ATENDIMENTO_ALLOW_SELLER_TRANSFER", "true")


def atendimento_exige_assuncao_para_admin() -> bool:
    """ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN -- quando true (padrão),
    mesmo adm/supervisor precisam assumir (claim) a conversa antes de
    responder, para manter consistência de fila. Só tem efeito quando
    ATENDIMENTO_SELLERS_ENABLED=true."""
    return _flag_env("ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN", "true")
