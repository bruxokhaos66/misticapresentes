from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARQUIVOS_CRITICOS = [
    ROOT / "mistica_presentes.py",
    ROOT / "MisticaLauncher.py",
    ROOT / "auto_updater.py",
    ROOT / "services" / "caixa_service.py",
    ROOT / "services" / "venda_service.py",
]

PREFIXOS_AUDITADOS = (
    "services.",
    "repositories.",
    "database",
    "reports.",
    "isis.",
)

PATCHES_LAUNCHER = [
    "app_backup_inicializacao_patch",
    "app_runtime_patch",
    "app_pagamento_misto_patch",
    "app_sync_pagamento_misto_payload_patch",
    "app_caixa_fechamento_avancado_patch",
    "app_backup_painel_patch",
    "app_manutencao_segura_patch",
    "app_sync_status_patch",
    "app_painel_guard_patch",
    "app_scroll_patch",
]

FUNCOES_CAIXA_OBRIGATORIAS = [
    "abrir_caixa",
    "excluir_conta",
    "fechar_caixa_conferido",
    "fechar_caixa_simples",
    "lancar_fluxo",
    "listar_contas",
    "listar_fluxo",
    "marcar_conta_paga",
    "obter_caixa_id_ativo",
    "obter_conta",
    "resumo_fechamento_caixa",
    "salvar_conta",
    "status_caixa_aberto",
    "caixa_abertos_count",
]


def falhar(mensagem: str) -> None:
    print(f"[ERRO] {mensagem}")
    raise SystemExit(1)


def validar_sintaxe() -> None:
    for caminho in ARQUIVOS_CRITICOS:
        if not caminho.exists():
            falhar(f"Arquivo critico nao encontrado: {caminho.relative_to(ROOT)}")
        try:
            ast.parse(caminho.read_text(encoding="utf-8-sig"), filename=str(caminho))
        except SyntaxError as exc:
            falhar(f"Erro de sintaxe em {caminho.relative_to(ROOT)}: {exc}")
    print("[OK] Sintaxe dos arquivos criticos validada.")


def importar_modulo(nome: str):
    try:
        return importlib.import_module(nome)
    except Exception as exc:
        falhar(f"Nao consegui importar {nome}: {exc}")


def validar_caixa_service() -> None:
    mod = importar_modulo("services.caixa_service")
    faltando = [nome for nome in FUNCOES_CAIXA_OBRIGATORIAS if not hasattr(mod, nome)]
    if faltando:
        falhar("services.caixa_service esta sem: " + ", ".join(faltando))
    print("[OK] services.caixa_service possui todas as funcoes obrigatorias.")


def validar_imports_arquivo(caminho: Path) -> None:
    arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"), filename=str(caminho))
    for node in ast.walk(arvore):
        if not isinstance(node, ast.ImportFrom):
            continue
        modulo = node.module or ""
        if not (modulo == "database" or modulo.startswith(PREFIXOS_AUDITADOS)):
            continue
        mod = importar_modulo(modulo)
        for alias in node.names:
            if alias.name == "*":
                continue
            if not hasattr(mod, alias.name):
                falhar(f"{caminho.relative_to(ROOT)} importa {alias.name} de {modulo}, mas a funcao/objeto nao existe.")
    print(f"[OK] Imports auditados em {caminho.relative_to(ROOT)}.")


def validar_patches_launcher() -> None:
    for nome in PATCHES_LAUNCHER:
        caminho = ROOT / f"{nome}.py"
        if not caminho.exists():
            falhar(f"Patch esperado pelo Launcher nao existe: {nome}.py")
        importar_modulo(nome)
    print("[OK] Patches do Launcher existem e importam corretamente.")


def main() -> None:
    validar_sintaxe()
    validar_caixa_service()
    validar_imports_arquivo(ROOT / "mistica_presentes.py")
    validar_patches_launcher()
    print("AUDITORIA_RUNTIME_IMPORTS_OK")


if __name__ == "__main__":
    main()
