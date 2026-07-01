import re
import io
import urllib.request
import webbrowser
from datetime import datetime
from PIL import Image, ImageTk

from database import query_db
from reports.estoque_report import contar_estoque_baixo, estoque_baixo, produtos_cadastro_incompleto, produtos_para_giro, produtos_sem_giro
from reports.financeiro_report import contas_para_alerta, contas_pendentes_resumo
from reports.vendas_report import lucro_bruto_itens_periodo, produto_campeao, resumo_vendas_periodo, total_vendido_produto
from services.caixa_service import caixa_abertos_count, obter_caixa_id_ativo, status_caixa_aberto

# Histórico global de links para suporte a comandos de voz e interface
_historico_links_recente = []


# ==========================================
# 1. FUNÇÕES DO BANCO DE DADOS E UTILITÁRIOS
# ==========================================

def consulta_sql(sql, params=()):
    """Executa consultas de forma segura contra SQL Injection."""
    try:
        return query_db(sql, params)
    except Exception as e:
        print(f"[Erro de Banco] Falha na consulta SQL: {e}")
        raise e


def normalizar_texto(texto):
    """Remove acentuação e caracteres especiais para melhor detecção de intenções."""
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
        6: "Dica de inverno: destaque velas aromáticas, essências amadeiradas e incensos de canela ou baunilha.",
        7: "Dica de inverno: monte kits de aconchego com vela, incensário e aroma especial.",
        8: "Dica de inverno: utilize stories para exibir produtos que trazem sensação de aquecimento ao ambiente.",
        11: "Dica de fim de ano: destaque banhos de ervas, pirita, citrino, incensos de sete ervas e velas brancas.",
        12: "Dica de fim de ano: priorize kits prontos e embalagens decoradas para presente.",
        5: "Dica de Dia das Mães: prepare kits com sabonetes artesanais, quartzo rosa, incensos florais e difusores.",
    }
    return sazonais.get(int(mes), "Dica sazonal: promova renovação e equilíbrio destacando sálvia branca, ametista e aromas suaves.")


# ==========================================
# 2. INTEGRAÇÃO E BUSCA WEB (DUAL-IMPORT)
# ==========================================

def limpar_consulta_web(pergunta):
    """Prepara a string removendo termos operacionais da Isis."""
    consulta = str(pergunta or "").strip()
    consulta = re.sub(r"(?i)\b(isis|bruxinha)\b[:, ]*", "", consulta).strip()
    comandos = [
        "pesquise na internet", "pesquisar na internet", "pesquisa na internet",
        "pesquise sobre", "pesquisa sobre", "pesquisar sobre",
        "procure por", "procurar por", "busque por", "buscar por",
        "encontre", "pesquise", "pesquisa", "pesquisar",
        "procure", "procurar", "busque", "buscar", "localize", "localizar",
        "clima", "tempo", "previsao", "como esta o clima em", "previsao do tempo para"
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
        "clima", "tempo", "previsao", "chuva", "frio", "calor",
        "evento", "eventos", "final de semana", "fim de semana", "movimento na cidade",
        "atacado", "revenda", "distribuidor", "fabricante", "fabrica", "preco", "comparar",
        "link", "links", "imagem", "imagens", "foto", "fotos"
    ]
    return any(t in p for t in termos)


def carregar_classe_ddgs():
    """Tenta carregar o módulo DDGS sob as duas nomenclaturas comuns."""
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            return DDGS
        except ImportError:
            return None


def obter_resultados_pesquisa(consulta, max_resultados=8):
    """Realiza a chamada interna ao motor de busca e retorna dicionários padronizados."""
    DDGS_class = carregar_classe_ddgs()
    if not DDGS_class:
        return []

    consulta_limpa = limpar_consulta_web(consulta)
    try:
        resultados = []
        with DDGS_class() as ddgs:
            for r in ddgs.text(consulta_limpa, max_results=int(max_resultados)):
                resultados.append({
                    "title": r.get("title", "Sem Título"),
                    "href": r.get("href", ""),
                    "body": r.get("body", "")
                })
        return resultados
    except Exception as e:
        print(f"[DDGS API] Erro ao obter dados do mecanismo de busca: {e}")
        return []


def obter_imagens_pesquisa(consulta, max_resultados=5):
    """Realiza a busca de imagens relacionadas ao produto ou termo desejado."""
    DDGS_class = carregar_classe_ddgs()
    if not DDGS_class:
        return []

    consulta_limpa = limpar_consulta_web(consulta)
    try:
        imagens = []
        with DDGS_class() as ddgs:
            for r in ddgs.images(consulta_limpa, max_results=int(max_resultados)):
                if r.get("image"):
                    imagens.append({
                        "title": r.get("title", "Imagem"),
                        "url": r.get("image"),
                        "thumbnail": r.get("thumbnail", "")
                    })
        return imagens
    except Exception as e:
        print(f"[DDGS Imagens] Falha ao obter imagens para '{consulta_limpa}': {e}")
        return []


# ==========================================
# 3. EXTRAÇÃO DE LINKS E INTERFACE (CTk)
# ==========================================

def abrir_link_no_navegador(url):
    """Abre uma URL externa explicitamente em uma nova aba do navegador padrão."""
    try:
        url_limpa = url.strip()
        if url_limpa.startswith("www."):
            url_limpa = "http://" + url_limpa
        
        webbrowser.open_new_tab(url_limpa)
        return True
    except Exception as e:
        print(f"[Navegador] Falha ao abrir link em nova aba: {e}")
        return False


def extrair_links(texto):
    """Localiza todos os endereços web válidos presentes em uma string."""
    padrao = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
    urls = re.findall(padrao, texto)
    normalizados = []
    for u in urls:
        if u.endswith(".") or u.endswith(",") or u.endswith(";"):
            u = u[:-1]
        if u.startswith("www."):
            normalizados.append("http://" + u)
        else:
            normalizados.append(u)
    return list(dict.fromkeys(normalizados))


def criar_botoes_de_acao(texto, lista_imagens=None):
    """
    Retorna uma estrutura de metadados para criação de botões de ação física na interface.
    Associa imagens correspondentes a cada link gerado (se disponíveis).
    """
    urls = extrair_links(texto)
    botoes = []
    for idx, url in enumerate(urls, start=1):
        url_lower = url.lower()
        tipo = "default"
        label = f"Abrir site {idx}"
        
        imagem_url = ""
        if lista_imagens and (idx - 1) < len(lista_imagens):
            imagem_url = lista_imagens[idx - 1].get("url", "")
        
        if "shopee.com.br" in url_lower or "mercadolivre.com" in url_lower:
            tipo = "compras"
            label = f"Visualizar/Comprar {idx}"
        elif "whatsapp.com" in url_lower or "api.whatsapp" in url_lower:
            tipo = "whatsapp"
            label = f"Chamar WhatsApp {idx}"
            
        botoes.append({
            "index": idx,
            "url": url,
            "tipo": tipo,
            "texto_botao": label,
            "imagem_url": imagem_url
        })
    return botoes


def renderizar_resposta_na_interface(textbox_widget, dados_resposta):
    """
    Renderiza os dados retornados pela Isis dentro de um CTkTextbox ou Text do Tkinter.
    Carrega as imagens inline e converte URLs em links clicáveis automaticamente.
    """
    textbox_widget.configure(state="normal")
    textbox_widget.delete("1.0", "end")
    
    texto = dados_resposta.get("texto", "")
    links_meta = dados_resposta.get("links", [])
    
    # Dicionário auxiliar para mapeamento rápido de imagens associadas às URLs
    url_para_imagem = {item["url"]: item["imagem_url"] for item in links_meta if item.get("imagem_url")}
    
    # Criação do cache interno de imagens para evitar garbage collection
    if not hasattr(textbox_widget, "_tk_images_cache"):
        textbox_widget._tk_images_cache = []
        
    tokens = re.split(r'(\s+)', texto)
    for token in tokens:
        if re.match(r'^(https?://[^\s<>"]+|www\.[^\s<>"]+)', token):
            url_limpa = token
            ponto_final = ""
            if url_limpa.endswith(".") or url_limpa.endswith(",") or url_limpa.endswith(";"):
                ponto_final = url_limpa[-1]
                url_limpa = url_limpa[:-1]
            
            tag_unica = f"link_{hash(url_limpa)}"
            
            textbox_widget.insert("end", url_limpa, tag_unica)
            textbox_widget.tag_config(tag_unica, foreground="#1f538d", underline=True)
            
            # Vinculação de eventos de hover e clique
            textbox_widget.tag_bind(tag_unica, "<Enter>", lambda e, w=textbox_widget: w.configure(cursor="hand2"))
            textbox_widget.tag_bind(tag_unica, "<Leave>", lambda e, w=textbox_widget: w.configure(cursor=""))
            textbox_widget.tag_bind(tag_unica, "<Button-1>", lambda e, url=url_limpa: abrir_link_no_navegador(url))
            
            # Carregamento e inserção física da imagem pareada
            imagem_url = url_para_imagem.get(url_limpa) or url_para_imagem.get("http://" + url_limpa)
            if imagem_url:
                try:
                    req = urllib.request.Request(imagem_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        img_data = response.read()
                    
                    img_raw = Image.open(io.BytesIO(img_data))
                    img_raw.thumbnail((160, 160))  # Redimensionamento para o tamanho do chat
                    
                    tk_img = ImageTk.PhotoImage(img_raw)
                    textbox_widget._tk_images_cache.append(tk_img)  # Cache de referência
                    
                    textbox_widget.insert("end", "\n")
                    textbox_widget.image_create("end", image=tk_img)
                    textbox_widget.insert("end", "\n")
                except Exception as img_err:
                    print(f"[Aviso de Imagem] Não foi possível carregar a miniatura {imagem_url}: {img_err}")
            
            if ponto_final:
                textbox_widget.insert("end", ponto_final)
        else:
            textbox_widget.insert("end", token)
            
    textbox_widget.configure(state="disabled")


# ==========================================
# 4. PARSERS E FORMATADORES DE RESPOSTA
# ==========================================

def formatar_resultados_com_imagens(consulta, resultados, imagens):
    """Gera o texto final contendo links de texto e de imagem formatados em Markdown."""
    if not resultados:
        return f"Não encontrei resultados claros para '{consulta}' no momento."
        
    linhas = [
        f"🌿 Busquei na internet por: **{consulta}**",
        "🏆 **Principais resultados encontrados:**\n"
    ]
    
    for idx, r in enumerate(resultados, start=1):
        linhas.append(f"**{idx}. {r['title']}**")
        linhas.append(f"🔗 Link: {r['href']}")
        
        if idx - 1 < len(imagens):
            img_url = imagens[idx - 1].get("url", "")
            if img_url:
                linhas.append(f"🖼️ [Visualizar Imagem]({img_url})")
                
        linhas.append(f"📝 {r['body']}\n")
        
    linhas.append(
        "Minha recomendação:\n"
        "- Confira a reputação do vendedor, frete e prazo de entrega;\n"
        "- Compare o valor unitário das opções antes de fechar;\n"
        "- Faça pedidos de teste pequenos antes de adquirir grandes quantidades para a Mística."
    )
    return "\n".join(linhas)


def parse_meteo(texto_pesquisa):
    """Tenta identificar temperatura, umidade e condição nos snippets."""
    temp_match = re.search(r"(\d{1,2})\s*(?:°C|graus|C\b)", texto_pesquisa, re.IGNORECASE)
    hum_match = re.search(r"(\d{1,3})\s*%\s*(?:de umidade|umidade|humidade)?", texto_pesquisa, re.IGNORECASE)
    
    condicoes = ["chuva", "chuvoso", "tempestade", "nublado", "encoberto", "sol", "limpo", "claro", "parcialmente nublado", "garoa"]
    condicao_detectada = "Não identificada pelas fontes abertas"
    for cond in condicoes:
        if cond in texto_pesquisa.lower():
            condicao_detectada = cond.capitalize()
            break
            
    temperatura = f"{temp_match.group(1)}°C" if temp_match else "Não identificada"
    umidade = f"{hum_match.group(1)}%" if hum_match else "Não identificada"
    return temperatura, condicao_detectada, umidade


def obter_sugestao_mistica(condicao, temperatura):
    cond = condicao.lower()
    temp_val = None
    try:
        match = re.search(r"(\d+)", temperatura)
        if match:
            temp_val = int(match.group(1))
    except Exception:
        pass

    if "chuva" in cond or "chuvoso" in cond or "tempestade" in cond or "garoa" in cond:
        return "Dias chuvosos combinam com incensos quentes de Canela, Baunilha ou Cravo. Aproveite para sugerir velas aromáticas para afastar a umidade fria e trazer aconchego místico ao lar."
    elif "nublado" in cond or "encoberto" in cond:
        return "Tempo nublado sintoniza bem com purificação interna. Sugira incensos de Alecrim para foco mental e cristais de Quartzo Verde ou Ametista para equilibrar o ambiente."
    elif temp_val is not None and temp_val < 18:
        return "O frio convida ao recolhimento. Destaque velas aromáticas quentes, defumadores naturais de ervas tradicionais e kits místicos para aquecer e proteger a casa."
    elif temp_val is not None and temp_val > 27:
        return "O calor pede purificação leve! Promova banhos de ervas refrescantes (Hortelã, Eucalipto), incensos florais de Alfazema ou Sálvia Branca, e difusores cítricos."
    else:
        return "Clima ameno e favorável. Perfeito para rituais de prosperidade. Promova incensos de Sete Ervas, Palo Santo e cristais como Pirita e Citrino para ativar o fluxo de abundância."


def analisar_estoque_para_reposicao():
    """Avalia o estado de estoque cruzando com as vendas dos últimos 30 dias (Requisito 6)."""
    urgentes, acompanhar, estaveis = [], [], []

    try:
        dados_giro = produtos_para_giro()
    except Exception as e:
        return f"Não foi possível ler as métricas de giro do estoque: {e}"

    for cod, nome, qtd_atual, est_min, categoria in dados_giro:
        try:
            total_vendido = int(total_vendido_produto(cod) or 0)
        except Exception:
            total_vendido = 0

        qtd_atual = int(qtd_atual or 0)
        est_min = int(est_min or 0)

        item_data = {
            "nome": nome,
            "qtd": qtd_atual,
            "min": est_min,
            "vendas": total_vendido
        }

        if qtd_atual <= est_min or (qtd_atual == 0 and est_min > 0):
            urgentes.append(item_data)
        elif qtd_atual <= est_min * 1.5:
            acompanhar.append(item_data)
        else:
            estaveis.append(item_data)

    urgentes.sort(key=lambda x: x["vendas"], reverse=True)
    acompanhar.sort(key=lambda x: x["vendas"], reverse=True)

    linhas = ["📋 **Análise de Giro de Estoque e Reposição**\n"]
    
    if urgentes:
        linhas.append("🚨 **REPOR URGENTE (Estoque abaixo do mínimo ou zerado):**")
        for item in urgentes[:15]:
            linhas.append(f"• {item['nome']} (Estoque: {item['qtd']} | Mín: {item['min']} | Vendas 30d: {item['vendas']})")
        if len(urgentes) > 15:
            linhas.append(f"  *(e mais {len(urgentes) - 15} itens listados como críticos)*")
        linhas.append("")

    if acompanhar:
        linhas.append("⚠️ **ACOMPANHAR (Estoque próximo ao limite mínimo):**")
        for item in acompanhar[:10]:
            linhas.append(f"• {item['nome']} (Estoque: {item['qtd']} | Mín: {item['min']} | Vendas 30d: {item['vendas']})")
        if len(acompanhar) > 10:
            linhas.append(f"  *(e mais {len(acompanhar) - 10} itens sob atenção)*")
        linhas.append("")

    if not urgentes and not acompanhar:
        linhas.append("✅ **Estoque Estável:** Todos os produtos monitorados apresentam níveis seguros de armazenamento.")

    return "\n".join(linhas)


# ==========================================
# 5. PROCESSADOR CENTRAL E INTENCIONALIDADE
# ==========================================

def processar_comando_inteligente(pergunta, usuario=None):
    from isis.assistant import IsisAssistant
    from repositories import isis_logs

    nome = usuario.get("nome", "Sistema") if isinstance(usuario, dict) else "Sistema"
    p = normalizar_texto(pergunta)

    # 1. Tratamento preventivo para perguntas vagas ("me da o link", "buscar imagem")
    consulta_limpa = limpar_consulta_web(pergunta)
    palavras_consulta = [w for w in consulta_limpa.split() if len(w) > 2]
    termos_vagos = ["link", "links", "imagem", "imagens", "foto", "fotos", "site", "sites", "pesquisa", "pesquise"]
    
    if all(w in termos_vagos for w in palavras_consulta) or len(palavras_consulta) == 0:
        texto_retorno = (
            "🌿 Entendi que você deseja links ou imagens! Para que eu possa te ajudar de forma precisa, "
            "por favor me especifique o produto ou termo que deseja buscar.\n\n"
            "**Exemplos de como me pedir:**\n"
            "• *'pesquise na internet imagem de pedra pirita'*\n"
            "• *'link para comprar incenso de sândalo na shopee'*\n"
            "• *'comparar preço de velas aromáticas de canela'*"
        )
        return {"handled": True, "modo": "ajuda_busca", "texto": texto_retorno, "links": []}

    # A. Consulta de Meteorologia (Requisito 1)
    if any(termo in p for termo in ["clima", "tempo", "previsao", "chuva", "frio", "calor", "temperatura"]):
        is_pinhalzinho = "pinhalzinho" in p
        termo_busca = "previsao do tempo Pinhalzinho SC" if is_pinhalzinho else f"previsao do tempo {limpar_consulta_web(pergunta)}"
        
        resultados_brutos = obter_resultados_pesquisa(termo_busca, max_resultados=4)
        texto_pesquisa = " ".join([r["body"] for r in resultados_brutos])
        
        if is_pinhalzinho:
            temp, cond, umid = parse_meteo(texto_pesquisa)
            sugestao = obter_sugestao_mistica(cond, temp)
            
            if temp == "Não identificada" and cond == "Não identificada pelas fontes abertas" and umid == "Não identificada":
                linhas_fallback = [
                    "Não consegui capturar dados estruturados exatos para Pinhalzinho/SC. No entanto, localizei as seguintes previsões disponíveis na internet:",
                    ""
                ]
                for r in resultados_brutos[:3]:
                    linhas_fallback.append(f"🌐 **{r['title']}**\n{r['href']}\n")
                linhas_fallback.append("💡 Sugestão para a Mística: Mantenha incensos purificadores e velas aromáticas em destaque na recepção da loja hoje.")
                texto_retorno = "\n".join(linhas_fallback)
            else:
                texto_retorno = (
                    "🌦️ Pinhalzinho/SC agora\n"
                    f"Temperatura: {temp}\n"
                    f"Condição: {cond}\n"
                    f"Umidade: {umid}\n"
                    "Previsão: Conforme principais canais meteorológicos integrados.\n"
                    "Fonte: DDGS / Pesquisa de canais públicos.\n\n"
                    f"💡 Sugestão para a Mística: {sugestao}"
                )
        else:
            if resultados_brutos:
                texto_retorno = f"Resultados encontrados de previsão meteorológica para '{limpar_consulta_web(pergunta)}':\n\n"
                for r in resultados_brutos[:3]:
                    texto_retorno += f"🌐 **{r['title']}**\n{r['href']}\n{r['body']}\n\n"
            else:
                texto_retorno = "Não consegui obter dados meteorológicos para essa localidade no momento."

        try:
            isis_logs.registrar(pergunta, "clima", nome, texto_retorno)
        except Exception:
            pass
        return {"handled": True, "modo": "clima", "texto": texto_retorno, "links": criar_botoes_de_acao(texto_retorno)}

    # B. Pesquisa de Fornecedores Atacado (Requisito 4)
    if any(termo in p for termo in ["fornecedor", "fornecedores", "atacado", "revenda", "distribuidor", "fabricante", "fabrica"]):
        item_pesquisa = limpar_consulta_web(pergunta)
        termo_busca = f"{item_pesquisa} fornecedor atacado distribuidor fabrica CNPJ contato whatsapp"
        
        resultados = obter_resultados_pesquisa(termo_busca, max_resultados=6)
        imagens = obter_imagens_pesquisa(item_pesquisa, max_resultados=len(resultados))
        
        if not resultados:
            texto_retorno = f"Não encontrei anúncios públicos ou registros de fornecedores de atacado para '{item_pesquisa}'."
        else:
            rankings = []
            for item in resultados:
                snippet = (item["title"] + " " + item["body"]).lower()
                score = 0
                if "cnpj" in snippet: score += 3
                if "atacado" in snippet: score += 3
                if "whatsapp" in snippet or "whats" in snippet: score += 2
                if "distribuidora" in snippet or "distribuidor" in snippet: score += 2
                if "fabrica" in snippet or "fabricante" in snippet: score += 1
                rankings.append((score, item))
            
            rankings.sort(key=lambda x: x[0], reverse=True)
            top_fornecedores = rankings[:3]
            
            linhas = [f"📋 **Ranking de Fornecedores Atacado para '{item_pesquisa}':**\n"]
            titulos_rank = ["Melhor opção aparente", "Segunda opção", "Terceira opção"]
            
            for idx, (score, info) in enumerate(top_fornecedores):
                rank_label = titulos_rank[idx] if idx < len(titulos_rank) else f"{idx+1}ª Opção"
                linhas.append(f"**{idx+1}. {rank_label}**")
                linhas.append(f"🏢 {info['title']}")
                linhas.append(f"🔗 Link: {info['href']}")
                
                if idx < len(imagens):
                    linhas.append(f"🖼️ [Visualizar Imagem]({imagens[idx]['url']})")
                    
                linhas.append(f"📝 Detalhes: {info['body'][:160]}...\n")
                
            linhas.append("💡 **Recomendação:** Faça um pedido pequeno de teste antes de comprar grande quantidade.")
            texto_retorno = "\n".join(linhas)

        try:
            isis_logs.registrar(pergunta, "fornecedores", nome, texto_retorno)
        except Exception:
            pass
        return {"handled": True, "modo": "fornecedores", "texto": texto_retorno, "links": criar_botoes_de_acao(texto_retorno, imagens)}

    # C. Comparação de Preços em Marketplaces (Requisito 5)
    if any(termo in p for termo in ["preco", "menor preco", "shopee", "mercado livre", "comparar"]):
        item_pesquisa = limpar_consulta_web(pergunta)
        termo_busca = f"{item_pesquisa} site:shopee.com.br OR site:mercadolivre.com.br"
        
        resultados = obter_resultados_pesquisa(termo_busca, max_resultados=8)
        imagens = obter_imagens_pesquisa(item_pesquisa, max_resultados=len(resultados))
        
        if not resultados:
            texto_retorno = f"Não encontrei referências de preços para '{item_pesquisa}' nas plataformas monitoradas."
        else:
            shopee_results = []
            ml_results = []
            for item in resultados:
                link = item["href"].lower()
                if "shopee.com.br" in link:
                    shopee_results.append(item)
                elif "mercadolivre.com" in link:
                    ml_results.append(item)
            
            linhas = [f"🛍️ **Comparação de Preços para '{item_pesquisa}':**\n"]
            
            if shopee_results:
                linhas.append("🧡 **Resultados encontrados na Shopee:**")
                for idx, item in enumerate(shopee_results[:3]):
                    linhas.append(f"• **Produto:** {item['title']}")
                    linhas.append(f"  **Plataforma:** Shopee")
                    linhas.append(f"  **Link:** {item['href']}")
                    if idx < len(imagens):
                        linhas.append(f"  **Imagem do Produto:** {imagens[idx]['url']}")
                    linhas.append(f"  **Observação:** {item['body'][:120]}...\n")
            
            if ml_results:
                linhas.append("💛 **Resultados encontrados no Mercado Livre:**")
                for idx, item in enumerate(ml_results[:3]):
                    img_idx = idx + len(shopee_results)
                    linhas.append(f"• **Produto:** {item['title']}")
                    linhas.append(f"  **Plataforma:** Mercado Livre")
                    linhas.append(f"  **Link:** {item['href']}")
                    if img_idx < len(imagens):
                        linhas.append(f"  **Imagem do Produto:** {imagens[img_idx]['url']}")
                    linhas.append(f"  **Observação:** {item['body'][:120]}...\n")
                    
            if not shopee_results and not ml_results:
                linhas.append("Resultados gerais em sites públicos de vendas:")
                for idx, item in enumerate(resultados[:4]):
                    linhas.append(f"• **Produto:** {item['title']}")
                    linhas.append(f"  **Link:** {item['href']}")
                    if idx < len(imagens):
                        linhas.append(f"  **Imagem:** {imagens[idx]['url']}")
                    linhas.append(f"  **Observação:** {item['body'][:120]}...\n")
                    
            linhas.append("⚠️ **Aviso:** Lembre-se sempre de conferir o custo do frete, as avaliações do vendedor e a reputação da loja antes de efetuar qualquer pagamento.")
            texto_retorno = "\n".join(linhas)

        try:
            isis_logs.registrar(pergunta, "comparacao_precos", nome, texto_retorno)
        except Exception:
            pass
        return {"handled": True, "modo": "comparacao_precos", "texto": texto_retorno, "links": criar_botoes_de_acao(texto_retorno, imagens)}

    # D. Eventos Locais e Sugestões de Campanhas (Requisito 7)
    if any(termo in p for termo in ["evento", "eventos", "final de semana", "fim de semana", "movimento na cidade"]):
        is_pinhalzinho = "pinhalzinho" in p or "cidade" in p
        termo_busca = "eventos Pinhalzinho SC final de semana agenda" if is_pinhalzinho else f"eventos {limpar_consulta_web(pergunta)}"
        
        resultados_brutos = obter_resultados_pesquisa(termo_busca, max_resultados=4)
        texto_pesquisa = " ".join([r["body"] for r in resultados_brutos]).lower()
        
        sugestao_mkt = "Sugerimos preparar posts focados em autocuidado e rituais relaxantes para o fim de semana, como velas de lavanda e banhos de sais com ervas calmantes."
        if any(x in texto_pesquisa for x in ["feira", "expo", "festival", "festa", "rodeio", "aniversario"]):
            sugestao_mkt = "Como haverá maior circulação de pessoas na cidade, crie uma vitrine temática atraente ou prepare kits portáteis (como chaveiros de pedras de proteção, mini incensários ou roll-ons de aromaterapia de bolso) focando em visitantes e turistas."
        elif any(x in texto_pesquisa for x in ["show", "balada", "festa noturna", "show musical"]):
            sugestao_mkt = "Recomende cristais de proteção energética (Turmalina Negra, Olho de Tigre) e banhos de ervas para descarrego energético após as comemorações."
            
        texto_retorno = "📅 **Eventos e Movimentos de Cidade Identificados:**\n"
        if resultados_brutos:
            for r in resultados_brutos[:3]:
                texto_retorno += f"• **{r['title']}**: {r['body'][:160]}...\n"
        else:
            texto_retorno += "Não foram localizados grandes eventos listados nos portais públicos para os próximos dias.\n"
            
        texto_retorno += f"\n💡 **Dica de Marketing para a Mística:**\n{sugestao_mkt}"

        try:
            isis_logs.registrar(pergunta, "eventos_locais", nome, texto_retorno)
        except Exception:
            pass
        return {"handled": True, "modo": "eventos_locais", "texto": texto_retorno, "links": criar_botoes_de_acao(texto_retorno)}

    # E. Sugestão Manual de Reposição de Estoque (Requisito 6)
    if any(termo in p for termo in ["reposicao", "repor estoque", "analise de estoque", "sugestao de reposicao"]):
        texto_retorno = analisar_estoque_para_reposicao()
        try:
            isis_logs.registrar(pergunta, "reposicao_estoque", nome, texto_retorno)
        except Exception:
            pass
        return {"handled": True, "modo": "reposicao_estoque", "texto": texto_retorno, "links": criar_botoes_de_acao(texto_retorno)}

    # F. Consulta Geral na Internet se solicitado
    try:
        if deve_pesquisar_web(pergunta):
            resultados = obter_resultados_pesquisa(consulta_limpa, max_resultados=5)
            imagens = obter_imagens_pesquisa(consulta_limpa, max_resultados=len(resultados))
            
            # Formatação de texto com exibição de fotos
            texto = formatar_resultados_com_imagens(consulta_limpa, resultados, imagens)
            
            try:
                isis_logs.registrar(pergunta, "pesquisa_web", nome, texto)
            except Exception:
                pass
            return {"handled": True, "modo": "pesquisa_web", "texto": texto, "links": criar_botoes_de_acao(texto, imagens)}
    except Exception as e:
        print(f"[Processador Inteligente] Falha de processamento web: {e}")

    # Retorno padrão ao assistente caso nenhum dos gatilhos diretos seja acionado
    try:
        resposta = IsisAssistant(usuario).responder(pergunta)
        if isinstance(resposta, dict):
            texto_resp = resposta.get("texto", "")
            resposta["links"] = criar_botoes_de_acao(texto_resp)
            isis_logs.registrar(pergunta, resposta.get("modo", "indefinido"), nome, texto_resp)
            return resposta
        else:
            texto_str = str(resposta)
            ret = {"handled": True, "modo": "assistente", "texto": texto_str, "links": criar_botoes_de_acao(texto_str)}
            isis_logs.registrar(pergunta, "assistente", nome, texto_str)
            return ret
    except Exception as e:
        isis_logs.registrar(pergunta, "erro_isis", nome, "", str(e))
        return {
            "handled": True,
            "modo": "erro",
            "texto": f"A Isis encontrou um obstáculo ao gerar a resposta: {e}",
            "links": []
        }


# ==========================================
# 6. INTEGRAÇÃO COM COMANDOS DE VOZ (REQUISITO 8)
# ==========================================

def processar_comando_voz(comando_de_voz, usuario=None):
    """
    Controlador para transcrição de voz. Suporta operações de abertura de links.
    """
    comando = str(comando_de_voz or "").strip()
    comando_norm = normalizar_texto(comando)
    
    abrir_link_match = re.search(r"abrir\s+link\s+(\d+)", comando_norm)
    if abrir_link_match:
        idx = int(abrir_link_match.group(1))
        global _historico_links_recente
        try:
            if _historico_links_recente:
                for item in _historico_links_recente:
                    if item.get("index") == idx:
                        url_alvo = item.get("url")
                        abrir_link_no_navegador(url_alvo)
                        return {
                            "handled": True,
                            "modo": "comando_voz_link",
                            "texto": f"Processando abertura do link {idx} no navegador: {url_alvo}",
                            "links": [item]
                        }
            return {
                "handled": True,
                "modo": "comando_voz_link_erro",
                "texto": f"Não consegui identificar o link {idx} na memória recente.",
                "links": []
            }
        except Exception as e:
            return {
                "handled": True,
                "modo": "comando_voz_link_erro",
                "texto": f"Falha ao realizar abertura automática via voz: {e}",
                "links": []
            }

    comando_limpo = re.sub(r"^(?i)(isis|bruxinha)\b[:, ]*", "", comando).strip()
    resposta = processar_comando_inteligente(comando_limpo, usuario)
    
    if isinstance(resposta, dict) and "links" in resposta:
        _historico_links_recente = resposta["links"]
        
    return resposta


# ==========================================
# 7. ROTINAS DE DIAGNÓSTICO E MANUTENÇÃO
# ==========================================

def diagnostico_banco_operacional(tabelas_obrigatorias):
    from isis.commands import diagnostico_tabelas

    problemas = []
    try:
        problemas.extend(diagnostico_tabelas(tabelas_obrigatorias))
    except Exception as e:
        problemas.append(f"Erro ao verificar integridade das tabelas: {e}")

    try:
        abertos = caixa_abertos_count()
        if abertos > 1:
            problemas.append(f"Inconsistência de Operação: Há {abertos} caixas abertos simultaneamente no sistema.")
    except Exception as e:
        problemas.append(f"Erro ao acessar dados de abertura de caixas: {e}")

    try:
        nulos = produtos_cadastro_incompleto()
        if nulos:
            problemas.append(f"Inconsistência de Cadastro: Há {nulos} produto(s) com cadastro pendente ou incompleto.")
    except Exception as e:
        problemas.append(f"Erro ao verificar cadastros nulos: {e}")

    return problemas


def reparar_banco_e_indices(init_db_func, backup_func):
    from isis.commands import criar_indices_seguros, normalizar_nulos_basicos

    alteracoes = []
    try:
        init_db_func()
        alteracoes.append("Estrutura do banco de dados inicializada pelo init_db().")
    except Exception as e:
        alteracoes.append(f"Erro durante a inicialização do banco: {e}")

    try:
        criar_indices_seguros()
        alteracoes.append("Índices de desempenho gerados/conferidos.")
    except Exception as e:
        alteracoes.append(f"Erro durante a criação dos índices do SQLite: {e}")

    try:
        normalizar_nulos_basicos()
        alteracoes.append("Campos com valores nulos normalizados.")
    except Exception as e:
        alteracoes.append(f"Erro ao normalizar nulos: {e}")

    try:
        backup_func()
        alteracoes.append("Backup preventivo de segurança realizado com sucesso.")
    except Exception as e:
        alteracoes.append(f"Erro ao executar backup automatizado: {e}")

    return alteracoes


# ==========================================
# 8. COMPATIBILIDADE E RETROCOMPATIBILIDADE
# ==========================================

def calcular_giro_estoque_30_dias():
    resultados = []
    try:
        dados_giro = produtos_para_giro()
    except Exception as e:
        print(f"[Giro] Falha ao acessar dados de produtos para giro: {e}")
        return resultados

    for cod, nome, qtd_atual, est_min, categoria in dados_giro:
        try:
            total_vendido = total_vendido_produto(cod)
        except Exception:
            total_vendido = 0
            
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
        
    try:
        nivers = query_db(
            "SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? ORDER BY nome LIMIT 6",
            (f"%{datetime.now().strftime('%%d/%m')}%",),
        )
        if nivers:
            alertas.append("Aniversariantes hoje: " + ", ".join([n[0] for n in nivers]))
    except Exception as e:
        print(f"[Alerta] Não foi possível mapear aniversários: {e}")

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
        except Exception as e:
            print(f"[Alerta] Falha ao processar vencimento para '{desc}': {e}")
            
    if vencendo:
        alertas.append("Contas: " + "; ".join(vencendo[:4]))
        
    caixa = status_caixa_aberto()
    if caixa:
        try:
            abertura = datetime.strptime(caixa[2], "%d/%m/%Y %H:%M")
            horas = (agora - abertura).total_seconds() / 3600
            if horas >= 8:
                alertas.append(f"Caixa aberto há {horas:.1f} horas. Confira se já está na hora de fechar.")
        except Exception as e:
            print(f"[Alerta] Falha ao mensurar tempo de abertura do caixa: {e}")
            
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
    
    try:
        clientes = query_db("SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1")[0][0]
    except Exception:
        clientes = 0
        
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
        
    try:
        nivers = query_db(
            "SELECT nome FROM clientes WHERE COALESCE(ativo,1)=1 AND nascimento LIKE ? LIMIT 5",
            (f"%{datetime.now().strftime('%d/%m')}%",),
        )
        if nivers:
            prioridades.append("Enviar felicitações para aniversariantes: " + ", ".join([n[0] for n in nivers]))
    except Exception as e:
        print(f"[Prioridades] Erro ao buscar aniversariantes: {e}")

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


def pesquisar_web(consulta, max_resultados=5):
    """Fallback mantido para chamadas diretas que esperam strings de texto concatenadas."""
    resultados_brutos = obter_resultados_pesquisa(consulta, max_resultados)
    if not resultados_brutos:
        return f"Não foi possível obter resultados estruturados para '{limpar_consulta_web(consulta)}' no momento."
        
    linhas = [f"🌿 Resultados da pesquisa para: {limpar_consulta_web(consulta)}\n"]
    for idx, r in enumerate(resultados_brutos, start=1):
        linhas.append(f"{idx}. {r['title']}")
        linhas.append(f"   Link: {r['href']}")
        linhas.append(f"   Resumo: {r['body']}\n")
    return "\n".join(linhas)