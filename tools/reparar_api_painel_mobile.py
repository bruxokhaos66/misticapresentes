import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from tools.sincronizar_painel_online import main as sincronizar_painel
from tools.comparar_dashboard_app import main as comparar


def main():
    init_db()
    print("=== REPARO DO PAINEL MOBILE ===")
    print("1/2 Sincronizando usuarios, produtos e vendas para a API...")
    sincronizar_painel()
    print("\n2/2 Comparando desktop x app/API depois do reparo...")
    comparar()
    print("\nSe API/App ainda aparecer zerada, aguarde 10 segundos e rode este comando novamente.")


if __name__ == "__main__":
    main()
