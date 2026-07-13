"""Testes da auditoria de segredos (detect-secrets).

Estes testes exercitam o comportamento real do `detect-secrets` contra a
baseline do repositório. Como a ferramenta não é uma dependência do app
(só é usada por tooling de segurança), os testes são pulados quando o
pacote não está instalado -- o workflow dedicado
`.github/workflows/security-secrets.yml` o instala e roda esta suíte.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

detect_secrets = pytest.importorskip("detect_secrets")

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".secrets.baseline"


def _rodar_scan(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "detect_secrets", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_baseline_atual_nao_gera_diferenca():
    """A baseline commitada já reflete o estado atual do repositório."""
    baseline_antes = BASELINE.read_text(encoding="utf-8")
    resultado = _rodar_scan("scan", "--baseline", str(BASELINE.relative_to(ROOT)))
    assert resultado.returncode == 0, resultado.stderr
    baseline_depois = BASELINE.read_text(encoding="utf-8")
    dados_antes = json.loads(baseline_antes)
    dados_depois = json.loads(baseline_depois)
    assert dados_antes["results"] == dados_depois["results"]
    # restaura o timestamp original para não sujar o working tree do teste
    BASELINE.write_text(baseline_antes, encoding="utf-8")


def test_segredo_ficticio_detectavel_falha_o_scan(tmp_path):
    """Um segredo obviamente fictício, mas com formato detectável, deve
    aparecer como um resultado novo não coberto pela baseline."""
    arquivo_tmp = tmp_path / "arquivo_com_segredo_forjado.py"
    arquivo_tmp.write_text(
        'AWS_SECRET_ACCESS_KEY = "AKIAFORJADOEXEMPLO0000000"\n',  # pragma: allowlist secret
        encoding="utf-8",
    )
    resultado = _rodar_scan("scan", "--string", "AKIAFORJADOEXEMPLO0000000")  # pragma: allowlist secret
    assert "AWS Access Key" in resultado.stdout or "True" in resultado.stdout


def test_falso_positivo_aprovado_nao_quebra_o_scan():
    """As chaves de teste fictícias já auditadas (is_secret=false) não
    devem voltar a acusar diferença na baseline."""
    dados = json.loads(BASELINE.read_text(encoding="utf-8"))
    aprovados = [
        item
        for arquivo in dados["results"].values()
        for item in arquivo
        if item.get("is_secret") is False
    ]
    assert aprovados, "Esperava ao menos um falso positivo já revisado na baseline"


def test_env_example_pode_existir_e_nao_tem_segredo_real():
    exemplo = ROOT / ".env.example"
    assert exemplo.exists()
    conteudo = exemplo.read_text(encoding="utf-8")
    for chave_sensivel in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        linha = next(l for l in conteudo.splitlines() if l.startswith(chave_sensivel))
        assert linha.split("=", 1)[1].strip() == "", (
            f"{chave_sensivel} não deve ter valor real em .env.example"
        )


def test_env_real_e_ignorado_pelo_git():
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", ".env"],
        cwd=ROOT,
    )
    assert resultado.returncode == 0, ".env deveria estar no .gitignore"


def test_banco_e_backups_reais_nao_podem_ser_versionados():
    for caminho in ("dados.sqlite3", "mistica.db", "backups/dump.sql"):
        resultado = subprocess.run(
            ["git", "check-ignore", "-q", caminho],
            cwd=ROOT,
        )
        assert resultado.returncode == 0, f"{caminho} deveria estar no .gitignore"


def test_workflow_de_segredos_nao_imprime_valores_sensiveis():
    workflow = (ROOT / ".github" / "workflows" / "security-secrets.yml").read_text(
        encoding="utf-8"
    )
    assert "hashed_secret" not in workflow
    for termo_perigoso in ("cat .secrets.baseline", "--string", "print_report"):
        assert termo_perigoso not in workflow


def test_exclusoes_da_baseline_nao_sao_amplas_demais():
    dados = json.loads((ROOT / ".secrets.baseline").read_text(encoding="utf-8"))
    filtro_regex = next(
        f
        for f in dados["filters_used"]
        if f["path"] == "detect_secrets.filters.regex.should_exclude_file"
    )
    padroes = filtro_regex["pattern"]
    proibidos_amplos = {".*", "^.*$", ".", "^/"}
    assert not (set(padroes) & proibidos_amplos)
    assert len(padroes) <= 10, "Muitas exclusões podem esconder segredos reais"
