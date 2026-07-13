"""Verificações seguras de infraestrutura (banco e disco).

Usadas pelo endpoint público /api/health (checagem leve, sem escrita em
disco) e pelo diagnóstico autenticado em system_status_routes.py (checagem
completa, com teste real de escrita). Nenhuma função aqui devolve caminhos,
variáveis de ambiente ou mensagens de erro internas: apenas booleans,
números e códigos curtos de motivo, seguros para expor mesmo sem
autenticação.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from config import DB_PATH

# Limiares de classificação do espaço livre em disco, configuráveis por
# variável de ambiente (padrão conservador). Usados só pelo diagnóstico
# autenticado -- o health público não calcula espaço em disco.
LIMIAR_ATENCAO_PERCENT = float(os.environ.get("MISTICA_DISCO_LIMIAR_ATENCAO_PERCENT", "20") or "20")
LIMIAR_CRITICO_PERCENT = float(os.environ.get("MISTICA_DISCO_LIMIAR_CRITICO_PERCENT", "10") or "10")


def banco_acessivel() -> bool:
    """Confirma que o banco abre e responde a uma consulta simples (leitura)."""
    try:
        from backend.database import conectar

        with conectar() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def disco_diretorio_disponivel() -> bool:
    """Checagem leve para o /api/health público: só confirma que a pasta do
    banco existe e o processo tem permissão de escrita segundo o SO, sem
    criar/remover arquivo a cada chamada (o health é chamado com frequência
    por monitores de uptime e não deve gerar I/O de disco repetido)."""
    try:
        pasta = Path(DB_PATH).parent
        return pasta.is_dir() and os.access(pasta, os.W_OK)
    except Exception:
        return False


def escrita_disco_segura() -> tuple[bool, str]:
    """Testa criação e remoção de um arquivo temporário dentro da pasta do
    banco. Só usada pelo diagnóstico autenticado (não pelo health público).

    Retorna (sucesso, motivo). O motivo é um código curto e seguro (nunca
    stack trace nem caminho) que distingue diretório inexistente, permissão
    negada, filesystem somente leitura, falta de espaço, falha ao criar o
    arquivo, caminho inesperado (defesa contra symlink/traversal apontando
    para fora da pasta esperada) e falha ao remover o arquivo de teste.
    """
    try:
        pasta = Path(DB_PATH).parent
    except Exception:
        return False, "caminho_invalido"

    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False, "permissao_negada"
    except OSError:
        return False, "diretorio_inexistente"

    try:
        pasta_resolvida = pasta.resolve(strict=True)
    except OSError:
        return False, "diretorio_inexistente"

    try:
        fd, tmp_nome = tempfile.mkstemp(dir=pasta_resolvida, prefix=".mistica_health_")
    except PermissionError:
        return False, "permissao_negada"
    except OSError as exc:
        if getattr(exc, "errno", None) == 28:  # ENOSPC
            return False, "sem_espaco"
        if getattr(exc, "errno", None) == 30:  # EROFS
            return False, "somente_leitura"
        return False, "falha_criacao"

    tmp_path = Path(tmp_nome)
    try:
        # Defesa contra symlink/traversal: o arquivo criado precisa mesmo
        # estar dentro da pasta esperada, nunca redirecionado para fora.
        if pasta_resolvida not in tmp_path.resolve().parents:
            os.close(fd)
            tmp_path.unlink(missing_ok=True)
            return False, "caminho_inesperado"

        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b"healthcheck")
        except OSError as exc:
            if getattr(exc, "errno", None) == 28:
                return False, "sem_espaco"
            if getattr(exc, "errno", None) == 30:
                return False, "somente_leitura"
            return False, "falha_criacao"
    finally:
        # A remoção é tentada mesmo se a escrita falhou, para nunca deixar
        # arquivo de teste para trás.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            return False, "falha_remocao"

    return True, "ok"


def espaco_disco_bytes() -> dict[str, int] | None:
    """Espaço livre/total/usado (em bytes) do disco onde o banco vive.

    Só números, sem caminho: quem chama decide se e como expor o resultado.
    """
    try:
        pasta = Path(DB_PATH).parent
        uso = shutil.disk_usage(pasta)
        return {"livre_bytes": uso.free, "total_bytes": uso.total, "usado_bytes": uso.used}
    except Exception:
        return None


def classificar_espaco_livre(livre_percentual: float) -> str:
    """Classifica o espaço livre em disco: 'saudavel', 'atencao' ou 'critico'."""
    if livre_percentual <= LIMIAR_CRITICO_PERCENT:
        return "critico"
    if livre_percentual <= LIMIAR_ATENCAO_PERCENT:
        return "atencao"
    return "saudavel"


def diagnostico_disco_completo() -> dict:
    """Diagnóstico completo de disco para o endpoint autenticado: checagem
    de diretório, teste real de escrita/remoção e classificação de espaço
    livre por limiares configuráveis. Nunca inclui caminho absoluto."""
    escreveu, motivo = escrita_disco_segura()
    espaco = espaco_disco_bytes()

    livre_percentual = None
    classificacao = "desconhecido"
    if espaco and espaco["total_bytes"] > 0:
        livre_percentual = round(espaco["livre_bytes"] / espaco["total_bytes"] * 100, 1)
        classificacao = classificar_espaco_livre(livre_percentual)

    return {
        "acessivel": disco_diretorio_disponivel(),
        "escrita_ok": escreveu,
        "escrita_motivo": motivo,
        "espaco_livre_percentual": livre_percentual,
        "classificacao": classificacao,
        "espaco_livre_bytes": espaco["livre_bytes"] if espaco else None,
        "espaco_total_bytes": espaco["total_bytes"] if espaco else None,
    }
