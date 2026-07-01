import os
import json
import hashlib
from datetime import datetime

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents")
CONFIG_REDE_PATH = os.path.join(DOCS_PATH, "mistica_config_rede.json")


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
    "Cliente bem atendido percebe o cuidado. Seja claro, educado e prestativo em cada conversa.",
    "Vendas fortes nascem de constância: manter a loja organizada, conhecer os produtos e atender com entusiasmo.",
    "A Mística Presentes cresce quando todos cuidam do mesmo objetivo: atendimento bonito, loja organizada e cliente satisfeito.",
]


def ensure_directories():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(ERROR_LOG_DIR, exist_ok=True)


def mensagem_dashboard_do_dia():
    try:
        indice = int(datetime.now().strftime("%j")) % len(DASHBOARD_DAILY_MSGS)
        return DASHBOARD_DAILY_MSGS[indice]
    except Exception:
        return DEFAULT_DASHBOARD_MSG


def hash_password_pbkdf2(password, salt=b"mistica_presentes_salt_secret"):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000).hex()
