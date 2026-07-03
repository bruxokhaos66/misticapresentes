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
PAINEL_URL = "https://api.misticaesotericos.com.br/painel/"
API_OFICIAL = "https://api.misticaesotericos.com.br"
SITE_OFICIAL = "https://misticaesotericos.com.br"


def status_configuracao_servidor():
    cfg = carregar_server_config()
    return {
        "server_url": cfg.get("server_url") or PAINEL_URL or SERVER_URL,
        "api_url": cfg.get("api_url") or API_OFICIAL or API_URL,
        "site_url": SITE_OFICIAL,
        "painel_url": PAINEL_URL,
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
    """Remove a configuração antiga de IP/token e grava o painel direto do servidor/API."""
    return salvar_server_config(
        server_url=PAINEL_URL,
        api_url=API_OFICIAL,
        storage_mode="api_first",
    )


def descricao_servidor():
    cfg = status_configuracao_servidor()
    return (
        "Mística Painel configurado para acesso em tempo real:\n"
        f"- Painel do app/celular: {cfg['painel_url']}\n"
        f"- API de dados: {cfg['api_url']}\n"
        f"- Site comercial: {cfg['site_url']}\n"
        f"- Modo: {cfg['server_mode']}\n"
        f"- Autenticação: {cfg['auth_mode']}\n"
        f"- Usa token antigo: {'sim' if cfg['use_token_access'] else 'não'}\n"
        f"- Armazenamento: {cfg['storage_mode']}\n\n"
        "O aplicativo de celular deve abrir o painel direto no servidor da API, com login de vendedor ou administrador. "
        "O IP local e o token antigo ficam desativados."
    )
