import os
import json
import hashlib
from datetime import datetime

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents")
CONFIG_REDE_PATH = os.path.join(DOCS_PATH, "mistica_config_rede.json")
SERVER_CONFIG_PATH = os.path.join(DOCS_PATH, "mistica_servidor_config.json")
OFFICIAL_DOMAIN = "misticaesotericos.com.br"
OFFICIAL_API_DOMAIN = "api.misticaesotericos.com.br"
DEFAULT_SITE_URL = f"https://{OFFICIAL_DOMAIN}"
DEFAULT_API_URL = f"https://{OFFICIAL_API_DOMAIN}"
DEFAULT_SERVER_URL = f"https://{OFFICIAL_DOMAIN}/painel/"
DEFAULT_SERVER_MODE = "production"
DEFAULT_STORAGE_MODE = "api_first"
DEFAULT_AUTH_MODE = "domain"


def _normalizar_url(url):
    texto = str(url or "").strip()
    if not texto:
        return ""
    if not texto.startswith(("http://", "https://")):
        texto = "https://" + texto
    return texto.rstrip("/")


def carregar_server_config():
    """Carrega a configuração oficial do Mística Painel.

    O app de celular deve abrir a área interna do site:
    https://misticaesotericos.com.br/painel/

    A API de dados fica em:
    https://api.misticaesotericos.com.br
    """
    cfg = {
        "server_url": DEFAULT_SERVER_URL,
        "api_url": DEFAULT_API_URL,
        "site_url": DEFAULT_SITE_URL,
        "server_mode": DEFAULT_SERVER_MODE,
        "storage_mode": DEFAULT_STORAGE_MODE,
        "auth_mode": DEFAULT_AUTH_MODE,
        "use_public_domain_access": True,
        "use_token_access": False,
    }
    try:
        if os.path.exists(SERVER_CONFIG_PATH):
            with open(SERVER_CONFIG_PATH, "r", encoding="utf-8") as f:
                local_cfg = json.load(f)
            if isinstance(local_cfg, dict):
                if local_cfg.get("storage_mode"):
                    cfg["storage_mode"] = local_cfg.get("storage_mode")
    except Exception:
        pass

    cfg["server_url"] = DEFAULT_SERVER_URL
    cfg["api_url"] = DEFAULT_API_URL
    cfg["site_url"] = DEFAULT_SITE_URL
    cfg["auth_mode"] = DEFAULT_AUTH_MODE
    cfg["use_public_domain_access"] = True
    cfg["use_token_access"] = False
    return cfg


def salvar_server_config(server_url=DEFAULT_SERVER_URL, api_url=None, storage_mode=DEFAULT_STORAGE_MODE):
    # Força o painel interno oficial e não grava tokens antigos no arquivo local.
    cfg = {
        "server_url": DEFAULT_SERVER_URL,
        "api_url": DEFAULT_API_URL,
        "site_url": DEFAULT_SITE_URL,
        "server_mode": DEFAULT_SERVER_MODE,
        "storage_mode": storage_mode or DEFAULT_STORAGE_MODE,
        "auth_mode": DEFAULT_AUTH_MODE,
        "use_public_domain_access": True,
        "use_token_access": False,
        "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    os.makedirs(DOCS_PATH, exist_ok=True)
    with open(SERVER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def resetar_server_config_oficial():
    """Recria a configuração local do servidor usando somente os domínios oficiais."""
    return salvar_server_config(DEFAULT_SERVER_URL, DEFAULT_API_URL, DEFAULT_STORAGE_MODE)


def carregar_db_path():
    padrao = os.path.join(DOCS_PATH, "mistica_gestao_v20.db")
    try:
        if os.path.exists(CONFIG_REDE_PATH):
            with open(CONFIG_REDE_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            caminho = str(cfg.get("db_path", "")).strip()
            if caminho:
                pasta = os.path.dirname(caminho)
                if pasta and os.path.exists(pasta):
                    return caminho
    except Exception:
        pass
    return padrao


SERVER_CONFIG = carregar_server_config()
SERVER_URL = SERVER_CONFIG["server_url"]
API_URL = SERVER_CONFIG["api_url"]
SERVER_MODE = SERVER_CONFIG.get("server_mode", DEFAULT_SERVER_MODE)
STORAGE_MODE = SERVER_CONFIG.get("storage_mode", DEFAULT_STORAGE_MODE)
AUTH_MODE = SERVER_CONFIG.get("auth_mode", DEFAULT_AUTH_MODE)
DB_PATH = carregar_db_path()
BACKUP_DIR = os.path.join(DOCS_PATH, "Mística_Backups")
ISSIS_IMG_PATH = os.path.join(DOCS_PATH, "issis_a_bruxinha.png")
ISSIS_IMG_FELIZ_PATH = os.path.join(DOCS_PATH, "issis_feliz.png")
ISSIS_IMG_PENSANDO_PATH = os.path.join(DOCS_PATH, "issis_pensando.png")
ISSIS_IMG_ALERTA_PATH = os.path.join(DOCS_PATH, "issis_alerta.png")
ISSIS_IMG_RAIVA_PATH = os.path.join(DOCS_PATH, "issis_raiva.png")
ISSIS_IMG_DESCOBERTA_PATH = os.path.join(DOCS_PATH, "issis_descoberta.png")
ISSIS_IMG_SONO_PATH = os.path.join(DOCS_PATH, "issis_sono.png")
ISSIS_HISTORY_PATH = os.path.join(DOCS_PATH, "issis_memoria_mensagens.json")
ISSIS_LEARNING_PATH = os.path.join(DOCS_PATH, "issis_aprendizado.json")
ERROR_LOG_DIR = os.path.join(DOCS_PATH, "Mística_Erros")
ERROR_LOG_PATH = os.path.join(ERROR_LOG_DIR, "erros_sistema.log")
DASHBOARD_MSG_PATH = os.path.join(DOCS_PATH, "mistica_mensagem_dashboard.txt")

DEFAULT_DASHBOARD_MSG = (
    "Vender não é apenas oferecer um produto. É criar confiança, solucionar necessidades "
    "e deixar uma experiência positiva em cada atendimento. O sucesso de um vendedor não "
    "está apenas nas vendas que realiza, mas nas pessoas que conquista ao longo do caminho."
)

DASHBOARD_DAILY_MSGS = [
    "Hoje é dia de atender com presença, carinho e atenção. Cada cliente que entra pode sair levando uma boa energia da Mística Presentes.",
    "Vender bem é ouvir primeiro, entender a necessidade e oferecer com verdade. Que hoje cada atendimento seja feito com coração e profissionalismo.",
    "A loja cresce quando cada detalhe importa: sorriso, organização, capricho e cuidado com o cliente. Vamos fazer um dia melhor que ontem.",
    "Cada venda começa com confiança. Atendimento cordial, produto bem apresentado e energia positiva fazem toda a diferença.",
    "Hoje, transforme atendimento em experiência. Quem se sente bem atendido volta, indica e fortalece a Mística Presentes.",
    "Organização, foco e simpatia são parte da venda. Uma loja bonita começa pela atitude de quem cuida dela.",
    "Que hoje cada cliente encontre mais do que um produto: encontre acolhimento, atenção e vontade de voltar.",
    "Vendedor excelente não empurra produto; ajuda o cliente a escolher melhor. Esse é o diferencial da Mística Presentes.",
    "Comece o dia com atenção aos detalhes. Produto alinhado, estoque cuidado e atendimento gentil vendem mais.",
    "A energia da loja também vem da equipe. Trabalhe com leveza, responsabilidade e orgulho do que está construindo.",
    "Cada atendimento é uma oportunidade de encantar. Faça o simples bem feito e o resultado aparece.",
    "Hoje é um bom dia para vender com propósito: resolver, orientar e criar uma boa lembrança para cada cliente.",
]


def mensagem_dashboard_do_dia():
    """Retorna a mensagem motivacional exibida no dashboard."""
    try:
        if os.path.exists(DASHBOARD_MSG_PATH):
            with open(DASHBOARD_MSG_PATH, "r", encoding="utf-8") as f:
                texto = f.read().strip()
            if texto:
                return texto
    except Exception:
        pass

    try:
        if DASHBOARD_DAILY_MSGS:
            indice = datetime.now().timetuple().tm_yday % len(DASHBOARD_DAILY_MSGS)
            return DASHBOARD_DAILY_MSGS[indice]
    except Exception:
        pass

    return DEFAULT_DASHBOARD_MSG


def hash_password_pbkdf2(senha, salt=b"mistica_presentes"):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 120000).hex()


def ensure_directories():
    for pasta in [DOCS_PATH, BACKUP_DIR, ERROR_LOG_DIR]:
        os.makedirs(pasta, exist_ok=True)
    try:
        resetar_server_config_oficial()
    except Exception:
        pass


ensure_directories()
