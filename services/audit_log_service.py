from datetime import datetime

from database import query_db


def _perfil_usuario(usuario):
    if isinstance(usuario, dict):
        return str(usuario.get("perfil") or "").lower()
    return ""


def exigir_adm(usuario):
    if _perfil_usuario(usuario) != "adm":
        raise PermissionError("Apenas perfil adm pode consultar auditoria completa.")


def listar_usuarios_logs(usuario):
    exigir_adm(usuario)
    rows = query_db("SELECT DISTINCT usuario FROM logs WHERE COALESCE(usuario,'') != '' ORDER BY usuario")
    return [r[0] for r in rows]


def listar_acoes_logs(usuario):
    exigir_adm(usuario)
    rows = query_db("SELECT DISTINCT acao FROM logs WHERE COALESCE(acao,'') != '' ORDER BY acao")
    return [r[0] for r in rows]


def listar_logs_auditoria(usuario, termo="", usuario_filtro="Todos", acao_filtro="Todas", mes=None, ano=None, limite=500):
    exigir_adm(usuario)
    sql = "SELECT usuario, acao, detalhes, data_hora FROM logs WHERE 1=1"
    params = []

    usuario_filtro = str(usuario_filtro or "Todos").strip()
    acao_filtro = str(acao_filtro or "Todas").strip()
    termo = str(termo or "").strip()

    if usuario_filtro and usuario_filtro != "Todos":
        sql += " AND usuario=?"
        params.append(usuario_filtro)
    if acao_filtro and acao_filtro != "Todas":
        sql += " AND acao=?"
        params.append(acao_filtro)
    if termo:
        like = f"%{termo}%"
        sql += " AND (COALESCE(usuario,'') LIKE ? OR COALESCE(acao,'') LIKE ? OR COALESCE(detalhes,'') LIKE ? OR COALESCE(data_hora,'') LIKE ?)"
        params.extend([like, like, like, like])
    if mes and ano:
        try:
            mes_txt = f"{int(mes):02d}"
            ano_txt = str(int(ano))
            sql += " AND COALESCE(data_hora,'') LIKE ?"
            params.append(f"%/{mes_txt}/{ano_txt}%")
        except Exception:
            pass

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limite or 500))
    return query_db(sql, tuple(params))


def resumo_logs_auditoria(usuario, mes=None, ano=None):
    exigir_adm(usuario)
    params = []
    where = "WHERE 1=1"
    if mes and ano:
        try:
            where += " AND COALESCE(data_hora,'') LIKE ?"
            params.append(f"%/{int(mes):02d}/{int(ano)}%")
        except Exception:
            pass
    total = query_db(f"SELECT COUNT(*) FROM logs {where}", tuple(params))[0][0] or 0
    usuarios = query_db(f"SELECT COUNT(DISTINCT usuario) FROM logs {where}", tuple(params))[0][0] or 0
    hoje = datetime.now().strftime("%d/%m/%Y")
    hoje_total = query_db("SELECT COUNT(*) FROM logs WHERE COALESCE(data_hora,'') LIKE ?", (f"{hoje}%",))[0][0] or 0
    return {"total": int(total), "usuarios": int(usuarios), "hoje": int(hoje_total)}


def registrar_log_auditoria(usuario_nome, acao, detalhes):
    query_db(
        "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
        (str(usuario_nome or "Sistema"), str(acao or "Auditoria"), str(detalhes or ""), datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        commit=True,
    )
