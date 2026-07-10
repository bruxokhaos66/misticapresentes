import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

# Tabelas cujo dono é database/migrations.py (fonte única de verdade do schema).
# Qualquer ALTER/CREATE TABLE fora daqui para essas tabelas é regressão da
# consolidação de schema (ver commit "Consolidar schema do banco num único
# lugar"). Tabelas de domínios não cobertos por este projeto (ex: música/curso
# do site) continuam podendo definir sua própria tabela onde são usadas.
TABELAS_COM_DONO_UNICO = {
    "produtos",
    "vendas",
    "pedidos",
    "pedidos_itens",
    "pedido_status_log",
    "pagamentos",
    "audit_log",
    "idempotency_keys",
}

PADRAO = re.compile(r"(?:ALTER TABLE|CREATE TABLE(?: IF NOT EXISTS)?)\s+(\w+)", re.IGNORECASE)


def test_schema_das_tabelas_principais_so_e_definido_em_migrations():
    ofensores = []
    for path in BACKEND_DIR.glob("*.py"):
        conteudo = path.read_text(encoding="utf-8")
        for match in PADRAO.finditer(conteudo):
            tabela = match.group(1)
            if tabela in TABELAS_COM_DONO_UNICO:
                ofensores.append(f"{path.name}: {tabela}")
    assert not ofensores, (
        "Definição de schema fora de database/migrations.py: "
        + ", ".join(ofensores)
    )


def test_validacao_de_chave_de_api_tem_implementacao_unica():
    """As rotas que exigem MISTICA_SITE_API_KEY/MISTICA_SYNC_KEY devem delegar
    para backend/api_security.py::validar_site_api_key, não reimplementar a
    checagem (ver commit "Consolidar validação de chave da API")."""
    ofensores = []
    for path in BACKEND_DIR.glob("*.py"):
        if path.name == "api_security.py":
            continue
        conteudo = path.read_text(encoding="utf-8")
        if "def validar_site_api_key" not in conteudo:
            continue
        if "validar_chave_api(" not in conteudo:
            ofensores.append(path.name)
    assert not ofensores, (
        "validar_site_api_key reimplementado (sem delegar para api_security.py) em: "
        + ", ".join(ofensores)
    )
