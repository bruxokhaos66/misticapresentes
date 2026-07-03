from datetime import datetime

from config import API_URL, SERVER_URL, STORAGE_MODE, carregar_server_config, salvar_server_config


DEFAULT_TIMEOUT = 8


def status_configuracao_servidor():
    cfg = carregar_server_config()
    return {
        "server_url": cfg.get("server_url") or SERVER_URL,
        "api_url": cfg.get("api_url") or API_URL,
        "storage_mode": cfg.get("storage_mode") or STORAGE_MODE,
        "server_mode": cfg.get("server_mode") or "production",
        "use_public_domain_access": bool(cfg.get("use_public_domain_access", True)),
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def configurar_servidor_oficial():
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
        f"- Armazenamento: {cfg['storage_mode']}\n\n"
        "Enquanto o backend online não estiver publicado, o aplicativo continua usando o banco local com segurança."
    )
