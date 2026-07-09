"""Consolida localmente o app_scroll_patch no codigo principal.

Este script ALTERA arquivos locais. Use somente na branch
`refactor/scroll-patch-consolidation` e com o Git limpo.

O que ele faz:

1. Aplica `app_scroll_patch.py` em `mistica_presentes.py`.
2. Remove a chamada de `app_scroll_patch` da lista de patches do `app.py`.
3. Gera um relatorio local com os arquivos alterados.
4. Nao apaga `app_scroll_patch.py` ainda.

Uso:

    python tools/consolidar_app_scroll_patch_local.py

Depois do uso:

    python app.py
    git diff
    git status

Se tudo funcionar, os arquivos alterados podem ser commitados.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PRINCIPAL = ROOT / "mistica_presentes.py"
APP_LAUNCHER = ROOT / "app.py"
PATCH_FILE = ROOT / "app_scroll_patch.py"
REPORT_FILE = ROOT / "docs" / "auditorias" / "RELATORIO_CONSOLIDACAO_APP_SCROLL_PATCH_LOCAL.md"

TRECHO_APP_PY = '        ("app_scroll_patch", "aplicar_scrollbars_runtime", "barras de rolagem"),\n'


def git_status_limpo() -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0 and not proc.stdout.strip()
    except Exception:
        return False


def branch_atual() -> str:
    try:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.stdout.strip()
    except Exception:
        return ""


def carregar_patch():
    namespace: dict[str, object] = {}
    exec(PATCH_FILE.read_text(encoding="utf-8"), namespace)
    func = namespace.get("aplicar_scrollbars_runtime")
    if not callable(func):
        raise RuntimeError("Funcao aplicar_scrollbars_runtime nao encontrada em app_scroll_patch.py")
    return func


def main() -> None:
    atual = branch_atual()
    if atual != "refactor/scroll-patch-consolidation":
        raise SystemExit(
            "Execute este script somente na branch refactor/scroll-patch-consolidation. "
            f"Branch atual: {atual or 'desconhecida'}"
        )

    if not git_status_limpo():
        raise SystemExit(
            "O Git nao esta limpo. Rode `git status` e resolva alteracoes locais antes de consolidar."
        )

    fonte_original = APP_PRINCIPAL.read_text(encoding="utf-8-sig")
    aplicar_scrollbars_runtime = carregar_patch()
    fonte_consolidada = aplicar_scrollbars_runtime(fonte_original)

    app_py_original = APP_LAUNCHER.read_text(encoding="utf-8")
    if TRECHO_APP_PY not in app_py_original:
        raise SystemExit("Nao encontrei a chamada do app_scroll_patch em app.py. Nada foi alterado.")
    app_py_consolidado = app_py_original.replace(TRECHO_APP_PY, "", 1)

    if fonte_consolidada == fonte_original:
        raise SystemExit(
            "O app_scroll_patch nao gerou diferenca em mistica_presentes.py. "
            "Neste caso, remova apenas a chamada no app.py em etapa separada."
        )

    APP_PRINCIPAL.write_text(fonte_consolidada, encoding="utf-8")
    APP_LAUNCHER.write_text(app_py_consolidado, encoding="utf-8")

    linhas = [
        "# Relatorio local - Consolidacao do app_scroll_patch",
        "",
        "## Resultado",
        "",
        "- `app_scroll_patch.py` foi aplicado em `mistica_presentes.py`.",
        "- A chamada do `app_scroll_patch` foi removida de `app.py`.",
        "- O arquivo `app_scroll_patch.py` NAO foi apagado nesta etapa.",
        "",
        "## Arquivos alterados localmente",
        "",
        "- `mistica_presentes.py`",
        "- `app.py`",
        "",
        "## Testes obrigatorios antes de commit",
        "",
        "1. Abrir o programa:",
        "",
        "```powershell",
        "python app.py",
        "```",
        "",
        "2. Fazer login.",
        "3. Abrir Dashboard.",
        "4. Abrir Vendas.",
        "5. Abrir Estoque.",
        "6. Conferir rolagem das tabelas.",
        "7. Conferir se nao apareceu erro no terminal.",
        "",
        "## Comandos de conferencia",
        "",
        "```powershell",
        "git diff -- app.py mistica_presentes.py",
        "git status",
        "```",
        "",
        "## Proxima etapa",
        "",
        "Se os testes passarem, fazer commit destes arquivos. Somente depois considerar excluir `app_scroll_patch.py`.",
        "",
    ]
    REPORT_FILE.write_text("\n".join(linhas), encoding="utf-8")

    print("Consolidacao local preparada com sucesso.")
    print("Arquivos alterados:")
    print("- mistica_presentes.py")
    print("- app.py")
    print(f"Relatorio: {REPORT_FILE}")
    print("\nAgora rode: python app.py")


if __name__ == "__main__":
    main()
