"""Validador seguro para consolidacao do app_scroll_patch.

Este script nao altera arquivos. Ele compara o conteudo original de
`mistica_presentes.py` com o resultado apos aplicar `app_scroll_patch.py`.

Uso local:

    python tools/validar_app_scroll_patch.py

Resultado esperado antes da consolidacao:

- mostrar se o patch ainda altera o arquivo principal;
- listar quais sentinelas/trechos foram encontrados;
- orientar se o patch pode ser removido com baixo risco ou se precisa ser
  incorporado manualmente.
"""

from __future__ import annotations

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "mistica_presentes.py"
PATCH_FILE = ROOT / "app_scroll_patch.py"
REPORT_FILE = ROOT / "docs" / "auditorias" / "RELATORIO_VALIDACAO_APP_SCROLL_PATCH_LOCAL.md"

TARGETS = [
    "self.tree_v_stock.pack",
    "self.tree_v_car.pack",
    "self.tree_logs.pack",
    "self.tree_vendas_dia.pack",
    "self.tree_meta_vendedores.pack",
    "def adicionar_barra_rolagem_tree(self, tree):",
    "self.adicionar_barra_rolagem_tree(self.tree_v_stock)",
    "self.adicionar_barra_rolagem_tree(self.tree_v_car)",
    "self.adicionar_barra_rolagem_tree(self.tree_logs)",
    "self.adicionar_barra_rolagem_tree(self.tree_vendas_dia)",
    "self.adicionar_barra_rolagem_tree(self.tree_meta_vendedores)",
]


def carregar_patch():
    namespace: dict[str, object] = {}
    exec(PATCH_FILE.read_text(encoding="utf-8"), namespace)
    func = namespace.get("aplicar_scrollbars_runtime")
    if not callable(func):
        raise RuntimeError("Funcao aplicar_scrollbars_runtime nao encontrada em app_scroll_patch.py")
    return func


def main() -> None:
    fonte = APP_FILE.read_text(encoding="utf-8-sig")
    aplicar_scrollbars_runtime = carregar_patch()
    fonte_patched = aplicar_scrollbars_runtime(fonte)

    mudou = fonte != fonte_patched
    encontrados = [target for target in TARGETS if target in fonte]
    adicionados = [target for target in TARGETS if target in fonte_patched and target not in fonte]

    diff = list(
        difflib.unified_diff(
            fonte.splitlines(),
            fonte_patched.splitlines(),
            fromfile="mistica_presentes.py",
            tofile="mistica_presentes.py + app_scroll_patch.py",
            lineterm="",
            n=3,
        )
    )

    linhas = [
        "# Relatorio local - Validacao do app_scroll_patch",
        "",
        "Este arquivo foi gerado localmente pelo script `tools/validar_app_scroll_patch.py`.",
        "Ele nao deve conter segredos nem dados sensiveis.",
        "",
        "## Resultado",
        "",
        f"- Patch alterou `mistica_presentes.py`: {'SIM' if mudou else 'NAO'}",
        f"- Total de linhas de diff: {len(diff)}",
        "",
        "## Alvos encontrados no arquivo original",
        "",
    ]

    if encontrados:
        linhas.extend([f"- `{item}`" for item in encontrados])
    else:
        linhas.append("- Nenhum alvo especifico encontrado.")

    linhas.extend(["", "## Alvos adicionados pelo patch", ""])
    if adicionados:
        linhas.extend([f"- `{item}`" for item in adicionados])
    else:
        linhas.append("- Nenhum alvo novo adicionado.")

    linhas.extend(["", "## Diff", "", "```diff"])
    if diff:
        linhas.extend(diff[:400])
        if len(diff) > 400:
            linhas.append("... diff truncado ...")
    else:
        linhas.append("# Sem diferenca gerada pelo patch.")
    linhas.append("```")
    linhas.append("")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(linhas), encoding="utf-8")

    print("Validacao concluida.")
    print(f"Patch alterou mistica_presentes.py: {'SIM' if mudou else 'NAO'}")
    print(f"Relatorio gerado em: {REPORT_FILE}")
    if mudou:
        print("Proxima acao: incorporar o diff no arquivo principal e testar no Windows.")
    else:
        print("Proxima acao: remover a chamada do app_scroll_patch no app.py e testar no Windows.")


if __name__ == "__main__":
    main()
