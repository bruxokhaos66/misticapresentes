from services import isis_service
from services import pesquisa_produto_service
from services import automacao_service

class IsisAssistant:
    def __init__(self, usuario=None):
        self.usuario = usuario or {}

    def responder(self, pergunta):
        p = isis_service.normalizar_texto(pergunta)
        nome = self.usuario.get("nome", "Sistema") if isinstance(self.usuario, dict) else "Sistema"

        auto = automacao_service.processar(pergunta)
        if auto:
            return {"handled": True, "modo": "automacao", "texto": auto}

        if any(x in p for x in ["pesquise", "pesquisar", "buscar online", "internet", "shopee", "mercado livre", "fornecedor", "atacado"]):
            consulta = pergunta
            for gatilho in ["pesquise na internet", "pesquisar na internet", "buscar na internet", "busque na internet", "pesquise", "pesquisar"]:
                if p.startswith(gatilho):
                    consulta = pergunta[len(gatilho):].strip(" :,-")
                    break
            dados = pesquisa_produto_service.pesquisar(consulta, usuario=nome, salvar=True)
            if not dados.get("ok") and not dados.get("resultados"):
                return {"handled": True, "modo": "pesquisa", "texto": "Tentei pesquisar, mas não encontrei resultado claro agora."}
            linhas = [f"Pesquisei por: {consulta}", "Resultados iniciais:"]
            for i, r in enumerate(dados.get("resultados", [])[:8], 1):
                linhas.append(f"{i}. {r.get('titulo')}\n   {r.get('link')}")
            linhas.append("\nConfirme preço, reputação, CNPJ, frete e prazo antes de comprar.")
            return {"handled": True, "modo": "pesquisa", "texto": "\n".join(linhas)}

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
