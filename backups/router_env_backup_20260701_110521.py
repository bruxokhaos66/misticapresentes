import os

from isis.confirmations import limpar_pendente, obter_pendente, salvar_pendente
from isis.intent_detector import detectar
from isis.safety import contem_bloqueio
from isis import actions
from repositories import isis_logs
from services import automacao_service, encomenda_service, pesquisa_produto_service


def _nome(usuario):
    return usuario.get("nome", "Sistema") if isinstance(usuario, dict) else "Sistema"


def responder(texto, usuario=None):
    usuario = usuario or {"nome": "Sistema"}
    nome = _nome(usuario)
    if contem_bloqueio(texto):
        return {"handled": True, "modo": "seguranca", "texto": "Por seguranca, eu nao preencho senha, cartao, dados pessoais nem compro online automaticamente."}
    det = detectar(texto)
    intent = det["intent"]
    try:
        if intent == "confirmacao_sim":
            pendente = obter_pendente(usuario)
            if not pendente:
                return {"handled": True, "modo": "confirmacao", "texto": "Nao encontrei nenhuma acao pendente para confirmar."}
            resposta = actions.executar_pendente(pendente, usuario)
            limpar_pendente(usuario)
            return {"handled": True, "modo": "acao_executada", "texto": resposta}
        if intent == "confirmacao_nao":
            limpar_pendente(usuario)
            return {"handled": True, "modo": "confirmacao", "texto": "Tudo bem. Cancelei a acao pendente e nao alterei dados."}
        if intent in ["consulta_vendas", "consulta_estoque", "consulta_caixa"]:
            resposta = actions.consulta(intent, texto)
            isis_logs.registrar(texto, intent, nome, resposta)
            return {"handled": True, "modo": "consulta", "texto": resposta}
        if intent == "calculo_margem":
            return {"handled": True, "modo": "consulta", "texto": actions.calcular_margem(texto)}
        if intent == "venda_texto":
            prep = actions.preparar_venda(texto, usuario)
            if prep.get("pendente"):
                salvar_pendente(usuario, prep["pendente"])
            return {"handled": True, "modo": "acao_pendente", "texto": prep["texto"]}
        if intent == "cadastro_produto":
            prep = actions.preparar_cadastro_produto(texto, usuario)
            if prep.get("pendente"):
                salvar_pendente(usuario, prep["pendente"])
            return {"handled": True, "modo": "acao_pendente", "texto": prep["texto"]}
        if intent == "entrada_estoque":
            prep = actions.preparar_entrada_estoque(texto, usuario)
            if prep.get("pendente"):
                salvar_pendente(usuario, prep["pendente"])
            return {"handled": True, "modo": "acao_pendente", "texto": prep["texto"]}
        if intent == "alterar_preco":
            prep = actions.preparar_alterar_preco(texto, usuario)
            if prep.get("pendente"):
                salvar_pendente(usuario, prep["pendente"])
            return {"handled": True, "modo": "acao_pendente", "texto": prep["texto"]}
        if intent == "pesquisa_produto":
            try:
                dados = pesquisa_produto_service.pesquisar(texto, nome, salvar=False)
                linhas = [f"Pesquisa feita em {dados['data_hora']}:", dados["aviso"]]
                for idx, r in enumerate(dados.get("resultados", [])[:6], 1):
                    linhas.append(f"{idx}. {r.get('titulo')}\n   {r.get('link')}")
                return {"handled": True, "modo": "pesquisa", "texto": "\n".join(linhas)}
            except Exception as e:
                return {"handled": True, "modo": "pesquisa", "texto": f"Nao consegui pesquisar online agora. O sistema continua funcionando offline. Detalhe: {e}"}
        if intent == "encomenda":
            if "lista" in texto.lower() or "pendente" in texto.lower():
                encs = encomenda_service.listar_pendentes()
                if not encs:
                    return {"handled": True, "modo": "encomenda", "texto": "Nao ha encomendas pendentes."}
                return {"handled": True, "modo": "encomenda", "texto": "Encomendas pendentes:\n" + "\n".join([f"- {e[0]} | {e[1]} | {e[2]} | {e[3]} un" for e in encs])}
            return {"handled": True, "modo": "encomenda", "texto": "Posso criar encomenda, mas preciso dos dados: cliente, produto, quantidade e origem/prazo."}
        if intent == "automacao":
            return {"handled": True, "modo": "automacao", "texto": automacao_service.processar(texto)}
    except Exception as e:
        isis_logs.registrar(texto, intent, nome, "", str(e))
        return {"handled": True, "modo": "erro", "texto": f"Encontrei um erro ao processar esse comando: {e}"}

    prompt = (
        "Voce esta conversando com um usuario da loja Mistica Presentes. "
        "Responda como Isis a Bruxinha, em portugues do Brasil, com tom natural, profissional e acolhedor. "
        "Se for uma saudacao, responda normalmente. Se for pedido de dado real, explique que voce pode consultar o sistema. "
        "Mensagem do usuario: " + texto
    )
    provider = os.environ.get("IA_PROVIDER", "auto").lower()
    candidatos = ["isis.local_llm", "isis.gemini_client", "isis.groq_client"] if provider == "auto" else [f"isis.{provider}_client"]
    for mod_name in candidatos:
        try:
            mod = __import__(mod_name, fromlist=["gerar_resposta"])
            resposta = mod.gerar_resposta(prompt)
            if resposta:
                return {"handled": True, "modo": "conversa", "texto": resposta}
        except Exception:
            pass
    texto_simples = (
        "Estou funcionando no modo gratuito/offline agora. "
        "Posso consultar vendas, estoque, caixa, calcular margem, preparar pesquisas, encomendas e automacoes. "
        "Para agir no sistema, sempre vou pedir confirmacao antes."
    )
    isis_logs.registrar(texto, "fallback_local", nome, texto_simples)
    return {"handled": True, "modo": "fallback_local", "texto": texto_simples}
