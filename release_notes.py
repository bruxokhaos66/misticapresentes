RELEASE_VERSION = "1.0.517"
RELEASE_TITLE = "Auditoria automatica de imports e Launcher"
RELEASE_NOTES = "Adiciona uma auditoria automatica para impedir que atualizacoes ou builds do Launcher sejam publicados quando faltar alguma funcao importada pelo app principal."
RELEASE_CHANGES = [
    "Cria scripts/auditoria_imports_runtime.py.",
    "Workflow Publish Online Update passa a validar imports antes de publicar pacote.",
    "Workflow Build Mistica Launcher passa a validar imports antes de gerar o executavel.",
    "A auditoria verifica funcoes obrigatorias do services.caixa_service.",
    "Reduz risco de novas atualizacoes quebrarem por import ausente.",
]
