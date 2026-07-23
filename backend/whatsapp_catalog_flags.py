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


# Hosts seguros que o próprio projeto já conhece sem depender de nenhuma
# configuração externa -- domínio oficial do site/API (mesmo trio de
# backend/api_security.py::ORIGENS_PERMITIDAS, aqui só o hostname, sem
# esquema/porta) e o host de download já usado como fallback legado de
# imagem de produto (backend/drive_storage.py). Nunca inclui um wildcard
# global (`*`, `*.com`) nem confia em nada vindo da requisição.
_HOSTS_OFICIAIS_PADRAO = (
    "misticaesotericos.com.br",
    "www.misticaesotericos.com.br",
    "api.misticaesotericos.com.br",
    "drive.google.com",
)


def atendimento_catalog_allowed_image_hosts() -> tuple[frozenset[str], frozenset[str]]:
    """Allowlist de hosts permitidos para imagem comercial do Catálogo
    (item 6 do envio de produto). Devolve (hosts_exatos, sufixos_wildcard):

    - hosts_exatos: comparação exata (host == entrada).
    - sufixos_wildcard: comparação por sufixo com fronteira de ponto
      (host == sufixo OU host termina em "." + sufixo) -- só quando a
      entrada de configuração começar explicitamente com "*." (nunca um
      `endswith` sem fronteira, que aceitaria "evilmisticaesotericos.com.br"
      para o sufixo "misticaesotericos.com.br").

    Sempre inclui os hosts oficiais (_HOSTS_OFICIAIS_PADRAO) e o host de
    PRODUCT_IMAGES_PUBLIC_BASE_URL quando configurado (lido do ambiente do
    servidor, nunca do request) -- nunca um wildcard global, nunca
    correspondência insegura por substring. ATENDIMENTO_CATALOG_ALLOWED_IMAGE_HOSTS
    (lista separada por vírgula) soma hosts extras (ex.: uma CDN legítima
    nova), nunca substitui os hosts oficiais."""
    from urllib.parse import urlsplit

    exatos: set[str] = set(_HOSTS_OFICIAIS_PADRAO)
    wildcards: set[str] = set()

    base_imagens = os.environ.get("PRODUCT_IMAGES_PUBLIC_BASE_URL", "").strip()
    if base_imagens:
        try:
            host_base = urlsplit(base_imagens).hostname
        except ValueError:
            host_base = None
        if host_base:
            exatos.add(host_base.lower().rstrip("."))

    bruto = os.environ.get("ATENDIMENTO_CATALOG_ALLOWED_IMAGE_HOSTS", "").strip()
    for pedaco in bruto.split(","):
        entrada = pedaco.strip().lower().rstrip(".")
        if not entrada or entrada == "*":
            continue
        if entrada.startswith("*."):
            sufixo = entrada[2:].strip(".")
            if sufixo:
                wildcards.add(sufixo)
        else:
            exatos.add(entrada)

    return frozenset(exatos), frozenset(wildcards)
