import re
from datetime import datetime

from database import query_db
from reports.estoque_report import contar_estoque_baixo, estoque_baixo, produtos_cadastro_incompleto, produtos_para_giro, produtos_sem_giro
from reports.financeiro_report import contas_para_alerta, contas_pendentes_resumo
from reports.vendas_report import lucro_bruto_itens_periodo, produto_campeao, resumo_vendas_periodo, total_vendido_produto
from services.caixa_service import caixa_abertos_count, obter_caixa_id_ativo, status_caixa_aberto


def consulta_sql(sql, params=()):
    return query_db(sql, params)


def normalizar_texto(texto):
    mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
    return str(texto or "").translate(mapa).lower().strip()


def detectar_intencao(pergunta):
    p = normalizar_texto(pergunta)
    sinonimos = {
        "lucro": ["lucro", "lucrei", "rentabilidade", "margem", "ganho", "ganhei", "lucros"],
        "faturamento": ["faturou", "faturamento", "vendeu", "receita", "vendas", "movimento", "faturado", "vendi"],
        "estoque": ["estoque", "falta", "acabou", "reposicao", "comprar", "repor", "reposicoes"],
        "financeiro": ["saldo", "caixa", "contas", "pagar", "vencidas", "despesas", "despesa", "custo", "pagamento"],
        "clientes": ["cliente", "inativo", "aniversario", "aniversariantes", "nascimento", "fidelidade", "marketing", "comprou"],
        "produtos": ["produto", "mais vendido", "encalhado", "giro", "mais vendidos", "campeao", "campeoes"],
    }
    pontos = {intent: 0 for intent in sinonimos}
    for intent, termos in sinonimos.items():
        for termo in termos:
            if termo in p:
                pontos[intent] += 1
    maior = max(pontos.values())
    return [intent for intent, valor in pontos.items() if valor == maior][0] if maior > 0 else None


def periodo_mes(pergunta):
    agora = datetime.now()
    mes = agora.strftime("%m")
    ano = agora.strftime("%Y")
    meses_map = {
        "janeiro": "01", "fevereiro": "02", "marco": "03", "março": "03", "abril": "04",
        "maio": "05", "junho": "06", "julho": "07", "agosto": "08", "setembro": "09",
        "outubro": "10", "novembro": "11", "dezembro": "12",
    }
    p = normalizar_texto(pergunta)
    for nome, numero in meses_map.items():
        if normalizar_texto(nome) in p:
            mes = numero
            break
    padrao = re.findall(r"\b(0[1-9]|1[0-2])\b", pergunta)
    if padrao:
        mes = padrao[0]
    anos = re.findall(r"\b(202\d)\b", pergunta)
    if anos:
        ano = anos[0]
    return mes, ano, f"/{mes}/{ano}"


def dica_sazonal(mes):
    sazonais = {
        6: "Dica sazonal de inverno: destaque velas aromáticas, essências amadeiradas e incensos de canela ou baunilha.",
        7: "Dica sazonal de inverno: monte kits de aconchego com vela, incensário e aroma especial.",
        8: "Dica sazonal de inverno: bons stories podem mostrar produtos que aquecem o ambiente.",
        11: "Dica de fim de ano: destaque banhos de ervas, pirita, citrino, incensos de sete ervas e velas brancas.",
        12: "Dica de fim de ano: capriche nos kits prontos e embalagens para presente.",
        5: "Dica de Dia das Mães: crie kits com sabonetes artesanais, quartzo rosa, incensos florais e difusores.",
    }
    return sazonais.get(int(mes), "Dica sazonal: destaque renovação, equilíbrio, sálvia branca, ametista, quartzo verde e aromas suaves.")


def calcular_giro_estoque_30_dias():
    resultados = []
    for cod, nome, qtd_atual, est_min, categoria in produtos_para_giro():
        total_vendido = total_vendido_produto(cod)
        qtd_atual = int(qtd_atual or 0)
        est_min = int(est_min or 0)
        media_diaria = total_vendido / 30.0
        dias_restantes = qtd_atual / media_diaria if media_diaria > 0 else float("inf")
        alvo = total_vendido * 2
        compra_sugerida = max(0, alvo - qtd_atual)
        if compra_sugerida > 0 or qtd_atual <= est_min:
            resultados.append({
                "cod": cod,
                "nome": nome,
                "qtd_atual": qtd_atual,
                "est_min": est_min,
                "categoria": categoria,
                "total_vendido": total_vendido,
                "media_diaria": media_diaria,
                "dias_restantes": dias_restantes,
                "compra_sugerida": int(compra_sugerida) if compra_sugerida > 0 else max(10, est_min * 2),
            })
    return resultados


def resumo_financeiro_isis():
    contas = contas_pendentes_resumo()
    caixa = status_caixa_aberto()
    return {"contas": contas, "caixa": caixa}


def aniversariantes_hoje():
    hoje = datetime.now().strftime("%d/%m")
    return query_db("SELECT id, nome, nascimento FROM clientes WHERE nascimento LIKE ?", (f"%{hoje}%",))


def clientes_incompletos(limite=20):
    return query_db(
        """
        SELECT nome, COALESCE(telefone,''), COALESCE(cpf,'')
        FROM clientes
        WHERE COALESCE(ativo,1)=1
          AND (COALESCE(telefone,'')='' OR COALESCE(cpf,'')='')
        ORDER BY nome
        LIMIT ?
        """,
        (int(limite),),
    )


def alertas_operacionais(formatador=str, formato_balao=False):
    alertas = []
    baixo = estoque_baixo(6)
    if baixo:
        alertas.append("Estoque baixo: " + ", ".join([f"{b[0]} ({b[1]} un)" for b in baixo]))
    nivers = query_db(
        "SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? ORDER BY nome LIMIT 6",
        (f"%{datetime.now().strftime('%d/%m')}%",),
    )
    if nivers:
        alertas.append("Aniversariantes hoje: " + ", ".join([n[0] for n in nivers]))
    vencendo = []
    agora = datetime.now()
    for desc, valor, vencimento in contas_para_alerta():
        try:
            data_v = datetime.strptime(str(vencimento), "%d/%m/%Y")
            dias = (data_v.date() - agora.date()).days
            if dias < 0:
                vencendo.append(f"{desc} vencida há {abs(dias)} dia(s) ({formatador(valor)})")
            elif dias <= 7:
                vencendo.append(f"{desc} vence em {dias} dia(s) ({formatador(valor)})")
        except Exception:
            pass
    if vencendo:
        alertas.append("Contas: " + "; ".join(vencendo[:4]))
    caixa = status_caixa_aberto()
    if caixa:
        try:
            abertura = datetime.strptime(caixa[2], "%d/%m/%Y %H:%M")
            horas = (agora - abertura).total_seconds() / 3600
            if horas >= 8:
                alertas.append(f"Caixa aberto há {horas:.1f} horas. Confira se já está na hora de fechar.")
        except Exception:
            pass
    parados = produtos_sem_giro(3, somente_com_estoque=True)
    if parados:
        alertas.append("Produtos sem giro: " + ", ".join([f"{p[0]} ({p[1]} un)" for p in parados]))
    if formato_balao:
        return alertas[0] if alertas else "Sem alertas críticos agora. A loja parece organizada."
    if not alertas:
        return "Não encontrei alertas urgentes agora. Caixa, estoque, contas e clientes parecem tranquilos."
    return "Alertas da Isis agora:\n- " + "\n- ".join(alertas)


def resumo_inteligente_loja(formatador=str):
    hoje = datetime.now().strftime("%d/%m/%Y")
    mes = datetime.now().strftime("/%m/%Y")
    vendas_hoje = resumo_vendas_periodo(hoje)
    vendas_mes = resumo_vendas_periodo(mes)
    baixo = contar_estoque_baixo()
    clientes = query_db("SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1")[0][0]
    top = produto_campeao()
    top_txt = f"{top[0]} ({top[1]} un)" if top else "ainda sem campeão claro"
    return (
        "Leitura inteligente da loja agora:\n"
        f"- Hoje: {vendas_hoje[0]} venda(s), {formatador(vendas_hoje[1])}.\n"
        f"- Mês atual: {vendas_mes[0]} venda(s), {formatador(vendas_mes[1])}.\n"
        f"- Estoque baixo/crítico: {baixo} produto(s).\n"
        f"- Clientes cadastrados: {clientes}.\n"
        f"- Produto campeão no histórico: {top_txt}.\n\n"
        "Minha sugestão: se o movimento estiver parado, publique um story com o produto campeão ou chame clientes pelo WhatsApp."
    )


def prioridades_do_dia():
    prioridades = []
    if not obter_caixa_id_ativo():
        prioridades.append("Abrir o caixa antes de vender.")
    baixo = estoque_baixo(5)
    if baixo:
        prioridades.append("Conferir estoque baixo: " + ", ".join([f"{b[0]} ({b[1]} un)" for b in baixo]))
    nivers = query_db(
        "SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? LIMIT 5",
        (f"%{datetime.now().strftime('%d/%m')}%",),
    )
    if nivers:
        prioridades.append("Enviar felicitações para aniversariantes: " + ", ".join([n[0] for n in nivers]))
    if not prioridades:
        prioridades.append("Criar uma chamada simples para Instagram/WhatsApp com um produto bonito da loja.")
    return "Prioridades que eu recomendo agora:\n- " + "\n- ".join(prioridades)


def produtos_sem_giro_texto():
    res = produtos_sem_giro(15)
    if not res:
        return "Não encontrei produtos totalmente sem venda registrada."
    linhas = ["Produtos sem giro registrado nas vendas:"]
    for nome, qtd, categoria in res:
        linhas.append(f"- {nome} | {qtd} un | {categoria}")
    linhas.append("\nSugestão: transforme 1 ou 2 desses itens em destaque de story ou kit promocional.")
    return "\n".join(linhas)


def clientes_incompletos_texto():
    res = clientes_incompletos(20)
    if not res:
        return "Os principais cadastros de clientes parecem completos."
    linhas = ["Clientes com cadastro incompleto:"]
    for nome, telefone, cpf in res:
        faltas = []
        if not telefone:
            faltas.append("WhatsApp")
        if not cpf:
            faltas.append("CPF")
        linhas.append(f"- {nome}: falta {', '.join(faltas)}")
    return "\n".join(linhas)


def diagnostico_banco_operacional(tabelas_obrigatorias):
    from isis.commands import diagnostico_tabelas

    problemas = diagnostico_tabelas(tabelas_obrigatorias)
    abertos = caixa_abertos_count()
    if abertos > 1:
        problemas.append(f"Existem {abertos} caixas abertos ao mesmo tempo.")
    nulos = produtos_cadastro_incompleto()
    if nulos:
        problemas.append(f"Existem {nulos} produto(s) com cadastro incompleto.")
    return problemas


def reparar_banco_e_indices(init_db_func, backup_func):
    from isis.commands import criar_indices_seguros, normalizar_nulos_basicos

    alteracoes = []
    init_db_func()
    alteracoes.append("Estrutura principal do banco conferida pelo init_db().")
    criar_indices_seguros()
    alteracoes.append("Indices de desempenho criados/conferidos.")
    normalizar_nulos_basicos()
    alteracoes.append("Valores nulos basicos normalizados.")
    backup_func()
    alteracoes.append("Backup de seguranca realizado.")
    return alteracoes



# --- MELHORIAS DE PESQUISA WEB: FORNECEDORES, PREÇOS, CLIMA E RESUMO ---
def classificar_pesquisa_web(consulta):
    p = normalizar_texto(consulta)
    if any(t in p for t in ["clima", "tempo", "previsao", "chuva", "temperatura"]):
        return "clima"
    if any(t in p for t in ["shopee", "mercado livre", "mercadolivre", "menor preco", "melhor preco", "preco", "comprar"]):
        return "preco"
    if any(t in p for t in ["fornecedor", "fornecedores", "atacado", "revenda", "distribuidor", "distribuidores"]):
        return "fornecedor"
    if any(t in p for t in ["evento", "eventos", "show", "feira", "final de semana"]):
        return "eventos"
    return "geral"


def preparar_consulta_web(pergunta):
    consulta = limpar_consulta_web(pergunta)
    tipo = classificar_pesquisa_web(pergunta)

    if tipo == "clima" and "pinhalzinho" not in normalizar_texto(consulta):
        consulta = consulta + " Pinhalzinho SC previsão do tempo"

    if tipo == "preco":
        p = normalizar_texto(consulta)

        if "shopee" in p:
            consulta = "site:shopee.com.br " + consulta.replace("shopee", "").strip()

        elif "mercado livre" in p or "mercadolivre" in p:
            consulta = (
                "site:mercadolivre.com.br "
                + consulta.replace("mercado livre", "").replace("mercadolivre", "").strip()
            )

        else:
            consulta = consulta + " Shopee Mercado Livre preço"

    if tipo == "fornecedor":
        p = normalizar_texto(consulta)
        if "atacado" not in p and "revenda" not in p:
            consulta = consulta + " atacado revenda Brasil"

    if tipo == "eventos" and "pinhalzinho" not in normalizar_texto(consulta):
        consulta = consulta + " Pinhalzinho SC"

    return " ".join(consulta.split()), tipo


def pontuar_resultado_web(resultado, tipo):
    titulo = normalizar_texto(resultado.get("title", ""))
    link = normalizar_texto(resultado.get("href", ""))
    corpo = normalizar_texto(resultado.get("body", ""))
    texto = f"{titulo} {link} {corpo}"
    pontos = 0

    if tipo == "fornecedor":
        for termo in ["atacado", "revenda", "distribuidor", "fabrica", "fornecedor", "catalogo", "whatsapp"]:
            if termo in texto:
                pontos += 3
        for termo in ["shopify", "como vender", "guia", "blog"]:
            if termo in texto:
                pontos -= 4

    elif tipo == "preco":
        for termo in ["shopee", "mercado livre", "mercadolivre", "preco", "comprar", "loja", "frete"]:
            if termo in texto:
                pontos += 3
        for termo in ["bitget", "token", "criptomoeda", "como vender"]:
            if termo in texto:
                pontos -= 6

    elif tipo == "clima":
        for termo in ["clima", "tempo", "previsao", "temperatura", "chuva", "weather"]:
            if termo in texto:
                pontos += 3

    elif tipo == "eventos":
        for termo in ["evento", "agenda", "show", "feira", "pinhalzinho", "sc"]:
            if termo in texto:
                pontos += 3

    else:
        for termo in ["loja", "site", "oficial", "comprar", "brasil"]:
            if termo in texto:
                pontos += 1

    if link.startswith("https"):
        pontos += 1
    return pontos


def resumir_resultados_web(resultados, consulta, tipo):
    if not resultados:
        return (
            "Tentei pesquisar na internet, mas não encontrei resultado claro agora.\n"
            f"Consulta usada: {consulta}\n\n"
            "Dica: tente especificar melhor, por exemplo: 'fornecedor de velas aromáticas atacado' ou 'preço de incenso Satya Shopee'."
        )

    resultados_ordenados = sorted(
        resultados,
        key=lambda r: pontuar_resultado_web(r, tipo),
        reverse=True
    )[:5]

    if tipo == "fornecedor":
        abertura = "🌿 Analisei os resultados e separei opções que parecem úteis para cotação/fornecimento."
        recomendacao = (
            "\n\nMinha recomendação para a Mística:\n"
            "- priorize sites com atacado, CNPJ, WhatsApp e política clara de frete;\n"
            "- compare preço por unidade, pedido mínimo e prazo de entrega;\n"
            "- antes de comprar grande quantidade, faça um pedido pequeno de teste."
        )
    elif tipo == "preco":
        abertura = "🌿 Busquei opções com foco em preço, compra online e comparação."
        recomendacao = (
            "\n\nMinha recomendação:\n"
            "- confira reputação do vendedor, frete e prazo;\n"
            "- compare preço unitário, não apenas o valor do anúncio;\n"
            "- evite comprar muito estoque antes de testar a saída na loja."
        )
    elif tipo == "clima":
        abertura = "🌦️ Pesquisei informações de clima/previsão."
        recomendacao = (
            "\n\nDica para a loja:\n"
            "- se estiver frio ou chuvoso, destaque velas, incensos, essências e itens de aconchego nos stories."
        )
    elif tipo == "eventos":
        abertura = "📍 Pesquisei eventos e movimentações locais."
        recomendacao = (
            "\n\nDica para a Mística:\n"
            "- em dias de evento, publique stories com produtos de presente, proteção e aromatização."
        )
    else:
        abertura = "🌐 Pesquisei na internet e organizei os principais resultados."
        recomendacao = "\n\nDica: confira a fonte, preço, prazo, reputação e segurança antes de tomar decisão."

    linhas = [f"{abertura}\n", f"Consulta usada: {consulta}\n", "🏆 Principais resultados:\n"]
    for i, r in enumerate(resultados_ordenados, 1):
        titulo = r.get("title", "Resultado")
        link = r.get("href", "")
        corpo = r.get("body", "")
        corpo = corpo[:260] + "..." if len(corpo) > 260 else corpo
        linhas.append(f"{i}. {titulo}\n{link}\n{corpo}\n")

    return "\n".join(linhas) + recomendacao


# --- PESQUISA WEB GRATUITA DA ISIS (DDGS) ---
def limpar_consulta_web(pergunta):
    """Remove palavras de comando e deixa apenas o termo que deve ser pesquisado."""
    consulta = str(pergunta or "").strip()
    consulta = re.sub(r"(?i)\b(isis|bruxinha)\b[:, ]*", "", consulta).strip()
    comandos = [
        "pesquise na internet", "pesquisar na internet", "pesquisa na internet",
        "pesquise sobre", "pesquisa sobre", "pesquisar sobre",
        "procure por", "procurar por", "busque por", "buscar por",
        "encontre", "pesquise", "pesquisa", "pesquisar",
        "procure", "procurar", "busque", "buscar", "localize", "localizar",
    ]
    consulta_norm = normalizar_texto(consulta)
    for cmd in comandos:
        cmd_norm = normalizar_texto(cmd)
        if consulta_norm.startswith(cmd_norm):
            consulta = consulta[len(cmd):].strip(" :,-.")
            break
    return consulta or str(pergunta or "").strip()


def deve_pesquisar_web(pergunta):
    p = normalizar_texto(pergunta)
    termos = [
        "pesquise", "pesquisa", "pesquisar", "procure", "procurar",
        "busque", "buscar", "encontre", "localize", "localizar",
        "internet", "google", "site", "sites", "fornecedor", "fornecedores",
        "shopee", "mercado livre", "melhor preco", "preco na internet",
    ]
    return any(t in p for t in termos)


def pesquisar_web(consulta, max_resultados=8):
    """Pesquisa gratuita usando ddgs. Instale com: pip install ddgs"""
    consulta_preparada, tipo = preparar_consulta_web(consulta)

    try:
        from ddgs import DDGS
    except Exception:
        return (
            "🌐 A pesquisa web ainda não está instalada neste Python.\n\n"
            "Abra o PowerShell e rode:\n"
            "pip install ddgs"
        )
    try:
        resultados = []

        with DDGS() as ddgs:
            for r in ddgs.text(
                consulta_preparada,
                max_results=int(max_resultados)
            ):
                if isinstance(r, dict):
                    resultados.append(r)

        return resumir_resultados_web(
            resultados,
            consulta_preparada,
            tipo
        )

    except Exception as e:
        return f"Tentei pesquisar, mas encontrei um erro: {e}"


def processar_comando_inteligente(pergunta, usuario=None):
    from isis.assistant import IsisAssistant
    from repositories import isis_logs

    nome = usuario.get("nome", "Sistema") if isinstance(usuario, dict) else "Sistema"

    # Pesquisa web antes da resposta padrão da Isis.
    # Assim comandos como "pesquisa sobre sites que vendem velas" já funcionam.
    try:
        if deve_pesquisar_web(pergunta):
            texto = pesquisar_web(pergunta)
            try:
                isis_logs.registrar(pergunta, "pesquisa_web", nome, texto)
            except Exception:
                pass
            return {"handled": True, "modo": "pesquisa_web", "texto": texto}
    except Exception:
        pass

    try:
        resposta = IsisAssistant(usuario).responder(pergunta)
        isis_logs.registrar(pergunta, resposta.get("modo", "indefinido"), nome, resposta.get("texto", ""))
        return resposta
    except Exception as e:
        isis_logs.registrar(pergunta, "erro_isis", nome, "", str(e))
        return {"handled": True, "modo": "erro", "texto": f"A Isis encontrou um erro ao responder: {e}"}
