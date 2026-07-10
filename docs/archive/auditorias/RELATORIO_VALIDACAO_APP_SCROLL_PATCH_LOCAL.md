# Relatorio local - Validacao do app_scroll_patch

Este arquivo foi gerado localmente pelo script `tools/validar_app_scroll_patch.py`.
Ele nao deve conter segredos nem dados sensiveis.

## Resultado

- Patch alterou `mistica_presentes.py`: SIM
- Total de linhas de diff: 26

## Alvos encontrados no arquivo original

- `self.tree_v_stock.pack`
- `self.tree_v_car.pack`
- `self.tree_logs.pack`
- `def adicionar_barra_rolagem_tree(self, tree):`

## Alvos adicionados pelo patch

- `self.adicionar_barra_rolagem_tree(self.tree_v_stock)`
- `self.adicionar_barra_rolagem_tree(self.tree_v_car)`
- `self.adicionar_barra_rolagem_tree(self.tree_logs)`

## Diff

```diff
--- mistica_presentes.py
+++ mistica_presentes.py + app_scroll_patch.py
@@ -570,6 +570,7 @@
             self.tree_v_stock.heading(c, text=h)
             self.tree_v_stock.column(c, width=90)
         self.tree_v_stock.pack(fill="x", padx=15, pady=5)
+        self.adicionar_barra_rolagem_tree(self.tree_v_stock)
         self.tree_v_stock.bind("<Double-1>", lambda e: self.add_ao_carrinho())
 
         f_mid = ctk.CTkFrame(esq, fg_color="transparent")
@@ -585,6 +586,7 @@
         self.tree_v_car.heading("q", text="Qtd")
         self.tree_v_car.heading("t", text="Total")
         self.tree_v_car.pack(fill="both", expand=True, padx=15, pady=10)
+        self.adicionar_barra_rolagem_tree(self.tree_v_car)
         self.tree_v_car.bind("<Double-1>", lambda e: self.editar_qtd_carrinho())
 
         dir = ctk.CTkFrame(f, fg_color=self.cor_vinho, width=390, corner_radius=15)
@@ -1887,6 +1889,7 @@
         for c, h in zip(("u","a","d","dt"), ("User","Acao","Detalhes","Data/Hora")):
             self.tree_logs.heading(c, text=h)
         self.tree_logs.pack(fill="both", expand=True, pady=(5, 15))
+        self.adicionar_barra_rolagem_tree(self.tree_logs)
         self.refresh_audit()
 
     # --- JANELA DE GERENCIAMENTO DE USUÁRIOS ---
```
