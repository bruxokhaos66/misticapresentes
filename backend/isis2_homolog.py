from __future__ import annotations

"""Isis 2.0 — autorização de homologação controlada.

Único mecanismo que pode ligar isis2.enabled/escola/refinamento no MESMO
domínio de produção, para um conjunto fechado de contas autorizadas, sem
tocar nas flags estáticas de site-config.js (que continuam false em
produção). A autorização é decidida inteiramente aqui, no servidor:

- Precisa de uma sessão válida já existente (cookie HttpOnly
  mistica_painel_sessao, perfil "adm" -- backend.panel_sessions -- OU
  cookie HttpOnly mistica_aluno_sessao -- backend.aluno_auth) E
- essa conta precisa estar na allowlist fechada (tabela
  isis2_homolog_testers, só editável por um admin autenticado) E
- o interruptor global (tabela isis2_homolog_config, chave "ativo")
  precisa estar ligado (também só editável por um admin autenticado).

Não existe nenhum caminho que dependa de query string, hash, header
customizado, localStorage/sessionStorage ou de um valor lido só no
navegador -- ver isis2/isis2-homolog-gate.js. Qualquer sessão ausente,
expirada, não autorizada, erro de banco ou estado inesperado resulta em
"desativado" (fail closed); nunca em "ativado" por omissão.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request

from backend.database import conectar
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_perfil, validar_sessao
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api/isis2", tags=["isis2-homologacao"])
logger = get_logger(__name__)

_CONFIG_CHAVE_ATIVO = "ativo"

limitar_consulta_config = limitar_requisicoes("isis2_homolog_config", limite=30, janela_segundos=60)

_CONFIG_DESATIVADA = {
    "enabled": False,
    "escola": False,
    "refinamento": False,
    "homologacao": False,
}


def garantir_tabelas_isis2_homolog(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis2_homolog_testers (
            aluno_id INTEGER PRIMARY KEY,
            adicionado_por TEXT,
            adicionado_em TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis2_homolog_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )


def _agora_txt() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def homolog_ativo(conn) -> bool:
    """Interruptor global -- default DESLIGADO. Só fica ligado depois que um
    admin chama POST /api/isis2/homolog/ativar explicitamente; qualquer linha
    ausente, corrompida ou com valor inesperado é tratada como desligado."""
    try:
        linha = conn.execute(
            "SELECT valor FROM isis2_homolog_config WHERE chave=?", (_CONFIG_CHAVE_ATIVO,)
        ).fetchone()
    except Exception:
        return False
    if not linha:
        return False
    return str(linha["valor"]).strip() == "1"


def _definir_ativo(conn, ativo: bool) -> None:
    conn.execute(
        """
        INSERT INTO isis2_homolog_config (chave, valor) VALUES (?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor
        """,
        (_CONFIG_CHAVE_ATIVO, "1" if ativo else "0"),
    )


def _aluno_autorizado(conn, aluno_id: int) -> bool:
    try:
        linha = conn.execute(
            "SELECT 1 FROM isis2_homolog_testers WHERE aluno_id=?", (aluno_id,)
        ).fetchone()
    except Exception:
        return False
    return linha is not None


def _sessao_admin(mistica_painel_sessao: str | None) -> dict | None:
    try:
        sessao = validar_sessao(mistica_painel_sessao)
    except Exception:
        return None
    if sessao and sessao.get("perfil") == "adm":
        return sessao
    return None


def _sessao_aluno(mistica_aluno_sessao: str | None) -> dict | None:
    try:
        from backend.aluno_auth import _validar_sessao_aluno

        return _validar_sessao_aluno(mistica_aluno_sessao)
    except Exception:
        return None


def _log_decisao(*, autorizado: bool, perfil: str) -> None:
    # Nunca registra token, cookie, e-mail, nome completo ou id -- só o
    # resultado booleano e o tipo de conta que tentou (allowlist do
    # Analytics existente segue o mesmo princípio, ver isis2/analytics.js).
    logger.info(
        "isis2 homologação: consulta de configuração",
        extra={"evento": "isis2_homolog_config_consultada", "autorizado": autorizado, "perfil": perfil},
    )


@router.get("/homolog-config", dependencies=[Depends(limitar_consulta_config)])
def obter_homolog_config(
    mistica_painel_sessao: str | None = Cookie(default=None),
    mistica_aluno_sessao: str | None = Cookie(default=None),
):
    """Fail-safe: qualquer exceção, sessão ausente/expirada, conta fora da
    allowlist ou interruptor global desligado devolve a configuração
    desativada com HTTP 200 (nunca 500 -- o front-end não deve tratar isso
    como erro de rede, e sim como "Isis desligada", que é o estado normal
    para a esmagadora maioria dos visitantes)."""
    try:
        with conectar() as conn:
            garantir_tabelas_isis2_homolog(conn)
            if not homolog_ativo(conn):
                _log_decisao(autorizado=False, perfil="desconhecido")
                return dict(_CONFIG_DESATIVADA)

            admin = _sessao_admin(mistica_painel_sessao)
            if admin:
                _log_decisao(autorizado=True, perfil="adm")
                return {"enabled": True, "escola": True, "refinamento": True, "homologacao": True}

            aluno = _sessao_aluno(mistica_aluno_sessao)
            if aluno and _aluno_autorizado(conn, int(aluno["aluno_id"])):
                _log_decisao(autorizado=True, perfil="aluno")
                return {"enabled": True, "escola": True, "refinamento": True, "homologacao": True}

            _log_decisao(autorizado=False, perfil="aluno" if aluno else "anonimo")
            return dict(_CONFIG_DESATIVADA)
    except Exception:
        logger.warning("isis2 homologação: falha ao avaliar configuração", extra={"evento": "isis2_homolog_config_erro"})
        return dict(_CONFIG_DESATIVADA)


@router.get("/homolog/estado")
def estado_homolog(sessao: dict = Depends(exigir_perfil("adm"))):
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        ativo = homolog_ativo(conn)
        testadores = conn.execute(
            "SELECT COUNT(*) AS total FROM isis2_homolog_testers"
        ).fetchone()
    return {"ativo": ativo, "total_testadores": int(testadores["total"] or 0)}


@router.post("/homolog/ativar")
def ativar_homolog(sessao: dict = Depends(exigir_perfil("adm"))):
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        _definir_ativo(conn, True)
    logger.info("isis2 homologação: interruptor global ligado", extra={"evento": "isis2_homolog_ativado_por_admin"})
    return {"ok": True, "ativo": True}


@router.post("/homolog/desativar")
def desativar_homolog(sessao: dict = Depends(exigir_perfil("adm"))):
    """Botão de desligamento imediato (item 9 do checklist): efetiva no
    próximo GET /homolog-config de qualquer testador, sem deploy."""
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        _definir_ativo(conn, False)
    logger.info("isis2 homologação: interruptor global desligado", extra={"evento": "isis2_homolog_desativado_por_admin"})
    return {"ok": True, "ativo": False}


@router.get("/homolog-testers")
def listar_testadores(sessao: dict = Depends(exigir_perfil("adm"))):
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        linhas = conn.execute(
            """
            SELECT t.aluno_id, t.adicionado_por, t.adicionado_em, a.nome, a.email
            FROM isis2_homolog_testers t
            JOIN alunos a ON a.id = t.aluno_id
            ORDER BY t.adicionado_em DESC
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


# Registrada ANTES de "/homolog-testers/{aluno_id}": rotas estáticas do
# FastAPI/Starlette são casadas na ordem de declaração, e um {aluno_id: int}
# declarado primeiro capturaria "revogar-todos" e falharia a conversão para
# int (422) antes de esta rota ser sequer considerada.
@router.post("/homolog-testers/revogar-todos")
def revogar_todos_testadores(sessao: dict = Depends(exigir_perfil("adm"))):
    """Revoga a autorização de TODOS os testadores de uma vez (allowlist
    fechada volta a ficar vazia). Efetiva no próximo GET /homolog-config de
    cada um -- não força logout do site (a sessão de aluno continua servindo
    o acesso normal aos cursos comprados)."""
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        conn.execute("DELETE FROM isis2_homolog_testers")
    logger.info("isis2 homologação: todos os testadores revogados", extra={"evento": "isis2_homolog_todos_revogados"})
    return {"ok": True}


@router.post("/homolog-testers/{aluno_id}")
def adicionar_testador(aluno_id: int, request: Request, sessao: dict = Depends(exigir_perfil("adm"))):
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        aluno = conn.execute("SELECT id FROM alunos WHERE id=?", (aluno_id,)).fetchone()
        if not aluno:
            raise HTTPException(status_code=404, detail="Aluno não encontrado.")
        conn.execute(
            """
            INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em)
            VALUES (?,?,?)
            ON CONFLICT(aluno_id) DO NOTHING
            """,
            (aluno_id, sessao.get("login"), _agora_txt()),
        )
    logger.info("isis2 homologação: testador adicionado", extra={"evento": "isis2_homolog_testador_adicionado"})
    return {"ok": True}


@router.delete("/homolog-testers/{aluno_id}")
def remover_testador(aluno_id: int, sessao: dict = Depends(exigir_perfil("adm"))):
    with conectar() as conn:
        garantir_tabelas_isis2_homolog(conn)
        conn.execute("DELETE FROM isis2_homolog_testers WHERE aluno_id=?", (aluno_id,))
    logger.info("isis2 homologação: testador removido", extra={"evento": "isis2_homolog_testador_removido"})
    return {"ok": True}
