"""Camada 1 — autorização de homologação do Chat Inteligente da Isis 2.0.

Reaproveita, sem duplicar, a mesma allowlist fechada e o mesmo mecanismo de
sessão criados pela homologação controlada da PR #354
(`backend.isis2_homolog`): tabela `isis2_homolog_testers` (aluno_id
autorizado) e as sessões HttpOnly já existentes (`mistica_painel_sessao`
para admin, `mistica_aluno_sessao` para aluno). Isso preserva
compatibilidade -- um mesmo administrador gerencia uma única allowlist de
testadores para toda a homologação da Isis 2.0, chat incluído.

A decisão de autorização é 100% do servidor:

- MISTICA_ISIS_CHAT_ENABLED precisa estar ligada; senão, ninguém tem acesso
  (nem admin) -- o chat simplesmente não existe nesse ambiente;
- MISTICA_ISIS_CHAT_HOMOLOG_ENABLED precisa estar ligada; senão, ninguém
  tem acesso -- ainda estamos em homologação fechada, nunca em produção
  aberta ao público;
- com as duas ligadas, um admin autenticado é sempre autorizado
  automaticamente, e um aluno autenticado só é autorizado se estiver na
  allowlist `isis2_homolog_testers`.

Qualquer sessão ausente, expirada, fora da allowlist, erro de banco ou
estado inesperado resulta em "não autorizado" (fail closed) -- nunca em
"autorizado" por omissão. Não existe nenhum caminho que dependa de query
string, hash, header customizado, localStorage/sessionStorage ou de um
valor lido só no navegador.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Cookie, HTTPException, Request

from backend.database import conectar
from backend.isis2_homolog import garantir_tabelas_isis2_homolog
from backend.isis_chat_flags import chat_habilitado, chat_homolog_habilitado
from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class IdentidadeChat:
    tipo: str  # "adm" | "aluno"
    referencia: str  # login do admin ou "aluno:<id>" -- nunca e-mail/nome completo


def _sessao_admin(mistica_painel_sessao: str | None) -> dict | None:
    from backend.panel_sessions import validar_sessao

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


def _aluno_autorizado(conn, aluno_id: int) -> bool:
    try:
        linha = conn.execute(
            "SELECT 1 FROM isis2_homolog_testers WHERE aluno_id=?", (aluno_id,)
        ).fetchone()
    except Exception:
        return False
    return linha is not None


def identidade_chat_autorizada(
    mistica_painel_sessao: str | None = Cookie(default=None),
    mistica_aluno_sessao: str | None = Cookie(default=None),
) -> IdentidadeChat:
    """Dependência FastAPI: 401 se o chat estiver desativado (flags) ou se
    não houver nenhuma conta autorizada por trás dos cookies de sessão."""
    if not chat_habilitado() or not chat_homolog_habilitado():
        raise HTTPException(status_code=404, detail="Não encontrado.")

    try:
        admin = _sessao_admin(mistica_painel_sessao)
        if admin:
            return IdentidadeChat(tipo="adm", referencia=str(admin.get("login") or "adm"))

        aluno = _sessao_aluno(mistica_aluno_sessao)
        if aluno:
            aluno_id = int(aluno["aluno_id"])
            with conectar() as conn:
                garantir_tabelas_isis2_homolog(conn)
                if _aluno_autorizado(conn, aluno_id):
                    return IdentidadeChat(tipo="aluno", referencia=f"aluno:{aluno_id}")
    except HTTPException:
        raise
    except Exception:
        logger.warning("isis chat: falha ao avaliar autorização", extra={"evento": "isis_chat_auth_erro"})

    raise HTTPException(status_code=401, detail="Você não está autorizado a usar a Isis em homologação.")


def identidade_chat_opcional(
    mistica_painel_sessao: str | None = Cookie(default=None),
    mistica_aluno_sessao: str | None = Cookie(default=None),
) -> IdentidadeChat | None:
    """Igual a `identidade_chat_autorizada`, mas devolve `None` em vez de
    levantar 401 -- usado por rotas que precisam responder 200 com estado
    "desativado" (ex.: `GET /api/isis2/chat/status`) em vez de erro."""
    try:
        return identidade_chat_autorizada(mistica_painel_sessao, mistica_aluno_sessao)
    except HTTPException:
        return None


def validar_origem_csrf(request: Request) -> None:
    """Mesma defesa em profundidade contra CSRF usada pelo restante do
    painel (`backend.panel_sessions._validar_origem_csrf`), reaplicada aqui
    porque as rotas de chat aceitam tanto sessão de admin quanto de aluno
    (a dependência genérica só cobre perfil admin)."""
    from backend.api_security import ORIGENS_PERMITIDAS

    metodos_mutaveis = {"POST", "PUT", "PATCH", "DELETE"}
    if request.method not in metodos_mutaveis:
        return
    origem = request.headers.get("origin") or ""
    if not origem:
        referer = request.headers.get("referer") or ""
        origem = referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2] if referer.count("/") >= 2 else ""
    if origem not in ORIGENS_PERMITIDAS:
        raise HTTPException(status_code=403, detail="Origem da requisição não permitida.")
