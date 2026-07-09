from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.producao_service import preparar_sistema_para_producao


def perguntar_bool(texto: str, padrao: bool = True) -> bool:
    sufixo = "S/n" if padrao else "s/N"
    resp = input(f"{texto} [{sufixo}]: ").strip().lower()
    if not resp:
        return padrao
    return resp in {"s", "sim", "y", "yes"}


def main() -> None:
    print("MISTICA PRESENTES - PREPARAR SISTEMA PARA PRODUCAO")
    print("=" * 60)
    print("Esta ferramenta cria backup e limpa dados de teste.")
    print("Use somente antes de iniciar o uso real na loja.")
    print()
    confirmacao = input("Digite CONFIRMAR para continuar: ").strip().upper()
    if confirmacao != "CONFIRMAR":
        print("Cancelado. Nenhum dado foi apagado.")
        return

    remover_produtos = perguntar_bool("Apagar produtos ficticios? Se nao, apenas zera estoque", True)
    remover_clientes = perguntar_bool("Apagar clientes de teste?", True)
    remover_fornecedores = perguntar_bool("Apagar fornecedores de teste?", True)
    limpar_memoria_isis = perguntar_bool("Limpar memoria/aprendizados de teste da Isis?", False)

    res = preparar_sistema_para_producao(
        operador="Script manual",
        remover_produtos=remover_produtos,
        remover_clientes=remover_clientes,
        remover_fornecedores=remover_fornecedores,
        limpar_memoria_isis=limpar_memoria_isis,
    )
    print()
    print("Concluido.")
    print("Backup:", res.get("backup"))
    print("Relatorio:", res.get("relatorio"))
    print("Registros removidos:", res.get("total_removido"))


if __name__ == "__main__":
    main()
