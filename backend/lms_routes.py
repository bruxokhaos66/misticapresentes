"""Endpoints da área do aluno para a Escola Mística hierárquica.

Reaproveita a sessão de aluno já existente (``sessao_aluno_atual`` em
``backend/aluno_auth.py``) e a matrícula ``alunos_cursos``. Todas as permissões
(acesso ao curso, módulo liberado, avaliação disponível, cálculo de nota) são
validadas no backend — o frontend nunca decide bloqueio nem nota, e o gabarito
das avaliações jamais é enviado ao aluno antes da correção.
"""

from __future__ import annotations

import random
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.aluno_auth import sessao_aluno_atual
from backend.database import conectar, obter
from backend.lms import (
    NOTA_MINIMA_PADRAO,
    PERCENTUAL_VIDEO_PADRAO,
    STATUS_AULA_VALIDOS,
    STATUS_CONCLUIDA,
    STATUS_EM_ANDAMENTO,
    _aulas_obrigatorias_concluidas,
    _melhor_tentativa,
    _quiz_do_modulo,
    estado_progressao,
    garantir_acesso,
    garantir_tabelas_lms,
    obter_config_curso,
)
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api/escola", tags=["escola-aluno"])

limitar_tentativa_quiz = limitar_requisicoes("quiz_tentativa", limite=20, janela_segundos=60)


def _agora() -> datetime:
    return datetime.now()


def _txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _nota_minima_modulo(conn, modulo: dict, slug: str) -> int:
    if modulo.get("nota_minima") is not None:
        return int(modulo["nota_minima"])
    cfg = obter_config_curso(conn, slug)
    return int(cfg.get("nota_minima") or NOTA_MINIMA_PADRAO)


def _serializar_aula(row: dict, progresso: dict | None, incluir_conteudo: bool) -> dict:
    base = {
        "id": row["id"],
        "titulo": row["titulo"],
        "descricao": row["descricao"],
        "tipo": row["tipo"],
        "capa_url": row["capa_url"],
        "ordem": row["ordem"],
        "duracao_min": row["duracao_min"],
        "obrigatoria": bool(row["obrigatoria"]),
        "status": (progresso or {}).get("status", "nao_iniciada"),
        "percentual": int((progresso or {}).get("percentual", 0) or 0),
    }
    # Conteúdo real (texto, vídeo, material) só é enviado quando o módulo está
    # liberado — assim mudar a URL/estado no navegador não vaza aula bloqueada.
    if incluir_conteudo:
        base.update(
            {
                "conteudo": row["conteudo"],
                "video_url": row["video_url"],
                "material_url": row["material_url"],
                "percentual_minimo": row["percentual_minimo"] or PERCENTUAL_VIDEO_PADRAO,
            }
        )
    return base


@router.get("/cursos/{slug}")
def arvore_curso(slug: str, sessao: dict = Depends(sessao_aluno_atual)):
    """Árvore completa do curso para o aluno logado, já com o estado de
    progressão (módulos liberados/bloqueados/concluídos, status de cada aula,
    avaliação disponível ou não, maior/última nota)."""
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        garantir_acesso(conn, aluno_id=aluno_id, slug=slug)
        cfg = obter_config_curso(conn, slug)

        prog_aulas = {
            int(r["aula_id"]): dict(r)
            for r in conn.execute(
                "SELECT aula_id, status, percentual FROM aluno_aula_progresso WHERE aluno_id=? AND slug=?",
                (aluno_id, slug),
            ).fetchall()
        }

        estado = estado_progressao(conn, aluno_id=aluno_id, slug=slug)
        modulos_out = []
        for item in estado["modulos"]:
            mod = item["modulo"]
            liberado = item["liberado"]
            aulas_rows = conn.execute(
                "SELECT * FROM curso_aulas WHERE modulo_id=? AND publicado=1 ORDER BY ordem, id",
                (mod["id"],),
            ).fetchall()
            aulas = [
                _serializar_aula(dict(a), prog_aulas.get(int(a["id"])), incluir_conteudo=liberado)
                for a in aulas_rows
            ]
            quiz = _quiz_do_modulo(conn, mod["id"])
            quiz_out = None
            if quiz:
                obrig_ok = _aulas_obrigatorias_concluidas(conn, aluno_id=aluno_id, modulo_id=mod["id"])
                melhor = _melhor_tentativa(conn, aluno_id=aluno_id, quiz_id=quiz["id"])
                num_tentativas = conn.execute(
                    "SELECT COUNT(*) AS n FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=?",
                    (aluno_id, quiz["id"]),
                ).fetchone()["n"]
                ultima = conn.execute(
                    "SELECT nota, aprovado, finalizada_em FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=? ORDER BY id DESC LIMIT 1",
                    (aluno_id, quiz["id"]),
                ).fetchone()
                quiz_out = {
                    "id": quiz["id"],
                    "titulo": quiz["titulo"] or "Avaliação do módulo",
                    "nota_minima": int(quiz["nota_minima"] or _nota_minima_modulo(conn, mod, slug)),
                    "max_tentativas": quiz["max_tentativas"],
                    "tentativas_feitas": int(num_tentativas),
                    "disponivel": bool(liberado and obrig_ok),
                    "maior_nota": int(melhor["nota"]) if melhor else None,
                    "ultima_nota": int(ultima["nota"]) if ultima else None,
                    "aprovado": bool(melhor and melhor["aprovado"]),
                }
            modulos_out.append(
                {
                    "id": mod["id"],
                    "titulo": mod["titulo"],
                    "descricao": mod["descricao"],
                    "ordem": mod["ordem"],
                    "liberado": liberado,
                    "concluido": item["concluido"],
                    "aulas": aulas,
                    "quiz": quiz_out,
                }
            )

        total_aulas = sum(len(m["aulas"]) for m in modulos_out)
        aulas_concluidas = sum(
            1 for m in modulos_out for a in m["aulas"] if a["status"] == STATUS_CONCLUIDA
        )
        percentual = round((aulas_concluidas / total_aulas) * 100) if total_aulas else 0
        curso_concluido = bool(modulos_out) and all(m["concluido"] for m in modulos_out)

        return {
            "slug": slug,
            "titulo": cfg.get("titulo") or slug.replace("-", " ").title(),
            "descricao": cfg.get("descricao"),
            "imagem": cfg.get("imagem"),
            "certificado": bool(cfg.get("certificado", 1)),
            "nota_minima": int(cfg.get("nota_minima") or NOTA_MINIMA_PADRAO),
            "progresso": {
                "total_aulas": total_aulas,
                "aulas_concluidas": aulas_concluidas,
                "percentual": percentual,
                "concluido": curso_concluido,
            },
            "modulos": modulos_out,
        }


class AulaProgressoIn(BaseModel):
    status: str = Field(default=STATUS_EM_ANDAMENTO)
    percentual: int = Field(default=0, ge=0, le=100)


@router.post("/aulas/{aula_id}/progresso")
def marcar_aula(aula_id: int, payload: AulaProgressoIn, sessao: dict = Depends(sessao_aluno_atual)):
    """Registra o progresso de uma aula (não iniciada / em andamento / concluída,
    percentual assistido). Salvo no backend e vinculado ao aluno — nunca só no
    navegador. Para vídeo, o cliente pode enviar o percentual; a conclusão exige
    atingir o percentual mínimo configurado."""
    if payload.status not in STATUS_AULA_VALIDOS:
        raise HTTPException(status_code=422, detail="Status de aula inválido.")
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        aula = conn.execute(
            """
            SELECT a.*, m.slug AS slug FROM curso_aulas a
            JOIN curso_modulos m ON m.id = a.modulo_id
            WHERE a.id=? AND a.publicado=1
            """,
            (aula_id,),
        ).fetchone()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula não encontrada.")
        slug = aula["slug"]
        garantir_acesso(conn, aluno_id=aluno_id, slug=slug)

        # Não deixa concluir aula de módulo bloqueado (defesa contra manipulação
        # de requisição): o módulo precisa estar liberado para o aluno.
        from backend.lms import modulo_liberado

        if not modulo_liberado(conn, aluno_id=aluno_id, modulo_id=int(aula["modulo_id"])):
            raise HTTPException(status_code=403, detail="Este módulo ainda está bloqueado.")

        status = payload.status
        percentual = int(payload.percentual)
        # Regra de vídeo: só conclui ao atingir o percentual mínimo assistido.
        if status == STATUS_CONCLUIDA and aula["tipo"] == "video":
            minimo = int(aula["percentual_minimo"] or PERCENTUAL_VIDEO_PADRAO)
            if percentual < minimo:
                status = STATUS_EM_ANDAMENTO
        if status == STATUS_CONCLUIDA:
            percentual = 100

        agora = _txt(_agora())
        existente = conn.execute(
            "SELECT id, status, iniciada_em FROM aluno_aula_progresso WHERE aluno_id=? AND aula_id=?",
            (aluno_id, aula_id),
        ).fetchone()
        if existente:
            iniciada = existente["iniciada_em"] or agora
            concluida = agora if status == STATUS_CONCLUIDA else None
            conn.execute(
                """
                UPDATE aluno_aula_progresso
                SET status=?, percentual=MAX(percentual, ?), iniciada_em=?, concluida_em=?, atualizado_em=?
                WHERE id=?
                """,
                (status, percentual, iniciada, concluida, agora, existente["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO aluno_aula_progresso
                (aluno_id, aula_id, slug, status, percentual, iniciada_em, concluida_em, atualizado_em)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    aluno_id,
                    aula_id,
                    slug,
                    status,
                    percentual,
                    agora,
                    agora if status == STATUS_CONCLUIDA else None,
                    agora,
                ),
            )
        return {"ok": True, "aula_id": aula_id, "status": status, "percentual": percentual}


@router.get("/quizzes/{quiz_id}/iniciar")
def iniciar_quiz(quiz_id: int, sessao: dict = Depends(sessao_aluno_atual)):
    """Prepara uma tentativa: seleciona (aleatoriamente, se configurado) e
    embaralha as perguntas e opções, SEM revelar quais são corretas. Guarda no
    servidor o conjunto de perguntas servidas para que a nota seja calculada
    depois exatamente sobre elas (impede escolher só perguntas fáceis)."""
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        quiz = conn.execute(
            "SELECT * FROM curso_quizzes WHERE id=? AND publicado=1", (quiz_id,)
        ).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
        modulo = conn.execute("SELECT * FROM curso_modulos WHERE id=?", (quiz["modulo_id"],)).fetchone()
        slug = modulo["slug"]
        garantir_acesso(conn, aluno_id=aluno_id, slug=slug)

        from backend.lms import modulo_liberado

        if not modulo_liberado(conn, aluno_id=aluno_id, modulo_id=int(quiz["modulo_id"])):
            raise HTTPException(status_code=403, detail="Este módulo ainda está bloqueado.")
        if not _aulas_obrigatorias_concluidas(conn, aluno_id=aluno_id, modulo_id=int(quiz["modulo_id"])):
            raise HTTPException(
                status_code=403,
                detail="Conclua todos os conteúdos obrigatórios antes de fazer a avaliação.",
            )

        # Tentativas e intervalo entre tentativas.
        tentativas = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=?",
            (aluno_id, quiz_id),
        ).fetchone()["n"]
        if quiz["max_tentativas"] and int(tentativas) >= int(quiz["max_tentativas"]):
            raise HTTPException(status_code=429, detail="Você atingiu o limite de tentativas desta avaliação.")
        if quiz["intervalo_min"]:
            ultima = conn.execute(
                "SELECT finalizada_em FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=? ORDER BY id DESC LIMIT 1",
                (aluno_id, quiz_id),
            ).fetchone()
            if ultima and ultima["finalizada_em"]:
                try:
                    fim = datetime.strptime(ultima["finalizada_em"], "%Y-%m-%d %H:%M:%S")
                    if _agora() < fim + timedelta(minutes=int(quiz["intervalo_min"])):
                        raise HTTPException(
                            status_code=429,
                            detail="Aguarde o intervalo entre tentativas antes de tentar de novo.",
                        )
                except ValueError:
                    pass

        perguntas = [
            dict(p)
            for p in conn.execute(
                "SELECT * FROM quiz_perguntas WHERE quiz_id=? AND ativa=1 ORDER BY ordem, id",
                (quiz_id,),
            ).fetchall()
        ]
        if not perguntas:
            raise HTTPException(status_code=409, detail="Esta avaliação ainda não tem perguntas cadastradas.")

        if quiz["num_perguntas"] and int(quiz["num_perguntas"]) < len(perguntas):
            perguntas = random.sample(perguntas, int(quiz["num_perguntas"]))
        if quiz["embaralhar_perguntas"]:
            random.shuffle(perguntas)

        perguntas_out = []
        for p in perguntas:
            opcoes = [
                {"id": o["id"], "texto": o["texto"]}
                for o in conn.execute(
                    "SELECT id, texto FROM quiz_opcoes WHERE pergunta_id=? ORDER BY ordem, id",
                    (p["id"],),
                ).fetchall()
            ]
            if quiz["embaralhar_opcoes"]:
                random.shuffle(opcoes)
            perguntas_out.append({"id": p["id"], "enunciado": p["enunciado"], "tipo": p["tipo"], "opcoes": opcoes})

        sessao_id = secrets.token_urlsafe(18)
        conn.execute(
            "INSERT INTO quiz_sessoes (id, quiz_id, aluno_id, slug, perguntas, iniciada_em) VALUES (?,?,?,?,?,?)",
            (sessao_id, quiz_id, aluno_id, slug, ",".join(str(p["id"]) for p in perguntas), _txt(_agora())),
        )
        return {
            "sessao_id": sessao_id,
            "quiz_id": quiz_id,
            "titulo": quiz["titulo"] or "Avaliação do módulo",
            "nota_minima": int(quiz["nota_minima"] or _nota_minima_modulo(conn, dict(modulo), slug)),
            "perguntas": perguntas_out,
        }


class RespostaIn(BaseModel):
    pergunta_id: int
    opcao_id: Optional[int] = None


class EnvioQuizIn(BaseModel):
    sessao_id: str = Field(min_length=1)
    respostas: list[RespostaIn] = Field(default_factory=list)


@router.post("/quizzes/{quiz_id}/enviar", dependencies=[Depends(limitar_tentativa_quiz)])
def enviar_quiz(quiz_id: int, payload: EnvioQuizIn, sessao: dict = Depends(sessao_aluno_atual)):
    """Corrige a avaliação NO BACKEND a partir do gabarito, registra a tentativa
    e as respostas, e libera o próximo módulo apenas se o aluno for aprovado.
    A sessão de tentativa é de uso único (idempotência contra reenvio)."""
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        ses = conn.execute(
            "SELECT * FROM quiz_sessoes WHERE id=? AND quiz_id=? AND aluno_id=?",
            (payload.sessao_id, quiz_id, aluno_id),
        ).fetchone()
        if not ses:
            raise HTTPException(status_code=404, detail="Sessão de avaliação inválida. Inicie a avaliação novamente.")
        if ses["consumida_em"]:
            raise HTTPException(status_code=409, detail="Esta tentativa já foi enviada.")

        quiz = conn.execute("SELECT * FROM curso_quizzes WHERE id=?", (quiz_id,)).fetchone()
        modulo = conn.execute("SELECT * FROM curso_modulos WHERE id=?", (quiz["modulo_id"],)).fetchone()
        slug = modulo["slug"]

        perguntas_ids = [int(x) for x in str(ses["perguntas"]).split(",") if x]
        respostas_por_pergunta = {int(r.pergunta_id): r.opcao_id for r in payload.respostas}

        acertos = 0
        detalhes = []
        for pid in perguntas_ids:
            opcao_id = respostas_por_pergunta.get(pid)
            correta = False
            if opcao_id is not None:
                op = conn.execute(
                    "SELECT correta FROM quiz_opcoes WHERE id=? AND pergunta_id=?", (opcao_id, pid)
                ).fetchone()
                correta = bool(op and op["correta"])
            if correta:
                acertos += 1
            detalhes.append((pid, opcao_id, 1 if correta else 0))

        total = len(perguntas_ids)
        nota = round((acertos / total) * 100) if total else 0
        nota_minima = int(quiz["nota_minima"] or _nota_minima_modulo(conn, dict(modulo), slug))
        aprovado = nota >= nota_minima
        agora = _txt(_agora())

        cur = conn.execute(
            """
            INSERT INTO quiz_tentativas
            (quiz_id, aluno_id, slug, nota, aprovado, total_perguntas, acertos, iniciada_em, finalizada_em)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (quiz_id, aluno_id, slug, nota, 1 if aprovado else 0, total, acertos, ses["iniciada_em"], agora),
        )
        tentativa_id = int(cur.lastrowid)
        for pid, opcao_id, ok in detalhes:
            conn.execute(
                "INSERT INTO quiz_respostas (tentativa_id, pergunta_id, opcao_id, correta) VALUES (?,?,?,?)",
                (tentativa_id, pid, opcao_id, ok),
            )
        conn.execute("UPDATE quiz_sessoes SET consumida_em=? WHERE id=?", (agora, payload.sessao_id))

        # Explicações só são reveladas DEPOIS de enviar (nunca antes da correção).
        explicacoes = {}
        for pid, opcao_id, ok in detalhes:
            p = conn.execute("SELECT explicacao FROM quiz_perguntas WHERE id=?", (pid,)).fetchone()
            correta_op = conn.execute(
                "SELECT id FROM quiz_opcoes WHERE pergunta_id=? AND correta=1 LIMIT 1", (pid,)
            ).fetchone()
            explicacoes[pid] = {
                "correta_opcao_id": correta_op["id"] if correta_op else None,
                "sua_opcao_id": opcao_id,
                "acertou": bool(ok),
                "explicacao": p["explicacao"] if p else None,
            }

        return {
            "ok": True,
            "nota": nota,
            "acertos": acertos,
            "total": total,
            "nota_minima": nota_minima,
            "aprovado": aprovado,
            "explicacoes": explicacoes,
        }


@router.get("/quizzes/{quiz_id}/tentativas")
def historico_tentativas(quiz_id: int, sessao: dict = Depends(sessao_aluno_atual)):
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        rows = conn.execute(
            """
            SELECT id, nota, aprovado, acertos, total_perguntas, finalizada_em
            FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=? ORDER BY id DESC LIMIT 50
            """,
            (aluno_id, quiz_id),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/meus-cursos")
def meus_cursos(sessao: dict = Depends(sessao_aluno_atual)):
    """Lista os cursos com estrutura LMS aos quais o aluno tem acesso, com o
    resumo de progresso para a vitrine 'Meus cursos' da área do aluno."""
    aluno_id = int(sessao["aluno_id"])
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        matriculas = conn.execute(
            "SELECT slug FROM alunos_cursos WHERE aluno_id=? AND COALESCE(suspenso,0)=0",
            (aluno_id,),
        ).fetchall()
        slugs = {m["slug"] for m in matriculas}
        # Cursos gratuitos com estrutura publicada também aparecem.
        for r in conn.execute("SELECT DISTINCT slug FROM curso_modulos WHERE publicado=1").fetchall():
            if not _e_pago(r["slug"]):
                slugs.add(r["slug"])

        saida = []
        for slug in sorted(slugs):
            tem_estrutura = conn.execute(
                "SELECT 1 FROM curso_modulos WHERE slug=? AND publicado=1 LIMIT 1", (slug,)
            ).fetchone()
            if not tem_estrutura:
                continue
            cfg = obter_config_curso(conn, slug)
            total = conn.execute(
                """
                SELECT COUNT(*) AS n FROM curso_aulas a
                JOIN curso_modulos m ON m.id=a.modulo_id
                WHERE m.slug=? AND a.publicado=1 AND m.publicado=1
                """,
                (slug,),
            ).fetchone()["n"]
            feitas = conn.execute(
                "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aluno_id=? AND slug=? AND status='concluida'",
                (aluno_id, slug),
            ).fetchone()["n"]
            pct = round((int(feitas) / int(total)) * 100) if total else 0
            saida.append(
                {
                    "slug": slug,
                    "titulo": cfg.get("titulo") or slug.replace("-", " ").title(),
                    "descricao": cfg.get("descricao"),
                    "imagem": cfg.get("imagem"),
                    "percentual": pct,
                    "total_aulas": int(total),
                    "aulas_concluidas": int(feitas),
                }
            )
    return saida


def _e_pago(slug: str) -> bool:
    from backend.course_routes import CATALOGO_CURSOS_PAGOS

    return slug in CATALOGO_CURSOS_PAGOS
