from services import automacao_service
from services import isis_service


class IsisAssistant:
    def __init__(self, usuario=None):
        self.usuario = usuario or {}

    def _auditoria_manual(self):
        from services.auditoria_service import executar_auditoria_sistema, resumo_curto_auditoria

        relatorio = executar_auditoria_sistema(corrigir=True, origem="manual_isis")
        texto = resumo_curto_auditoria(relatorio)

        problemas = relatorio.get("problemas", [])
        correcoes = relatorio.get("correcoes", [])

        if problemas:
            texto += "\n\nPontos de atenção encontrados:\n- " + "\n- ".join(problemas[:8])
        else:
            texto += "\n\nNão encontrei problema crítico agora."

        if correcoes:
            texto += "\n\nCorreções seguras aplicadas:\n- " + "\n- ".join(correcoes[:8])

        texto += "\n\nEu posso corrigir automaticamente apenas estrutura do banco, índices e dados básicos. Bugs de código ficam registrados no relatório para revisão antes de alterar."
        return texto

    def responder(self, pergunta):
        p = isis_service.normalizar_texto(pergunta)

        auto = automacao_service.processar(pergunta)
        if auto:
            return {"handled": True, "modo": "automacao", "texto": auto}

        if any(x in p for x in ["auditoria", "analise completa", "análise completa", "verificar sistema", "revisar sistema", "buscar erros", "procurar bugs", "corrigir sistema"]):
            return {"handled": True, "modo": "auditoria_sistema", "texto": self._auditoria_manual()}

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
