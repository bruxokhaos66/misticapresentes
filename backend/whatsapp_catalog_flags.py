"""Feature flags do Catálogo Comercial na Central de Atendimento WhatsApp.

Mesmo padrão de backend/whatsapp_flags.py e backend/atendimento_flags.py:
cada flag é lida só da variável de ambiente do processo, nasce
desligada/no valor mais conservador em qualquer ambiente sem configuração
explícita -- inclusive produção. Com ATENDIMENTO_CATALOG_ENABLED=false
(padrão), nenhuma rota de catálogo funciona e o frontend não deve exibir o
painel Produtos -- a Central de Atendimento continua idêntica à versão sem
esta funcionalidade (PRs #405-407)."""
from __future__ import annotations

import os

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}


def _flag_env(nome: str, default: str = "") -> bool:
    return os.environ.get(nome, default).strip().lower() in _VALORES_VERDADEIROS


def _int_env(nome: str, default: int, *, minimo: int, maximo: int) -> int:
    bruto = os.environ.get(nome, "").strip()
    if not bruto:
        return default
    try:
        valor = int(bruto)
    except ValueError:
        return default
    if valor < minimo:
        return minimo
    if valor > maximo:
        return maximo
    return valor


def atendimento_catalog_habilitado() -> bool:
    """ATENDIMENTO_CATALOG_ENABLED -- interruptor mestre do Catálogo
    Comercial. Desligada (padrão): nenhuma mudança aparece na Central e
    todas as rotas de catálogo/envio de produto devolvem 503."""
    return _flag_env("ATENDIMENTO_CATALOG_ENABLED", "false")


def atendimento_catalog_max_produtos_por_envio() -> int:
    """Limite máximo de produtos em um único envio em lote (item 10 da
    especificação -- nunca envia dezenas de produtos em sequência)."""
    return _int_env("ATENDIMENTO_CATALOG_MAX_PRODUCTS_PER_SEND", 5, minimo=1, maximo=10)


def atendimento_catalog_limite_estoque_baixo() -> int:
    """Quantidade em estoque igual ou abaixo deste limite é normalizada
    como 'low_stock' em vez de 'available' (nunca expõe a quantidade exata
    ao atendente por padrão -- ver backend/whatsapp_catalog_repository.py)."""
    return _int_env("ATENDIMENTO_CATALOG_LOW_STOCK_THRESHOLD", 3, minimo=0, maximo=1000)
