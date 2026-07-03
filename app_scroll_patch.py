def aplicar_scrollbars_runtime(fonte):
    """Adiciona barras de rolagem nas tabelas principais do app.

    Correção: a versão anterior retornava cedo quando o método
    adicionar_barra_rolagem_tree já existia no app principal. Como o método
    já existe em mistica_presentes.py, as substituições nunca eram aplicadas
    e algumas tabelas ficavam sem barra.
    """

    substituicoes = [
        (
            "        self.tree_v_stock.pack(fill=\"x\", padx=15, pady=5)",
            "        self.tree_v_stock.pack(fill=\"x\", padx=15, pady=5)\n        self.adicionar_barra_rolagem_tree(self.tree_v_stock)",
            "self.adicionar_barra_rolagem_tree(self.tree_v_stock)",
        ),
        (
            "        self.tree_v_car.pack(fill=\"both\", expand=True, padx=15, pady=10)",
            "        self.tree_v_car.pack(fill=\"both\", expand=True, padx=15, pady=10)\n        self.adicionar_barra_rolagem_tree(self.tree_v_car)",
            "self.adicionar_barra_rolagem_tree(self.tree_v_car)",
        ),
        (
            "        self.tree_logs.pack(fill=\"both\", expand=True, pady=(5, 15))",
            "        self.tree_logs.pack(fill=\"both\", expand=True, pady=(5, 15))\n        self.adicionar_barra_rolagem_tree(self.tree_logs)",
            "self.adicionar_barra_rolagem_tree(self.tree_logs)",
        ),
        (
            "        self.tree_vendas_dia.pack(fill=\"both\", expand=True, padx=8, pady=(0, 8))",
            "        self.tree_vendas_dia.pack(fill=\"both\", expand=True, padx=8, pady=(0, 8))\n        self.adicionar_barra_rolagem_tree(self.tree_vendas_dia)",
            "self.adicionar_barra_rolagem_tree(self.tree_vendas_dia)",
        ),
        (
            "        self.tree_meta_vendedores.pack(fill=\"x\", padx=8, pady=(0, 8))",
            "        self.tree_meta_vendedores.pack(fill=\"x\", padx=8, pady=(0, 8))\n        self.adicionar_barra_rolagem_tree(self.tree_meta_vendedores)",
            "self.adicionar_barra_rolagem_tree(self.tree_meta_vendedores)",
        ),
    ]

    for antigo, novo, sentinela in substituicoes:
        if antigo in fonte and sentinela not in fonte:
            fonte = fonte.replace(antigo, novo, 1)

    if "def adicionar_barra_rolagem_tree(self, tree):" not in fonte:
        marcador = "    def montar_painel_vendas_dia(self, parent=None):"
        metodo = r'''
    def adicionar_barra_rolagem_tree(self, tree):
        try:
            parent = tree.master
            yscroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
            xscroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            yscroll.pack(side="right", fill="y", padx=(0, 3), pady=2)
            xscroll.pack(side="bottom", fill="x", padx=3, pady=(0, 3))
            def rolar_mouse(event):
                try:
                    tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
                except Exception:
                    pass
            tree.bind("<MouseWheel>", rolar_mouse)
        except Exception as exc:
            try:
                registrar_erro_sistema("adicionar_barra_rolagem_tree", exc)
            except Exception:
                pass

'''
        if marcador in fonte:
            fonte = fonte.replace(marcador, metodo + marcador, 1)

    return fonte
