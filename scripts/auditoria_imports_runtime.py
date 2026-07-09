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
    ROOT / "services" / "producao_service.py",
    ROOT / "scripts" / "gerar_pacote_atualizacao.py",
    ROOT / "scripts" / "gerar_manifestos_canais.py",
    ROOT / "scripts" / "gerar_icone_mistica.py",
    ROOT / "scripts" / "preparar_sistema_producao.py",
]

ARQUIVOS_OBRIGATORIOS = [
    "mistica_presentes.py",
    "MisticaLauncher.py",
    "auto_updater.py",
    "app_version.py",
    "release_notes.py",
    "config.py",
    "services/producao_service.py",
    "installer/Instalar_Mistica_Presentes.bat",
    "scripts/gerar_pacote_atualizacao.py",
    "scripts/gerar_manifestos_canais.py",
    "scripts/gerar_icone_mistica.py",
    "scripts/preparar_sistema_producao.py",
    ".github/workflows/build-instalador-windows.yml",
    ".github/workflows/build-launcher.yml",
    ".github/workflows/publish-online-update.yml",
]

PASTAS_OBRIGATORIAS = [
    "database",
    "repositories",
    "services",
    "isis",
    "reports",
    "assets",
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

FUNCOES_VENDA_OBRIGATORIAS = [
    "calcular_total_venda",
    "calcular_total_venda_misto",
    "registrar_venda_service",
    "cancelar_venda_service",
    "consultar_venda_salva",
    "obter_resumo_venda",
    "normalizar_forma_pagamento",
    "dinheiro_para_float",
]

FUNCOES_PRODUCAO_OBRIGATORIAS = [
    "preparar_sistema_para_producao",
]


def falhar(mensagem: str) -> None:
    print(f"[ERRO] {mensagem}")
    raise SystemExit(1)


def validar_estrutura() -> None:
    for item in ARQUIVOS_OBRIGATORIOS:
        if not (ROOT / item).exists():
            falhar(f"Arquivo obrigatorio ausente: {item}")
    for pasta in PASTAS_OBRIGATORIAS:
        if not (ROOT / pasta).is_dir():
            falhar(f"Pasta obrigatoria ausente: {pasta}")
    print("[OK] Estrutura obrigatoria validada.")


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


def validar_funcoes_obrigatorias(modulo_nome: str, funcoes: list[str]) -> None:
    mod = importar_modulo(modulo_nome)
    faltando = [nome for nome in funcoes if not hasattr(mod, nome)]
    if faltando:
        falhar(f"{modulo_nome} esta sem: " + ", ".join(faltando))
    print(f"[OK] {modulo_nome} possui todas as funcoes obrigatorias.")


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


def validar_gerador_pacote() -> None:
    mod = importar_modulo("scripts.gerar_pacote_atualizacao")
    arquivos = list(getattr(mod, "INCLUIR_ARQUIVOS", []) or [])
    pastas = list(getattr(mod, "INCLUIR_PASTAS", []) or [])
    obrigatorios = ["mistica_presentes.py", "MisticaLauncher.py", "auto_updater.py", "app_version.py", "release_notes.py", "config.py"]
    faltando = [nome for nome in obrigatorios if nome not in arquivos]
    if faltando:
        falhar("Gerador de pacote nao inclui arquivos obrigatorios: " + ", ".join(faltando))
    for pasta in ["assets", "services", "database", "repositories", "reports", "isis"]:
        if pasta not in pastas:
            falhar(f"Gerador de pacote nao inclui pasta obrigatoria: {pasta}")
    print("[OK] Gerador de pacote inclui arquivos e pastas obrigatorias.")


def validar_instalador() -> None:
    bat = (ROOT / "installer" / "Instalar_Mistica_Presentes.bat").read_text(encoding="utf-8-sig", errors="ignore")
    checks = [
        "MisticaLauncher.exe",
        "Mistica Presentes.lnk",
        "GetFolderPath('Desktop')",
        "mistica_xamanico_moderno.ico",
    ]
    for trecho in checks:
        if trecho not in bat:
            falhar(f"Instalador nao contem trecho obrigatorio: {trecho}")
    print("[OK] Instalador cria atalho principal para o Launcher com icone.")


def validar_botao_producao() -> None:
    patch = (ROOT / "app_manutencao_segura_patch.py").read_text(encoding="utf-8-sig", errors="ignore")
    checks = [
        "PREPARAR SISTEMA PARA PRODUÇÃO",
        "preparar_sistema_producao_manutencao",
        "preparar_sistema_para_producao",
        "CONFIRMAR",
    ]
    for trecho in checks:
        if trecho not in patch:
            falhar(f"Patch de manutencao nao contem trecho obrigatorio: {trecho}")
    print("[OK] Botao seguro de preparacao para producao validado.")


def main() -> None:
    validar_estrutura()
    validar_sintaxe()
    validar_funcoes_obrigatorias("services.caixa_service", FUNCOES_CAIXA_OBRIGATORIAS)
    validar_funcoes_obrigatorias("services.venda_service", FUNCOES_VENDA_OBRIGATORIAS)
    validar_funcoes_obrigatorias("services.producao_service", FUNCOES_PRODUCAO_OBRIGATORIAS)
    validar_imports_arquivo(ROOT / "mistica_presentes.py")
    validar_imports_arquivo(ROOT / "MisticaLauncher.py")
    validar_patches_launcher()
    validar_gerador_pacote()
    validar_instalador()
    validar_botao_producao()
    print("AUDITORIA_RUNTIME_IMPORTS_OK")


if __name__ == "__main__":
    main()
