from __future__ import annotations

import os
import re
import secrets
import time
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response

from backend.api_security import ORIGENS_PERMITIDAS
from backend.database import conectar
from backend.rate_limit import _client_ip

COOKIE_NOME = "mistica_painel_sessao"
METODOS_MUTAVEIS = {"POST", "PUT", "PATCH", "DELETE"}
DURACAO_MAXIMA_HORAS = 12
INATIVIDADE_MAXIMA_MINUTOS = 30
LOGIN_JANELA_MINUTOS = int(os.environ.get("MISTICA_LOGIN_WINDOW_MINUTES", "10") or "10")
LOGIN_MAX_TENTATIVAS = int(os.environ.get("MISTICA_LOGIN_MAX_ATTEMPTS", "5") or "5")
LOGIN_ATRASO_MAXIMO = float(os.environ.get("MISTICA_LOGIN_MAX_DELAY_SECONDS", "2") or "2")


def _agora() -> datetime:
    return datetime.now()


def _txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse(valor: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(valor or ""), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _garantir_estrutura_seguranca(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS painel_login_tentativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT,
            ip TEXT,
            user_agent TEXT,
            sucesso INTEGER,
            data_hora TEXT,
            motivo TEXT,
            bloqueado_ate TEXT
        )
        """
    )
    for sql in (
        "ALTER TABLE painel_login_tentativas ADD COLUMN motivo TEXT",
        "ALTER TABLE painel_login_tentativas ADD COLUMN bloqueado_ate TEXT",
    ):
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_login_tentativas_login_data ON painel_login_tentativas(login, data_hora)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_login_tentativas_ip_data ON painel_login_tentativas(ip, data_hora)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS painel_alertas_seguranca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            login TEXT,
            ip TEXT,
            detalhe TEXT,
            criado_em TEXT NOT NULL,
            resolvido INTEGER DEFAULT 0
        )
        """
    )


def _senha_forte(senha: str) -> bool:
    valor = str(senha or "")
    return (
        len(valor) >= 12
        and bool(re.search(r"[a-z]", valor))
        and bool(re.search(r"[A-Z]", valor))
        and bool(re.search(r"\d", valor))
        and bool(re.search(r"[^A-Za-z0-9]", valor))
    )


def _validar_senha_padrao_forte() -> None:
    senha_padrao = os.environ.get("MISTICA_DEFAULT_PANEL_PASSWORD", "").strip()
    if senha_padrao and not _senha_forte(senha_padrao):
        raise HTTPException(
            status_code=503,
            detail="A senha administrativa configurada é fraca. Use ao menos 12 caracteres com maiúscula, minúscula, número e símbolo.",
        )


def _contar_falhas(conn, *, login: str, ip: str, desde: str) -> tuple[int, int]:
    por_login = conn.execute(
        "SELECT COUNT(*) AS total FROM painel_login_tentativas WHERE sucesso=0 AND login=? AND data_hora>=?",
        (login, desde),
    ).fetchone()
    por_ip = conn.execute(
        "SELECT COUNT(*) AS total FROM painel_login_tentativas WHERE sucesso=0 AND ip=? AND data_hora>=?",
        (ip, desde),
    ).fetchone()
    return int(por_login["total"] or 0), int(por_ip["total"] or 0)


def _bloqueio_ativo(conn, *, login: str, ip: str, agora: datetime) -> datetime | None:
    linha = conn.execute(
        """
        SELECT bloqueado_ate
        FROM painel_login_tentativas
        WHERE sucesso=0 AND (login=? OR ip=?) AND bloqueado_ate IS NOT NULL
        ORDER BY bloqueado_ate DESC
        LIMIT 1
        """,
        (login, ip),
    ).fetchone()
    bloqueado_ate = _parse(linha["bloqueado_ate"] if linha else None)
    return bloqueado_ate if bloqueado_ate and bloqueado_ate > agora else None


def _erro_bloqueio(bloqueado_ate: datetime, agora: datetime) -> HTTPException:
    segundos = max(1, int((bloqueado_ate - agora).total_seconds()))
    return HTTPException(
        status_code=429,
        detail="Acesso temporariamente bloqueado por tentativas inválidas. Tente novamente mais tarde.",
        headers={"Retry-After": str(segundos)},
    )


def _duracao_bloqueio(falhas_24h: int) -> timedelta | None:
    if falhas_24h >= 15:
        return timedelta(hours=24)
    if falhas_24h >= 10:
        return timedelta(minutes=30)
    if falhas_24h >= LOGIN_MAX_TENTATIVAS:
        return timedelta(minutes=5)
    return None


def _verificar_login_liberado(login: str, request: Request) -> None:
    agora = _agora()
    ip = _client_ip(request)
    desde = _txt(agora - timedelta(minutes=LOGIN_JANELA_MINUTOS))
    with conectar() as conn:
        _garantir_estrutura_seguranca(conn)
        bloqueado_ate = _bloqueio_ativo(conn, login=login, ip=ip, agora=agora)
        falhas_login, falhas_ip = _contar_falhas(conn, login=login, ip=ip, desde=desde)
    if bloqueado_ate:
        raise _erro_bloqueio(bloqueado_ate, agora)
    if max(falhas_login, falhas_ip) >= LOGIN_MAX_TENTATIVAS:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de login. Tente novamente mais tarde.",
            headers={"Retry-After": "300"},
        )


def registrar_tentativa_login(login: str, request: Request, sucesso: bool) -> None:
    """Audita tentativas e aplica limite por IP/usuário, atraso e bloqueio crescente."""
    agora = _agora()
    ip = _client_ip(request)
    user_agent = str(request.headers.get("user-agent", ""))[:255]
    login = str(login or "").strip().lower()

    if sucesso:
        _verificar_login_liberado(login, request)
        with conectar() as conn:
            _garantir_estrutura_seguranca(conn)
            conn.execute(
                """
                INSERT INTO painel_login_tentativas
                    (login, ip, user_agent, sucesso, data_hora, motivo, bloqueado_ate)
                VALUES (?,?,?,?,?,?,NULL)
                """,
                (login, ip, user_agent, 1, _txt(agora), "sucesso"),
            )
        return

    with conectar() as conn:
        _garantir_estrutura_seguranca(conn)
        bloqueado_ate = _bloqueio_ativo(conn, login=login, ip=ip, agora=agora)
        if bloqueado_ate:
            raise _erro_bloqueio(bloqueado_ate, agora)

        desde_janela = _txt(agora - timedelta(minutes=LOGIN_JANELA_MINUTOS))
        falhas_login, falhas_ip = _contar_falhas(conn, login=login, ip=ip, desde=desde_janela)
        desde_24h = _txt(agora - timedelta(hours=24))
        falhas_login_24h, falhas_ip_24h = _contar_falhas(conn, login=login, ip=ip, desde=desde_24h)
        falhas_janela = max(falhas_login, falhas_ip) + 1
        falhas_24h = max(falhas_login_24h, falhas_ip_24h) + 1
        duracao = _duracao_bloqueio(falhas_24h) if falhas_janela >= LOGIN_MAX_TENTATIVAS else None
        novo_bloqueio = agora + duracao if duracao else None
        conn.execute(
            """
            INSERT INTO painel_login_tentativas
                (login, ip, user_agent, sucesso, data_hora, motivo, bloqueado_ate)
            VALUES (?,?,?,?,?,?,?)
            """,
            (login, ip, user_agent, 0, _txt(agora), "credenciais_invalidas", _txt(novo_bloqueio) if novo_bloqueio else None),
        )
        if novo_bloqueio:
            detalhe = f"{falhas_24h} falhas em 24h; bloqueio até {_txt(novo_bloqueio)}; user-agent={user_agent}"
            conn.execute(
                "INSERT INTO painel_alertas_seguranca (tipo, login, ip, detalhe, criado_em) VALUES (?,?,?,?,?)",
                ("login_suspeito", login, ip, detalhe, _txt(agora)),
            )
            print(f"[ALERTA_SEGURANCA] login={login} ip={ip} {detalhe}")

    if novo_bloqueio:
        raise _erro_bloqueio(novo_bloqueio, agora)

    atraso = min(LOGIN_ATRASO_MAXIMO, 0.25 * (2 ** max(0, falhas_janela - 1)))
    time.sleep(atraso)


def limpar_sessoes_expiradas() -> None:
    try:
        with conectar() as conn:
            conn.execute("DELETE FROM painel_sessoes WHERE expira_em < ?", (_txt(_agora()),))
    except Exception:
        pass


def criar_sessao(usuario: dict, perfil: str, request: Request, response: Response) -> str:
    """Cria uma sessão armazenada no servidor e enviada somente por cookie seguro."""
    login = str(usuario.get("login") or "").strip().lower()
    _validar_senha_padrao_forte()
    _verificar_login_liberado(login, request)
    limpar_sessoes_expiradas()
    token = secrets.token_urlsafe(32)
    agora = _agora()
    expira = agora + timedelta(minutes=INATIVIDADE_MAXIMA_MINUTOS)
    ip = _client_ip(request)
    user_agent = str(request.headers.get("user-agent", ""))[:255]
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO painel_sessoes
                (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token,
                usuario.get("id"),
                usuario.get("login"),
                usuario.get("nome"),
                perfil,
                ip,
                user_agent,
                _txt(agora),
                _txt(expira),
                _txt(agora),
            ),
        )
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=DURACAO_MAXIMA_HORAS * 3600,
        path="/",
    )
    return token


def validar_sessao(token: str | None) -> dict | None:
    """Valida expiração absoluta e por inatividade (sliding window)."""
    if not token:
        return None
    limpar_sessoes_expiradas()
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM painel_sessoes WHERE token=?", (token,)).fetchone()
        if not linha:
            return None
        dados = dict(linha)
        agora = _agora()
        expira = _parse(dados.get("expira_em"))
        criada = _parse(dados.get("criada_em"))
        if not expira or expira < agora:
            conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
            return None
        if criada and (agora - criada) > timedelta(hours=DURACAO_MAXIMA_HORAS):
            conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
            return None
        nova_expiracao = agora + timedelta(minutes=INATIVIDADE_MAXIMA_MINUTOS)
        conn.execute(
            "UPDATE painel_sessoes SET expira_em=?, ultimo_acesso=? WHERE token=?",
            (_txt(nova_expiracao), _txt(agora), token),
        )
        dados["expira_em"] = _txt(nova_expiracao)
        return dados


def encerrar_sessao(token: str | None, response: Response) -> None:
    """Logout: apaga a sessão no servidor e remove o cookie do navegador."""
    if token:
        try:
            with conectar() as conn:
                conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
        except Exception:
            pass
    response.delete_cookie(COOKIE_NOME, path="/")


def sessao_atual(mistica_painel_sessao: str | None = Cookie(default=None)) -> dict:
    dados = validar_sessao(mistica_painel_sessao)
    if not dados:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")
    return dados


def _validar_origem_csrf(request: Request) -> None:
    """Defesa em profundidade contra CSRF nas rotas autenticadas por cookie de
    sessão: o cookie já é SameSite=Lax (o navegador não o envia em POST/PUT/
    PATCH/DELETE de origem cruzada), mas se algum navegador antigo ignorar
    SameSite, uma requisição que muda estado sem Origin/Referer batendo com um
    domínio conhecido nosso é rejeitada. Chamadas autenticadas por
    X-Mistica-Api-Key (integrações servidor-a-servidor, sem cookie) não
    passam por aqui."""
    if request.method not in METODOS_MUTAVEIS:
        return
    origem = request.headers.get("origin") or ""
    if not origem:
        referer = request.headers.get("referer") or ""
        origem = referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2] if referer.count("/") >= 2 else ""
    if origem not in ORIGENS_PERMITIDAS:
        raise HTTPException(status_code=403, detail="Origem da requisição não permitida.")


def exigir_perfil(perfil_minimo: str = "vendedor"):
    """Dependência FastAPI para proteger rotas por sessão e perfil."""

    def dependencia(request: Request, sessao: dict = Depends(sessao_atual)) -> dict:
        if perfil_minimo == "adm" and sessao.get("perfil") != "adm":
            raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
        _validar_origem_csrf(request)
        return sessao

    return dependencia


def exigir_sessao_ou_chave_api(perfil_minimo: str = "vendedor"):
    """Dependência FastAPI que aceita a sessão de painel (uso pelo navegador) OU a chave
    estática MISTICA_SITE_API_KEY/MISTICA_SYNC_KEY (uso por integrações servidor-a-servidor).
    A chave nunca deve ser digitada ou guardada no navegador; ela fica apenas em segredos do
    servidor (Render/GitHub Secrets) e é usada por scripts de sincronização automatizados.
    """

    def dependencia(
        request: Request,
        mistica_painel_sessao: str | None = Cookie(default=None),
        x_mistica_api_key: str | None = Header(default=None),
    ) -> dict:
        sessao = validar_sessao(mistica_painel_sessao)
        if sessao:
            if perfil_minimo == "adm" and sessao.get("perfil") != "adm":
                raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
            _validar_origem_csrf(request)
            return sessao

        chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
        if chave and x_mistica_api_key and secrets.compare_digest(str(x_mistica_api_key), chave):
            return {"perfil": "adm", "login": "integracao-api-key"}

        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")

    return dependencia
