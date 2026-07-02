import os
from datetime import datetime

from config import DASHBOARD_MSG_PATH
from database import query_db
from services.system_diagnostics_service import backup_manual, diagnosticar_banco


class PermissaoNegada(ValueError):
    pass


def _nome_usuario(usuario):
    if isinstance(usuario, dict):
        return usuario.get("nome") or usuario.get("login") or "Sistema"
    return str(usuario or "Sistema")


def _perfil_usuario(usuario):
    if isinstance(usuario, dict):
        return str(usuario.get("perfil") or "").lower()
    return ""


def exigir_adm(usuario):
    if _perfil_usuario(usuario) != "adm":
        raise PermissaoNegada("Apenas perfil adm pode executar manutenção do sistema.")
    return True


def registrar_log_manutencao(usuario, acao, detalhes):
    query_db(
        "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
        (
            _nome_usuario(usuario),
            f"Manutenção - {acao}",
            detalhes,
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        ),
        commit=True,
    )


def reiniciar_dashboard(usuario):
    """Reinicia apenas o estado visual/configurável do dashboard.

    Não apaga vendas, caixa, estoque ou financeiro.
    """
    exigir_adm(usuario)
    removeu_msg = False
    if os.path.exists(DASHBOARD_MSG_PATH):
        os.remove(DASHBOARD_MSG_PATH)
        removeu_msg = True
    registrar_log_manutencao(
        usuario,
        "Reiniciar Dashboard",
        "Dashboard visual reiniciado; mensagem personalizada removida." if removeu_msg else "Dashboard visual reiniciado; não havia mensagem personalizada.",
    )
    return {
        "ok": True,
        "area": "dashboard",
        "acao": "reiniciar_visual",
        "removeu_mensagem_personalizada": removeu_msg,
        "mensagem": "Dashboard reiniciado visualmente sem apagar dados reais.",
    }


def diagnosticar_caixa(usuario):
    exigir_adm(usuario)
    caixas_abertos = query_db("SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'")[0][0] or 0
    fluxo_sem_caixa = query_db("SELECT COUNT(*) FROM fluxo_caixa WHERE caixa_id IS NULL")[0][0] or 0
    ultimos = query_db(
        """
        SELECT id, data_abertura, data_fechamento, saldo_inicial, saldo_final, status
        FROM caixa_diario
        ORDER BY id DESC
        LIMIT 10
        """
    )
    problemas = []
    if int(caixas_abertos) > 1:
        problemas.append("Existe mais de um caixa aberto.")
    if int(fluxo_sem_caixa) > 0:
        problemas.append("Existem lançamentos de fluxo sem caixa vinculado.")
    registrar_log_manutencao(usuario, "Diagnosticar Caixa", f"Caixas abertos: {caixas_abertos}; fluxo sem caixa: {fluxo_sem_caixa}")
    return {
        "ok": not problemas,
        "area": "caixa",
        "caixas_abertos": int(caixas_abertos),
        "fluxo_sem_caixa": int(fluxo_sem_caixa),
        "ultimos_caixas": ultimos,
        "problemas": problemas,
    }


def diagnosticar_estoque(usuario):
    exigir_adm(usuario)
    negativos = query_db("SELECT codigo_p, nome, quantidade FROM produtos WHERE COALESCE(quantidade,0) < 0 ORDER BY nome")
    baixos = query_db(
        """
        SELECT codigo_p, nome, quantidade, estoque_minimo
        FROM produtos
        WHERE COALESCE(ativo,1)=1 AND COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0)
        ORDER BY quantidade ASC, nome
        LIMIT 100
        """
    )
    sem_categoria = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND COALESCE(categoria,'')='' ")[0][0] or 0
    problemas = []
    if negativos:
        problemas.append(f"Existem {len(negativos)} produto(s) com estoque negativo.")
    if int(sem_categoria) > 0:
        problemas.append(f"Existem {sem_categoria} produto(s) sem categoria.")
    registrar_log_manutencao(usuario, "Diagnosticar Estoque", f"Negativos: {len(negativos)}; baixos: {len(baixos)}; sem categoria: {sem_categoria}")
    return {
        "ok": not problemas,
        "area": "estoque",
        "produtos_negativos": negativos,
        "produtos_baixos": baixos,
        "produtos_sem_categoria": int(sem_categoria),
        "problemas": problemas,
    }


def diagnosticar_financeiro(usuario):
    exigir_adm(usuario)
    contas_pendentes = query_db("SELECT COUNT(*), COALESCE(SUM(valor),0) FROM contas_a_pagar WHERE status='Pendente'")[0]
    contas_pagas_sem_fluxo = query_db(
        """
        SELECT COUNT(*)
        FROM contas_a_pagar c
        WHERE c.status='Pago'
          AND NOT EXISTS (
            SELECT 1 FROM fluxo_caixa f
            WHERE f.descricao LIKE '%' || c.descricao || '%'
          )
        """
    )[0][0] or 0
    vendas_sem_fluxo = query_db(
        """
        SELECT COUNT(*)
        FROM vendas v
        WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
          AND NOT EXISTS (
            SELECT 1 FROM fluxo_caixa f
            WHERE f.descricao LIKE '%Venda no ' || v.id || '%'
          )
        """
    )[0][0] or 0
    problemas = []
    if int(contas_pagas_sem_fluxo) > 0:
        problemas.append(f"Existem {contas_pagas_sem_fluxo} conta(s) pagas sem fluxo localizado.")
    if int(vendas_sem_fluxo) > 0:
        problemas.append(f"Existem {vendas_sem_fluxo} venda(s) concluídas sem fluxo localizado.")
    registrar_log_manutencao(
        usuario,
        "Diagnosticar Financeiro",
        f"Pendentes: {contas_pendentes[0]}; valor pendente: {contas_pendentes[1]}; contas pagas sem fluxo: {contas_pagas_sem_fluxo}; vendas sem fluxo: {vendas_sem_fluxo}",
    )
    return {
        "ok": not problemas,
        "area": "financeiro",
        "contas_pendentes": int(contas_pendentes[0] or 0),
        "valor_pendente": float(contas_pendentes[1] or 0),
        "contas_pagas_sem_fluxo": int(contas_pagas_sem_fluxo),
        "vendas_sem_fluxo": int(vendas_sem_fluxo),
        "problemas": problemas,
    }


def reiniciar_area_segura(area, usuario):
    """Executa reinício seguro/diagnóstico de área, sem apagar dados reais."""
    exigir_adm(usuario)
    area_norm = str(area or "").strip().lower()
    if area_norm == "dashboard":
        return reiniciar_dashboard(usuario)
    if area_norm == "caixa":
        return diagnosticar_caixa(usuario)
    if area_norm == "estoque":
        return diagnosticar_estoque(usuario)
    if area_norm == "financeiro":
        return diagnosticar_financeiro(usuario)
    if area_norm in {"sistema", "geral", "todos"}:
        backup = backup_manual()
        geral = diagnosticar_banco()
        caixa = diagnosticar_caixa(usuario)
        estoque = diagnosticar_estoque(usuario)
        financeiro = diagnosticar_financeiro(usuario)
        registrar_log_manutencao(usuario, "Reiniciar/Diagnosticar Geral", f"Backup criado: {backup}")
        return {
            "ok": geral.get("ok") and caixa.get("ok") and estoque.get("ok") and financeiro.get("ok"),
            "area": "geral",
            "backup": backup,
            "diagnostico_geral": geral,
            "caixa": caixa,
            "estoque": estoque,
            "financeiro": financeiro,
        }
    raise ValueError("Área inválida. Use dashboard, caixa, estoque, financeiro ou geral.")
