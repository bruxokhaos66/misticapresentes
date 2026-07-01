"""Executa a auditoria semanal da Isis.

Este script pode ser chamado pelo Agendador de Tarefas do Windows.
Ele usa o banco real configurado no sistema, cria backup, confere estrutura,
normaliza dados basicos e salva relatorio em Documentos/Mistica_Auditorias.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.auditoria_service import executar_auditoria_sistema, resumo_curto_auditoria


def main():
    relatorio = executar_auditoria_sistema(corrigir=True, origem="agendador_windows")
    print(resumo_curto_auditoria(relatorio))
    if relatorio.get("problemas"):
        print("\nPontos de atencao:")
        for item in relatorio.get("problemas", []):
            print("-", item)
    if relatorio.get("correcoes"):
        print("\nAcoes seguras realizadas:")
        for item in relatorio.get("correcoes", []):
            print("-", item)


if __name__ == "__main__":
    main()
