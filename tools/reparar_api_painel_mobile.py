import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from services.painel_online_guard import diagnosticar_api_painel, resultado_resumido, sincronizar_painel_completo
from tools.sincronizar_painel_online import main as sincronizar_painel
from tools.comparar_dashboard_app import main as comparar


def main():
    init_db()
    print("=== REPARO DO PAINEL MOBILE ===")
    print("Diagnostico antes:", diagnosticar_api_painel())
    print("1/2 Sincronizando usuarios, produtos e vendas para a API...")
    resultado = sincronizar_painel_completo()
    print("Resultado do reparo:", resultado_resumido(resultado))
    if resultado.get("status") == "erro":
        print("Fallback: tentando sincronizacao direta...")
        sincronizar_painel()
    print("\n2/2 Comparando desktop x app/API depois do reparo...")
    comparar()
    print("Diagnostico depois:", diagnosticar_api_painel())
    print("\nSe API/App ainda aparecer zerada, aguarde 10 segundos e rode este comando novamente.")


if __name__ == "__main__":
    main()
