import re
from datetime import datetime

from reports.vendas_report import resumo_vendas_periodo, produto_campeao, lucro_bruto_itens_periodo
from reports.estoque_report import estoque_baixo, produtos_sem_giro
from services.caixa_service import obter_caixa_id_ativo, status_caixa_aberto
from services.produto_service import pesquisar_produtos_venda
from services.venda_service import calcular_total_venda, registrar_venda_service
from repositories import isis_logs


def _usuario_nome(usuario):
    return usuario.get("nome", "Isis") if isinstance(usuario, dict) else "Isis"


def moeda(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num_depois(texto, palavras):
    p = texto.lower()
    for palavra in palavras:
        m = re.search(palavra + r"\s*(?:de|por|para|a)?\s*(\d+[\d\.,]*)", p)
        if m:
            return float(m.group(1).replace(".", "").replace(",", "."))
    return None


def _nome_produto_cadastro(texto):
    bruto = re.sub(r"(?i)\b(isis|cadastra|cadastre|cadastrar|novo produto|adiciona produto|adicionar produto|adiciona)\b", "", texto)
    bruto = re.split(r"(?i),| custo | margem | vender por | preco | preço | quantidade | qtd ", bruto)[0]
    return bruto.strip(" .:-")


def _nome_produto_estoque(texto):
    m = re.search(r"(?i)(?:estoque do|estoque da|estoque de|estoque)\s+(.+)", texto)
    if m:
        return re.split(r"(?i),| custo | margem | vender por | preco | preço | em \d+| para \d+", m.group(1))[0].strip()
    m = re.search(r"(?i)(?:adiciona|aumenta|entrada de estoque)\s+(\d+)\s+(.+)", texto)
    if m:
        return re.split(r"(?i)no estoque|ao estoque|,| custo | margem | vender por | preco | preço", m.group(2))[0].strip()
    return _nome_produto_cadastro(texto)


def _nome_produto_preco(texto):
    bruto = re.sub(r"(?i)\b(isis|altera|alterar|muda|mudar|troca|trocar|o preco|o preço|preco|preço|do|da|de)\b", "", texto)
    bruto = re.split(r"(?i) para | por |,| custo | margem ", bruto)[0]
    return bruto.strip(" .:-")


def preparar_cadastro_produto(texto, usuario):
    nome = _nome_produto_cadastro(texto)
    custo = _num_depois(texto, ["custo"])
    preco = _num_depois(texto, ["vender por", "preco", "preço"])
    margem = _num_depois(texto, ["margem"])
    qtd = _num_depois(texto, ["quantidade", "qtd"])
    if qtd is None:
        qtd = 0
    if custo is None:
        custo = 0.0
    if preco is None and margem is not None:
        preco = custo * (1 + margem / 100)
    if preco is None:
        return {"texto": "Para cadastrar com seguranca, informe pelo menos nome e preco de venda. Exemplo: cadastra vela colorida, custo 12 reais, margem de 80%.", "pendente": None}
    if margem is None:
        margem = ((preco / custo) - 1) * 100 if custo > 0 else 0.0
    acao = {"tipo": "cadastro_produto", "nome": nome, "custo": custo, "preco": preco, "lucro": margem, "quantidade": int(qtd), "estoque_minimo": 0, "categoria": "Geral"}
    texto_resumo = (
        "Conferencia de cadastro de produto:\n"
        f"- Produto: {nome}\n- Custo: {moeda(custo)}\n- Preco de venda: {moeda(preco)}\n"
        f"- Margem: {margem:.1f}%\n- Estoque inicial: {int(qtd)}\n\n"
        "Nada foi salvo ainda. Para cadastrar, responda: confirmar."
    )
    return {"texto": texto_resumo, "pendente": acao}


def preparar_entrada_estoque(texto, usuario):
    nums = [int(float(x.replace(".", "").replace(",", "."))) for x in re.findall(r"\d+[\d\.,]*", texto)]
    qtd = nums[0] if nums else 0
    nome = _nome_produto_estoque(texto)
    encontrados = pesquisar_produtos_venda(nome)
    if encontrados:
        prod = encontrados[0]
        acao = {"tipo": "entrada_estoque", "codigo": prod[0], "nome": prod[1], "quantidade": qtd}
        return {"texto": f"Conferencia de entrada de estoque:\n- Produto: {prod[1]}\n- Entrada: {qtd} unidade(s)\n\nNada foi alterado ainda. Para confirmar, responda: confirmar.", "pendente": acao}
    cadastro = preparar_cadastro_produto(texto, usuario)
    if cadastro.get("pendente"):
        cadastro["pendente"]["quantidade"] = qtd
        cadastro["texto"] += "\n\nNao encontrei produto existente com esse nome, entao preparei como novo cadastro."
    return cadastro


def preparar_alterar_preco(texto, usuario):
    nome = _nome_produto_preco(texto)
    preco = _num_depois(texto, ["para", "por", "preco", "preço"])
    if preco is None:
        return {"texto": "Informe o novo preco. Exemplo: altera o preco da vela colorida para 18 reais.", "pendente": None}
    encontrados = pesquisar_produtos_venda(nome)
    if not encontrados:
        return {"texto": f"Nao encontrei produto parecido com: {nome}", "pendente": None}
    prod = encontrados[0]
    acao = {"tipo": "alterar_preco", "codigo": prod[0], "nome": prod[1], "preco": preco}
    return {"texto": f"Conferencia de alteracao de preco:\n- Produto: {prod[1]}\n- Novo preco: {moeda(preco)}\n\nNada foi alterado ainda. Para confirmar, responda: confirmar.", "pendente": acao}



def consulta(intent, texto):
    hoje = datetime.now().strftime("%d/%m/%Y")
    mes = datetime.now().strftime("/%m/%Y")
    p = (texto or "").lower()
    if intent == "consulta_vendas":
        if "produto mais vendido" in p:
            top = produto_campeao()
            return f"Produto mais vendido: {top[0]} com {top[1]} unidade(s), total {moeda(top[2])}." if top else "Ainda nao ha produto campeao registrado."
        if "lucro" in p:
            lucro, faturamento, custo = lucro_bruto_itens_periodo(mes)
            return f"Lucro bruto do mes: {moeda(lucro)}. Faturamento: {moeda(faturamento)}. Custo: {moeda(custo)}."
        qtd, total = resumo_vendas_periodo(hoje)
        return f"Hoje voce vendeu {moeda(total)} em {qtd} venda(s)."
    if intent == "consulta_estoque":
        baixos = estoque_baixo(10)
        parados = produtos_sem_giro(6, somente_com_estoque=True)
        linhas = []
        if baixos:
            linhas.append("Produtos acabando: " + ", ".join([f"{b[0]} ({b[1]} un)" for b in baixos]))
        if parados:
            linhas.append("Produtos parados: " + ", ".join([f"{p[0]} ({p[1]} un)" for p in parados]))
        return "\n".join(linhas) if linhas else "O estoque nao mostra alertas urgentes agora."
    if intent == "consulta_caixa":
        cx = status_caixa_aberto()
        return f"Caixa aberto desde {cx[2]}, fundo inicial {moeda(cx[1])}." if cx else "O caixa esta fechado."
    return ""


def calcular_margem(texto):
    nums = [float(x.replace(".", "").replace(",", ".")) for x in re.findall(r"\d+[\d\.,]*", texto)]
    if len(nums) >= 2:
        margem, custo = nums[0], nums[1]
        preco = custo * (1 + margem / 100)
        return f"Com custo de {moeda(custo)} e margem de {margem:.0f}%, o preco sugerido e {moeda(preco)}. Lucro unitario: {moeda(preco-custo)}."
    return "Me informe margem e custo. Exemplo: calcula preco com 100% de margem em cima do custo 7 reais."


def preparar_venda(texto, usuario):
    partes = re.findall(r"(\d+)\s+([^,;]+?)(?=\s+e\s+\d+|,|;|$)", texto, flags=re.I)
    if not partes:
        return {"texto": "Nao consegui identificar os itens. Exemplo: realiza venda de 2 incensos Noa e 1 vela colorida.", "pendente": None}
    carrinho = []
    avisos = []
    for qtd_txt, nome_txt in partes:
        termo = re.sub(r"\b(de|do|da|dos|das|venda|vende|realiza|realizar)\b", "", nome_txt, flags=re.I).strip()
        encontrados = pesquisar_produtos_venda(termo)
        if not encontrados:
            avisos.append(f"Nao encontrei produto parecido com: {termo}")
            continue
        prod = encontrados[0]
        qtd = int(qtd_txt)
        estoque = int(prod[3] or 0)
        if qtd > estoque:
            avisos.append(f"Estoque insuficiente para {prod[1]}: pediu {qtd}, disponivel {estoque}.")
            continue
        preco = float(prod[2] or 0)
        carrinho.append({"id": prod[0], "n": prod[1], "q": qtd, "p": preco, "t": preco * qtd})
    if not carrinho:
        return {"texto": "Nao consegui montar uma venda segura.\n" + "\n".join(avisos), "pendente": None}
    calc = calcular_total_venda(carrinho, 0, "Dinheiro")
    linhas = ["Resumo da venda para conferencia:"]
    for item in carrinho:
        linhas.append(f"- {item['q']}x {item['n']} = {moeda(item['t'])}")
    if avisos:
        linhas.append("Avisos: " + " | ".join(avisos))
    linhas.append(f"Total: {moeda(calc['tot'])}")
    linhas.append("Para registrar e baixar estoque, responda: confirmar.")
    return {"texto": "\n".join(linhas), "pendente": {"tipo": "venda_texto", "carrinho": carrinho, "calculo": calc}}


def executar_pendente(acao, usuario):
    tipo = acao.get("tipo")
    if tipo == "venda_texto":
        cx_id = obter_caixa_id_ativo()
        if not cx_id:
            return "Nao registrei a venda porque o caixa esta fechado. Abra o caixa primeiro."
        data = datetime.now().strftime("%d/%m/%Y %H:%M")
        data_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vid = registrar_venda_service(acao["carrinho"], "Consumidor Final", data, data_iso, acao["calculo"], "Dinheiro", _usuario_nome(usuario), cx_id)
        isis_logs.registrar("confirmar venda por texto", "registrar_venda", _usuario_nome(usuario), f"Venda {vid} registrada")
        return f"Venda {vid} registrada com sucesso. Estoque baixado e caixa atualizado."
    if tipo == "cadastro_produto":
        from services.produto_service import cadastrar_produto_service
        codigo = cadastrar_produto_service(acao["nome"], acao["custo"], acao["lucro"], acao["preco"], acao["quantidade"], acao.get("estoque_minimo", 0), acao.get("categoria", "Geral"), _usuario_nome(usuario))
        isis_logs.registrar("confirmar cadastro produto", "cadastro_produto", _usuario_nome(usuario), f"Produto {codigo} cadastrado")
        return f"Produto cadastrado com sucesso. Codigo: {codigo}."
    if tipo == "entrada_estoque":
        from services.produto_service import consultar_produto_edicao, editar_produto_service
        dados = consultar_produto_edicao(acao["codigo"])
        if not dados:
            return "Produto nao localizado para entrada de estoque."
        nome, custo, lucro, preco, quantidade, estoque_minimo, categoria = dados
        nova_qtd = int(quantidade or 0) + int(acao["quantidade"] or 0)
        editar_produto_service(acao["codigo"], nome, custo or 0.0, lucro or 0.0, preco or 0.0, nova_qtd, estoque_minimo or 0, _usuario_nome(usuario))
        isis_logs.registrar("confirmar entrada estoque", "entrada_estoque", _usuario_nome(usuario), f"{acao['codigo']} +{acao['quantidade']}")
        return f"Entrada de estoque confirmada. {nome} agora ficou com {nova_qtd} unidade(s)."
    if tipo == "alterar_preco":
        from services.produto_service import consultar_produto_edicao, editar_produto_service
        dados = consultar_produto_edicao(acao["codigo"])
        if not dados:
            return "Produto nao localizado para alteracao de preco."
        nome, custo, lucro, preco_antigo, quantidade, estoque_minimo, categoria = dados
        novo_preco = float(acao["preco"] or 0)
        novo_lucro = ((novo_preco / float(custo or 0)) - 1) * 100 if float(custo or 0) > 0 else float(lucro or 0)
        editar_produto_service(acao["codigo"], nome, custo or 0.0, novo_lucro, novo_preco, quantidade or 0, estoque_minimo or 0, _usuario_nome(usuario))
        isis_logs.registrar("confirmar alterar preco", "alterar_preco", _usuario_nome(usuario), f"{acao['codigo']} {moeda(preco_antigo)} -> {moeda(novo_preco)}")
        return f"Preco alterado com sucesso. {nome}: {moeda(preco_antigo)} -> {moeda(novo_preco)}."
    return "Essa acao pendente ainda nao tem executor seguro."
