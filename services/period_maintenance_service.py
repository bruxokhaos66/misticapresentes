from datetime import datetime

from database import get_connection, query_db
from services.system_diagnostics_service import backup_manual


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
        raise PermissionError("Apenas perfil adm pode executar manutenção por período.")


def _registrar_log(usuario, acao, detalhes):
    query_db(
        "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
        (_nome_usuario(usuario), f"Manutenção - {acao}", detalhes, datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        commit=True,
    )


def intervalo_periodo(tipo, dia=None, mes=None, ano=None):
    tipo = str(tipo or "dia").strip().lower()
    ano = int(ano or datetime.now().year)
    mes = int(mes or datetime.now().month)
    if tipo == "mes":
        ini = datetime(ano, mes, 1)
        fim = datetime(ano + 1, 1, 1) if mes == 12 else datetime(ano, mes + 1, 1)
        rotulo = f"{mes:02d}/{ano}"
    else:
        dia = int(dia or datetime.now().day)
        ini = datetime(ano, mes, dia)
        fim = ini.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        fim = fim + timedelta(days=1)
        rotulo = f"{dia:02d}/{mes:02d}/{ano}"
    return ini.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S"), rotulo


def _where_data_iso(coluna="data_iso"):
    return f"datetime(CASE WHEN length(COALESCE({coluna}, '')) = 10 THEN {coluna} || ' 00:00:00' ELSE {coluna} END) >= datetime(?) AND datetime(CASE WHEN length(COALESCE({coluna}, '')) = 10 THEN {coluna} || ' 00:00:00' ELSE {coluna} END) < datetime(?)"


def listar_vendas_periodo(usuario, tipo="dia", dia=None, mes=None, ano=None):
    exigir_adm(usuario)
    ini, fim, rotulo = intervalo_periodo(tipo, dia, mes, ano)
    vendas = query_db(
        f"""
        SELECT id, data_venda, cliente, total_final, forma_pagamento, vendedor, COALESCE(status,'Concluído')
        FROM vendas
        WHERE {_where_data_iso('data_iso')}
        ORDER BY id DESC
        """,
        (ini, fim),
    )
    total_ativas = sum(float(v[3] or 0) for v in vendas if str(v[6]).lower() != "cancelado")
    return {"periodo": rotulo, "inicio": ini, "fim": fim, "vendas": vendas, "total_ativas": total_ativas}


def listar_lancamentos_caixa_periodo(usuario, tipo="dia", dia=None, mes=None, ano=None):
    exigir_adm(usuario)
    ini, fim, rotulo = intervalo_periodo(tipo, dia, mes, ano)
    lancamentos = query_db(
        f"""
        SELECT id, tipo, descricao, valor, data_hora, caixa_id, forma_pagamento, data_iso
        FROM fluxo_caixa
        WHERE {_where_data_iso('data_iso')}
        ORDER BY id DESC
        """,
        (ini, fim),
    )
    total = sum(float(l[3] or 0) for l in lancamentos)
    return {"periodo": rotulo, "inicio": ini, "fim": fim, "lancamentos": lancamentos, "total": total}


def zerar_vendas_e_caixa_periodo(usuario, tipo="dia", dia=None, mes=None, ano=None, motivo="Correção administrativa"):
    """Zera dashboards do período com rastreabilidade.

    Não apaga produtos nem estoque. As vendas do período são marcadas como Cancelado para saírem dos KPIs.
    Os lançamentos do caixa dentro do período são removidos do fluxo_caixa após backup.
    """
    exigir_adm(usuario)
    ini, fim, rotulo = intervalo_periodo(tipo, dia, mes, ano)
    backup = backup_manual()
    conn = get_connection()
    cur = conn.cursor()
    try:
        vendas = cur.execute(
            f"SELECT id, total_final, COALESCE(status,'Concluído') FROM vendas WHERE {_where_data_iso('data_iso')}",
            (ini, fim),
        ).fetchall()
        vendas_ativas = [v for v in vendas if str(v[2]).lower() != "cancelado"]
        total_vendas = sum(float(v[1] or 0) for v in vendas_ativas)
        ids_vendas = [str(v[0]) for v in vendas_ativas]

        cur.execute(
            f"UPDATE vendas SET status='Cancelado' WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {_where_data_iso('data_iso')}",
            (ini, fim),
        )
        vendas_canceladas = cur.rowcount

        lancamentos = cur.execute(
            f"SELECT id, valor FROM fluxo_caixa WHERE {_where_data_iso('data_iso')}",
            (ini, fim),
        ).fetchall()
        total_fluxo = sum(float(l[1] or 0) for l in lancamentos)
        cur.execute(f"DELETE FROM fluxo_caixa WHERE {_where_data_iso('data_iso')}", (ini, fim))
        lancamentos_removidos = cur.rowcount

        detalhe = (
            f"Período {rotulo}; vendas canceladas={vendas_canceladas}; total vendas={total_vendas}; "
            f"lançamentos caixa removidos={lancamentos_removidos}; total fluxo={total_fluxo}; "
            f"motivo={motivo}; backup={backup}; vendas IDs={', '.join(ids_vendas[:60])}"
        )
        cur.execute(
            "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
            (_nome_usuario(usuario), "Manutenção - Zerar Vendas/Caixa por Período", detalhe, datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        )
        conn.commit()
        return {
            "ok": True,
            "periodo": rotulo,
            "backup": backup,
            "vendas_canceladas": vendas_canceladas,
            "total_vendas_canceladas": total_vendas,
            "lancamentos_removidos": lancamentos_removidos,
            "total_fluxo_removido": total_fluxo,
            "mensagem": "Período zerado: vendas canceladas para sair do Dashboard e lançamentos removidos do caixa.",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
