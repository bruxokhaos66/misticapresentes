from services import automacao_service
from services import isis_service


class IsisAssistant:
    def __init__(self, usuario=None):
        self.usuario = usuario or {}

    def _auditoria_manual(self, corrigir=False):
        from services.auditoria_service import executar_auditoria_sistema, resumo_curto_auditoria

        relatorio = executar_auditoria_sistema(corrigir=bool(corrigir), origem="manual_isis")
        texto = resumo_curto_auditoria(relatorio)

        problemas = relatorio.get("problemas", [])
        correcoes = relatorio.get("correcoes", [])

        if problemas:
            texto += "\n\nPontos de atenção encontrados:\n- " + "\n- ".join(problemas[:8])
        else:
            texto += "\n\nNão encontrei problema crítico agora."

        if correcoes:
            texto += "\n\nCorreções seguras aplicadas:\n- " + "\n- ".join(correcoes[:8])
        elif not corrigir:
            texto += "\n\nModo usado: apenas análise. Para aplicar correções seguras, diga: Isis, corrigir sistema."

        texto += "\n\nMudanças em código-fonte continuam exigindo revisão antes de alterar."
        return texto

    def responder(self, pergunta):
        p = isis_service.normalizar_texto(pergunta)

        auto = automacao_service.processar(pergunta)
        if auto:
            return {"handled": True, "modo": "automacao", "texto": auto}

        gatilhos_correcao = [
            "corrigir sistema", "corrigir bugs", "reparar sistema", "fazer correcoes", "fazer correções",
            "arrumar sistema", "consertar sistema", "corrige o sistema"
        ]
        if any(x in p for x in gatilhos_correcao):
            return {"handled": True, "modo": "correcao_sistema", "texto": self._auditoria_manual(corrigir=True)}

        gatilhos_auditoria = [
            "auditoria", "analise completa", "análise completa", "verificar sistema", "verifica sistema",
            "verifica o sistema", "verifica como esta o sistema", "verifica como está o sistema",
            "checar sistema", "checa sistema", "checa o sistema", "status do sistema",
            "como esta o sistema", "como está o sistema", "revisar sistema", "buscar erros",
            "procurar bugs", "erros do sistema", "bugs do sistema", "diagnostico do sistema",
            "diagnóstico do sistema", "analisar sistema", "analisa o sistema"
        ]
        if any(x in p for x in gatilhos_auditoria):
            return {"handled": True, "modo": "auditoria_sistema", "texto": self._auditoria_manual(corrigir=False)}

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
