"""CLI operacional de restore/disaster recovery do banco SQLite.

Uso:
    python scripts/restaurar_backup.py --listar
    python scripts/restaurar_backup.py --arquivo backup_2026-07-15_03-00-00.db --confirmar
    python scripts/restaurar_backup.py --rollback --confirmar

Sem `--confirmar`, o script só valida o candidato (dry-run) e mostra o que
faria -- nunca troca o banco em uso sem confirmação explícita do operador.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import BACKUP_DIR, DB_PATH
from database.restore import (
    listar_backups_disponiveis,
    reverter_ultimo_restore,
    restaurar_backup,
    validar_candidato_restore,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listar", action="store_true", help="Lista backups disponíveis para restore")
    parser.add_argument("--arquivo", help="Nome do arquivo de backup (dentro do diretório de backups) ou caminho completo")
    parser.add_argument("--confirmar", action="store_true", help="Executa a troca real; sem isso, só valida (dry-run)")
    parser.add_argument("--rollback", action="store_true", help="Reverte para a cópia preservada antes do último restore")
    parser.add_argument("--usuario", default="operador_cli", help="Identificação do operador, para auditoria")
    args = parser.parse_args()

    if args.listar:
        for item in listar_backups_disponiveis():
            print(f"{item['nome']}  {item['tamanho_bytes']} bytes  {item['modificado_em']}  checksum={item['checksum_disponivel']}")
        return 0

    if args.rollback:
        if not args.confirmar:
            print("Rollback é uma operação real de troca de banco. Rode novamente com --confirmar.")
            return 2
        resultado = reverter_ultimo_restore(usuario=args.usuario)
        print(resultado)
        return 0 if resultado.status == "ok" else 1

    if not args.arquivo:
        parser.error("informe --arquivo, --rollback ou --listar")

    caminho = Path(args.arquivo)
    if not caminho.is_absolute() and not caminho.exists():
        caminho = Path(BACKUP_DIR) / args.arquivo

    if not args.confirmar:
        validacao = validar_candidato_restore(caminho)
        print(f"[dry-run] válido={validacao.valido} motivo={validacao.motivo} tabelas_ausentes={validacao.tabelas_ausentes}")
        print(f"[dry-run] banco atual não foi tocado ({DB_PATH}). Rode novamente com --confirmar para restaurar de verdade.")
        return 0 if validacao.valido else 1

    resultado = restaurar_backup(caminho, usuario=args.usuario)
    print(resultado)
    return 0 if resultado.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
