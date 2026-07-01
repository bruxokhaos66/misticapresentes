from pathlib import Path
import re


BLOCO_ISIS_CORRIGIDO = r'''
    def inserir_texto_com_links_isis(self, texto):
        import re
        import webbrowser

        texto = str(texto or "")
        urls = re.findall(r"https?://[^\s]+", texto)
        pos = 0

        for idx, url in enumerate(urls):
            inicio = texto.find(url, pos)
            if inicio < 0:
                continue

            if inicio > pos:
                self.txt_chat.insert("end", texto[pos:inicio])

            tag = f"link_isis_{idx}_{inicio}"
            self.txt_chat.insert("end", url, tag)
            self.txt_chat.tag_config(tag, foreground="#4da3ff", underline=True)
            self.txt_chat.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
            pos = inicio + len(url)

        self.txt_chat.insert("end", texto[pos:])

    def _isis_texto_normalizado_local(self, texto):
        try:
            return isis_normalizar_texto(texto)
        except Exception:
            mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
            return str(texto or "").translate(mapa).lower().strip()

    def _isis_usuario_nome(self):
        try:
            return self.current_user.get("nome", "Isis") if isinstance(self.current_user, dict) else "Isis"
        except Exception:
            return "Isis"

    def _isis_buscar_produto_operacional(self, termo):
        termo = str(termo or "").strip()
        if not termo:
            return None
        termo_like = "%" + termo + "%"
        res = query_db(
            """
            SELECT codigo_p, nome, COALESCE(preco,0), COALESCE(quantidade,0), COALESCE(custo,0), COALESCE(estoque_minimo,0)
            FROM produtos
            WHERE COALESCE(ativo,1)=1
              AND (codigo_p LIKE ? OR nome LIKE ? OR categoria LIKE ?)
            ORDER BY CASE WHEN LOWER(nome)=LOWER(?) THEN 0 ELSE 1 END, nome
            LIMIT 1
            """,
            (termo_like, termo_like, termo_like, termo),
        )
        return res[0] if res else None

    def _isis_parse_quantidade_produto(self, texto):
        texto = str(texto or "").strip()
        m = re.search(r"(?:adicionar|adiciona|colocar|coloca|entrada|remover|remove|retirar|baixa|baixar|tirar|vender|venda|efetuar venda|realizar venda)\s+(?:do estoque|ao estoque|no estoque|estoque)?\s*(\d+)\s+(.+)$", texto, flags=re.I)
        if not m:
            m = re.search(r"(\d+)\s+(.+)$", texto)
        if not m:
            return None, ""
        qtd = int(m.group(1))
        termo = m.group(2).strip(" .,;:-")
        termo = re.sub(r"(?i)\b(unidades|unidade|un|do estoque|ao estoque|no estoque|para estoque)\b", "", termo).strip(" .,;:-")
        return qtd, termo

    def _isis_alterar_mensagem_inicial(self, pergunta):
        p = self._isis_texto_normalizado_local(pergunta)
        gatilhos = [
            "mensagem inicial", "mensagem da tela", "mensagem do dashboard",
            "mensagem motivacional", "frase inicial", "frase da tela"
        ]
        if not any(g in p for g in gatilhos):
            return None
        texto = str(pergunta or "").strip()
        partes = re.split(r"(?i)\bpara\b", texto, maxsplit=1)
        if len(partes) < 2 or not partes[1].strip():
            return "Me diga a nova mensagem assim: Isis, mude a mensagem inicial para Hoje vamos vender com energia boa."
        nova = partes[1].strip(" .:-")
        if len(nova) < 5:
            return "A mensagem ficou muito curta. Escreva uma frase um pouco mais completa."
        salvar_mensagem_dashboard(nova)
        try:
            self.montar_dashboard()
        except Exception:
            pass
        registrar_log(self._isis_usuario_nome(), "Isis", "Alterou mensagem inicial da tela")
        return "Pronto. Alterei a mensagem inicial da tela para:\n" + nova

    def _isis_alterar_estoque_por_comando(self, pergunta):
        p = self._isis_texto_normalizado_local(pergunta)
        if not any(x in p for x in ["adicionar estoque", "adiciona estoque", "colocar estoque", "entrada estoque", "remover estoque", "remove estoque", "retirar estoque", "baixar estoque", "baixa estoque", "tirar estoque", "remover do estoque", "adicionar ao estoque"]):
            return None
        operacao = "entrada"
        if any(x in p for x in ["remover", "remove", "retirar", "baixar", "baixa", "tirar"]):
            operacao = "saida"
        qtd, termo = self._isis_parse_quantidade_produto(pergunta)
        if not qtd or qtd <= 0 or not termo:
            return "Me diga assim: Isis, adicionar estoque 5 incenso X, ou Isis, remover do estoque 2 vela Y."
        produto = self._isis_buscar_produto_operacional(termo)
        if not produto:
            return f"Nao encontrei produto parecido com: {termo}."
        codigo, nome, preco, estoque_atual, custo, estoque_minimo = produto
        estoque_atual = int(estoque_atual or 0)
        novo = estoque_atual + qtd if operacao == "entrada" else estoque_atual - qtd
        if novo < 0:
            return f"Nao posso deixar estoque negativo. {nome} tem {estoque_atual} unidade(s)."
        query_db("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (novo, codigo), commit=True)
        try:
            registrar_movimentacao_estoque_service(
                codigo,
                nome,
                qtd if operacao == "entrada" else -qtd,
                "Entrada" if operacao == "entrada" else "Saida",
                "Comando da Isis",
                self._isis_usuario_nome(),
                estoque_atual,
                novo,
            )
        except Exception:
            pass
        try:
            self.refresh_estoque_list()
        except Exception:
            pass
        try:
            self.filtrar_vendas()
        except Exception:
            pass
        return f"Pronto. Estoque de {nome} atualizado: {estoque_atual} -> {novo}."

    def _isis_parse_itens_venda(self, pergunta):
        texto = str(pergunta or "")
        texto = re.sub(r"(?i)\b(isis|bruxinha|efetuar venda|realizar venda|fazer venda|adicionar venda|vender|venda)\b[:, ]*", " ", texto)
        texto = re.sub(r"(?i)\b(e|mais|com)\b", " ", texto)
        texto = " ".join(texto.split())
        pares = re.findall(r"(\d+)\s+(.+?)(?=\s+\d+\s+|$)", texto)
        itens = []
        for qtd_txt, termo in pares:
            termo = termo.strip(" .,;:-")
            if not termo:
                continue
            itens.append((int(qtd_txt), termo))
        return itens

    def _isis_adicionar_venda_por_comando(self, pergunta):
        p = self._isis_texto_normalizado_local(pergunta)
        if not any(x in p for x in ["efetuar venda", "realizar venda", "fazer venda", "adicionar venda", "vender ", "venda "]):
            return None
        itens_pedidos = self._isis_parse_itens_venda(pergunta)
        if not itens_pedidos:
            return "Me diga assim: Isis, efetuar venda 2 incenso Noa 1 vela colorida."
        adicionados = []
        falhas = []
        for qtd, termo in itens_pedidos:
            produto = self._isis_buscar_produto_operacional(termo)
            if not produto:
                falhas.append(f"Nao encontrei: {termo}")
                continue
            codigo, nome, preco, estoque_atual, custo, estoque_minimo = produto
            estoque_atual = int(estoque_atual or 0)
            qtd_no_carrinho = sum(int(it.get("q", 0)) for it in self.carrinho if it.get("id") == codigo)
            if qtd <= 0:
                falhas.append(f"Quantidade invalida para {termo}")
                continue
            if qtd + qtd_no_carrinho > estoque_atual:
                falhas.append(f"Estoque insuficiente para {nome}. Disponivel: {estoque_atual}.")
                continue
            preco = float(preco or 0)
            self.carrinho.append({"id": codigo, "n": nome, "q": qtd, "p": preco, "t": preco * qtd})
            adicionados.append(f"{qtd}x {nome}")
        try:
            self.render_v_car()
        except Exception:
            pass
        try:
            self.tabs.set("Vendas")
        except Exception:
            pass
        resposta = []
        if adicionados:
            total = sum(float(it.get("t", 0)) for it in self.carrinho)
            resposta.append("Adicionei ao carrinho: " + ", ".join(adicionados))
            resposta.append("Total parcial do carrinho: " + format_moeda(total))
            resposta.append("Para concluir, diga: finalizar venda.")
        if falhas:
            resposta.append("Pendencias: " + " | ".join(falhas))
        return "\n".join(resposta) if resposta else "Nao consegui adicionar itens ao carrinho."

    def _isis_finalizar_venda_por_comando(self, pergunta):
        p = self._isis_texto_normalizado_local(pergunta)
        if not any(x in p for x in ["finalizar venda", "concluir venda", "fechar venda", "salvar venda"]):
            return None
        if not getattr(self, "carrinho", None):
            return "O carrinho esta vazio. Primeiro diga, por exemplo: efetuar venda 2 incenso Noa."
        try:
            self.finalizar_venda()
            return "Abri a conferencia da venda. Confira o cupom e clique em confirmar para salvar."
        except Exception as e:
            return f"Tentei finalizar a venda, mas encontrei um erro: {e}"

    def _isis_montar_cupom_venda_operacional(self, venda_id=None):
        if venda_id:
            venda = query_db("SELECT id, data_venda, cliente, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor FROM vendas WHERE id=?", (venda_id,))
        else:
            venda = query_db("SELECT id, data_venda, cliente, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor FROM vendas ORDER BY id DESC LIMIT 1")
        if not venda:
            return None, None, None
        v = venda[0]
        itens = query_db("SELECT nome_p, quantidade, valor_total FROM vendas_itens WHERE venda_id=?", (v[0],))
        cupom = (
            "        MISTICA PRESENTES\n"
            "        Natalia Grunwald\n"
            "--------------------------------\n"
            f"CUPOM N: {v[0]} | DATA: {v[1]}\n"
            f"CLIENTE: {v[2]}\n"
            f"VENDEDOR: {v[8]}\n"
            f"PAGAMENTO: {v[7]}\n"
            "--------------------------------\n"
        )
        for nome, qtd, total in itens:
            cupom += f"{str(nome)[:18]:<18} Qtd:{qtd:<3} {format_moeda(total)}\n"
        cupom += (
            "--------------------------------\n"
            f"SUBTOTAL: {format_moeda(v[3])}\n"
            f"DESCONTO: -{format_moeda(v[4])}\n"
            f"TAXA CARTAO: {format_moeda(v[5])}\n"
            f"TOTAL FINAL: {format_moeda(v[6])}\n"
            "--------------------------------\n"
            "Mistica Presentes agradece pela sua compra\n"
        )
        return v[0], v[2], cupom

    def _isis_cupom_por_comando(self, pergunta):
        p = self._isis_texto_normalizado_local(pergunta)
        if not any(x in p for x in ["enviar cupom", "cupom whatsapp", "cupom whats", "imprimir cupom", "imprime cupom"]):
            return None
        nums = re.findall(r"\d+", str(pergunta or ""))
        venda_id = int(nums[0]) if nums else None
        vid, cliente, cupom = self._isis_montar_cupom_venda_operacional(venda_id)
        if not cupom:
            return "Nao encontrei venda para gerar cupom."
        if any(x in p for x in ["whatsapp", "whats", "zap"]):
            try:
                self.enviar_cupom_whatsapp(cupom, cliente)
                return f"Pronto. Abri o WhatsApp com o cupom da venda {vid}."
            except Exception as e:
                return f"Tentei enviar o cupom no WhatsApp, mas encontrei um erro: {e}"
        try:
            self.imprimir_cupom_texto(cupom, vid)
            return f"Pronto. Enviei o cupom da venda {vid} para impressao/arquivo."
        except Exception as e:
            return f"Tentei imprimir o cupom, mas encontrei um erro: {e}"

    def _isis_processar_comando_operacional(self, pergunta):
        for func in (
            self._isis_alterar_mensagem_inicial,
            self._isis_alterar_estoque_por_comando,
            self._isis_adicionar_venda_por_comando,
            self._isis_finalizar_venda_por_comando,
            self._isis_cupom_por_comando,
        ):
            try:
                resposta = func(pergunta)
                if resposta:
                    return resposta
            except Exception as e:
                return f"A Isis tentou executar o comando, mas encontrou erro: {e}"
        return None

    def enviar_pergunta_ia(self):
        pergunta = self.ent_pergunta.get().strip()
        if not pergunta:
            return
        self.txt_chat.configure(state="normal")
        self.txt_chat.insert("end", f"Você: {pergunta}\n\n")
        resposta = self._isis_processar_comando_operacional(pergunta)
        if resposta is None:
            resposta = self.processar_pergunta_ia(pergunta)
        try:
            self.registrar_aprendizado_issis(pergunta, resposta)
        except Exception:
            pass
        self.txt_chat.insert("end", "Isis a Bruxinha:\n")
        self.inserir_texto_com_links_isis(resposta)
        self.txt_chat.insert("end", "\n\n" + "-" * 56 + "\n\n")
        self.txt_chat.configure(state="disabled")
        self.txt_chat.see("end")
        self.ent_pergunta.delete(0, "end")
'''


def carregar_codigo_corrigido(caminho: Path) -> str:
    codigo = caminho.read_text(encoding="utf-8-sig")
    codigo = codigo.replace("\t", "    ")

    padrao = (
        r"\n[ \t]*def inserir_texto_com_links_isis\(self, texto\):"
        r".*?"
        r"(?=\n[ \t]*def importar_json_isis_para_sqlite\(self\):)"
    )

    codigo, alterados = re.subn(
        padrao,
        lambda _match: "\n" + BLOCO_ISIS_CORRIGIDO.strip("\n"),
        codigo,
        count=1,
        flags=re.DOTALL,
    )

    if alterados == 0:
        inicio = codigo.find("def inserir_texto_com_links_isis")
        fim = codigo.find("def importar_json_isis_para_sqlite", inicio)
        if inicio != -1 and fim != -1:
            linha_inicio = codigo.rfind("\n", 0, inicio)
            linha_fim = codigo.rfind("\n", 0, fim)
            codigo = codigo[:linha_inicio] + "\n" + BLOCO_ISIS_CORRIGIDO.strip("\n") + codigo[linha_fim:]

    return codigo
