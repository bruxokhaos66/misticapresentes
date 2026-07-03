from datetime import datetime

from config import (
    API_URL,
    AUTH_MODE,
    SERVER_URL,
    STORAGE_MODE,
    carregar_server_config,
    resetar_server_config_oficial,
    salvar_server_config,
)


DEFAULT_TIMEOUT = 8


def status_configuracao_servidor():
    cfg = carregar_server_config()
    return {
        "server_url": cfg.get("server_url") or SERVER_URL,
        "api_url": cfg.get("api_url") or API_URL,
        "storage_mode": cfg.get("storage_mode") or STORAGE_MODE,
        "server_mode": cfg.get("server_mode") or "production",
        "auth_mode": cfg.get("auth_mode") or AUTH_MODE,
        "use_public_domain_access": bool(cfg.get("use_public_domain_access", True)),
        "use_token_access": bool(cfg.get("use_token_access", False)),
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def configurar_servidor_oficial():
    return resetar_server_config_oficial()


def forcar_dominio_oficial():
    """Remove configuração antiga de token e grava o domínio oficial no app."""
    return salvar_server_config(
        server_url="https://misticaesotericos.com.br",
        api_url="https://misticaesotericos.com.br",
        storage_mode="local_first",
    )


def descricao_servidor():
    cfg = status_configuracao_servidor()
    return (
        "Servidor oficial configurado:\n"
        f"- Site: {cfg['server_url']}\n"
        f"- API: {cfg['api_url']}\n"
        f"- Modo: {cfg['server_mode']}\n"
        f"- Autenticação: {cfg['auth_mode']}\n"
        f"- Usa token antigo: {'sim' if cfg['use_token_access'] else 'não'}\n"
        f"- Armazenamento: {cfg['storage_mode']}\n\n"
        "O aplicativo agora usa o domínio oficial misticaesotericos.com.br como referência. "
        "Enquanto o backend online não estiver publicado, o aplicativo continua usando o banco local com segurança."
    )
