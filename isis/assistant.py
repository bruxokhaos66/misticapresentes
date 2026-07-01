from services import automacao_service
from services import isis_service


class IsisAssistant:
    def __init__(self, usuario=None):
        self.usuario = usuario or {}

    def responder(self, pergunta):
        p = isis_service.normalizar_texto(pergunta)

        auto = automacao_service.processar(pergunta)
        if auto:
            return {"handled": True, "modo": "automacao", "texto": auto}

        # Pesquisa online fica centralizada em services.isis_service.processar_comando_inteligente.
        # Este assistente cuida das respostas operacionais internas quando a pesquisa nao foi acionada.
        if any(x in p for x in ["prioridade", "o que fazer hoje", "tarefas de hoje"]):
            return {"handled": True, "modo": "prioridades", "texto": isis_service.prioridades_do_dia()}
        if any(x in p for x in ["resumo da loja", "como esta a loja", "como está a loja", "painel da loja"]):
            return {"handled": True, "modo": "resumo", "texto": isis_service.resumo_inteligente_loja()}
        if any(x in p for x in ["estoque baixo", "alerta", "alertas"]):
            return {"handled": True, "modo": "alertas", "texto": isis_service.alertas_operacionais()}
        if any(x in p for x in ["sem giro", "parado", "encalhado"]):
            return {"handled": True, "modo": "estoque", "texto": isis_service.produtos_sem_giro_texto()}
        if any(x in p for x in ["cadastro incompleto", "clientes incompletos"]):
            return {"handled": True, "modo": "clientes", "texto": isis_service.clientes_incompletos_texto()}

        return {"handled": False, "modo": "livre", "texto": ""}
