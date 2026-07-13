"""Núcleo da Escola Mística evoluída (LMS hierárquico).

Este módulo NÃO recria autenticação, matrícula, pagamento nem contas de aluno:
ele se apoia no que já existe (``backend/aluno_auth.py`` para as contas/sessões
de aluno e a tabela ``alunos_cursos`` de matrícula; ``backend/course_routes.py``
para o catálogo pago e o fluxo de pedidos/Pix). A camada nova apenas acrescenta
a hierarquia Curso → Módulos → Aulas → Avaliação, indexada pelo MESMO ``slug``
de curso já usado nas vendas, de modo que a integração com pagamento continua
valendo sem duplicar sistemas.

Regras de segurança que vivem aqui (sempre validadas no backend):
* acesso ao curso exige matrícula ativa (ou curso gratuito), nunca só o frontend;
* módulos abrem em cascata: o próximo só libera após concluir os conteúdos
  obrigatórios e ser aprovado na avaliação do módulo atual;
* a nota é calculada aqui a partir do gabarito, que nunca é enviado ao aluno.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

NOTA_MINIMA_PADRAO = 70
PERCENTUAL_VIDEO_PADRAO = 80

STATUS_NAO_INICIADA = "nao_iniciada"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_CONCLUIDA = "concluida"
STATUS_AULA_VALIDOS = {STATUS_NAO_INICIADA, STATUS_EM_ANDAMENTO, STATUS_CONCLUIDA}

# Tipos de aula suportados hoje. A arquitetura permite acrescentar novos tipos
# sem migração destrutiva: basta aceitar o novo valor aqui (o conteúdo já tem
# colunas genéricas de texto, vídeo, imagem e material).
TIPOS_AULA = {"texto", "video", "imagem", "material", "misto"}

# Tipos de pergunta. Hoje só "unica" (múltipla escolha, uma correta) é corrigida
# automaticamente; os demais já podem ser cadastrados para evolução futura
# (verdadeiro/falso, múltiplas respostas, discursiva com correção manual).
TIPOS_PERGUNTA = {"unica", "verdadeiro_falso", "multipla", "discursiva"}


def _agora_txt() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def garantir_tabelas_lms(conn) -> None:
    """Cria (idempotente) as tabelas da hierarquia de cursos.

    Segue o mesmo padrão dos demais ``garantir_tabela_*`` do projeto para
    conviver com o ``init_db`` das migrações sem exigir passo manual em deploy.
    """
    # Garante as tabelas de aluno/matrícula (incl. coluna ``suspenso``) antes das
    # tabelas do LMS: rotas administrativas que fazem JOIN em ``alunos_cursos``
    # funcionam mesmo num banco recém-criado, sem depender da ordem de chamada.
    from backend.aluno_auth import garantir_tabelas_alunos

    garantir_tabelas_alunos(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS curso_config (
            slug TEXT PRIMARY KEY,
            titulo TEXT,
            descricao TEXT,
            imagem TEXT,
            nota_minima INTEGER NOT NULL DEFAULT 70,
            certificado INTEGER NOT NULL DEFAULT 1,
            publicado INTEGER NOT NULL DEFAULT 1,
            atualizado_em TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS curso_modulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            ordem INTEGER NOT NULL DEFAULT 0,
            nota_minima INTEGER,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_curso_modulos_slug ON curso_modulos(slug, ordem)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS curso_aulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            tipo TEXT NOT NULL DEFAULT 'texto',
            conteudo TEXT,
            video_url TEXT,
            capa_url TEXT,
            material_url TEXT,
            ordem INTEGER NOT NULL DEFAULT 0,
            duracao_min INTEGER,
            obrigatoria INTEGER NOT NULL DEFAULT 1,
            percentual_minimo INTEGER,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (modulo_id) REFERENCES curso_modulos(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_curso_aulas_modulo ON curso_aulas(modulo_id, ordem)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS curso_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_id INTEGER NOT NULL UNIQUE,
            titulo TEXT,
            nota_minima INTEGER,
            num_perguntas INTEGER,
            max_tentativas INTEGER,
            intervalo_min INTEGER NOT NULL DEFAULT 0,
            embaralhar_perguntas INTEGER NOT NULL DEFAULT 1,
            embaralhar_opcoes INTEGER NOT NULL DEFAULT 1,
            publicado INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (modulo_id) REFERENCES curso_modulos(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_perguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            enunciado TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'unica',
            explicacao TEXT,
            ordem INTEGER NOT NULL DEFAULT 0,
            ativa INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES curso_quizzes(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_perguntas_quiz ON quiz_perguntas(quiz_id, ordem)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_opcoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            correta INTEGER NOT NULL DEFAULT 0,
            ordem INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (pergunta_id) REFERENCES quiz_perguntas(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_opcoes_pergunta ON quiz_opcoes(pergunta_id, ordem)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_tentativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            aluno_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            nota INTEGER NOT NULL,
            aprovado INTEGER NOT NULL DEFAULT 0,
            total_perguntas INTEGER NOT NULL,
            acertos INTEGER NOT NULL,
            iniciada_em TEXT,
            finalizada_em TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES curso_quizzes(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_tentativas_aluno ON quiz_tentativas(aluno_id, quiz_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tentativa_id INTEGER NOT NULL,
            pergunta_id INTEGER NOT NULL,
            opcao_id INTEGER,
            correta INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (tentativa_id) REFERENCES quiz_tentativas(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_sessoes (
            id TEXT PRIMARY KEY,
            quiz_id INTEGER NOT NULL,
            aluno_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            perguntas TEXT NOT NULL,
            iniciada_em TEXT NOT NULL,
            consumida_em TEXT,
            FOREIGN KEY (quiz_id) REFERENCES curso_quizzes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aluno_aula_progresso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            aula_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'nao_iniciada',
            percentual INTEGER NOT NULL DEFAULT 0,
            iniciada_em TEXT,
            concluida_em TEXT,
            atualizado_em TEXT,
            UNIQUE(aluno_id, aula_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_aluno_aula_prog ON aluno_aula_progresso(aluno_id, slug)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aluno_modulo_liberado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            modulo_id INTEGER NOT NULL,
            liberado_em TEXT NOT NULL,
            origem TEXT,
            UNIQUE(aluno_id, modulo_id)
        )
        """
    )
    # Extensão tolerante da matrícula existente para permitir suspensão de acesso
    # sem apagar o histórico (spec: suspender / reativar acesso do aluno).
    try:
        conn.execute("ALTER TABLE alunos_cursos ADD COLUMN suspenso INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Acesso e configuração do curso
# ---------------------------------------------------------------------------

def obter_config_curso(conn, slug: str) -> dict:
    linha = conn.execute("SELECT * FROM curso_config WHERE slug=?", (slug,)).fetchone()
    if linha:
        return dict(linha)
    return {"slug": slug, "nota_minima": NOTA_MINIMA_PADRAO, "certificado": 1, "publicado": 1}


def curso_e_pago(slug: str) -> bool:
    from backend.course_routes import CATALOGO_CURSOS_PAGOS

    return slug in CATALOGO_CURSOS_PAGOS


def aluno_matriculado(conn, *, aluno_id: int, slug: str) -> bool:
    """Matrícula ativa (não suspensa). Curso gratuito basta ter sessão de aluno."""
    linha = conn.execute(
        "SELECT COALESCE(suspenso,0) AS suspenso FROM alunos_cursos WHERE aluno_id=? AND slug=?",
        (aluno_id, slug),
    ).fetchone()
    if not linha:
        return not curso_e_pago(slug)
    return int(linha["suspenso"] or 0) == 0


def garantir_acesso(conn, *, aluno_id: int, slug: str) -> None:
    from fastapi import HTTPException

    if not aluno_matriculado(conn, aluno_id=aluno_id, slug=slug):
        raise HTTPException(status_code=403, detail="Você ainda não tem acesso a este curso.")


# ---------------------------------------------------------------------------
# Progressão de módulos (cálculo derivado, sempre no backend)
# ---------------------------------------------------------------------------

def _quiz_do_modulo(conn, modulo_id: int) -> Optional[dict]:
    linha = conn.execute(
        "SELECT * FROM curso_quizzes WHERE modulo_id=? AND publicado=1", (modulo_id,)
    ).fetchone()
    return dict(linha) if linha else None


def _melhor_tentativa(conn, *, aluno_id: int, quiz_id: int) -> Optional[dict]:
    linha = conn.execute(
        """
        SELECT nota, aprovado, finalizada_em FROM quiz_tentativas
        WHERE aluno_id=? AND quiz_id=? ORDER BY aprovado DESC, nota DESC LIMIT 1
        """,
        (aluno_id, quiz_id),
    ).fetchone()
    return dict(linha) if linha else None


def _aulas_obrigatorias_concluidas(conn, *, aluno_id: int, modulo_id: int) -> bool:
    aulas = conn.execute(
        "SELECT id FROM curso_aulas WHERE modulo_id=? AND publicado=1 AND obrigatoria=1",
        (modulo_id,),
    ).fetchall()
    if not aulas:
        return True
    ids = [int(a["id"]) for a in aulas]
    placeholders = ",".join("?" for _ in ids)
    concluidas = conn.execute(
        f"""
        SELECT COUNT(*) AS n FROM aluno_aula_progresso
        WHERE aluno_id=? AND status='concluida' AND aula_id IN ({placeholders})
        """,
        (aluno_id, *ids),
    ).fetchone()["n"]
    return int(concluidas) >= len(ids)


def _modulo_concluido(conn, *, aluno_id: int, modulo: dict) -> bool:
    if not _aulas_obrigatorias_concluidas(conn, aluno_id=aluno_id, modulo_id=modulo["id"]):
        return False
    quiz = _quiz_do_modulo(conn, modulo["id"])
    if not quiz:
        return True
    melhor = _melhor_tentativa(conn, aluno_id=aluno_id, quiz_id=quiz["id"])
    return bool(melhor and melhor["aprovado"])


def _modulo_liberado_manualmente(conn, *, aluno_id: int, modulo_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM aluno_modulo_liberado WHERE aluno_id=? AND modulo_id=?",
        (aluno_id, modulo_id),
    ).fetchone() is not None


def estado_progressao(conn, *, aluno_id: int, slug: str) -> dict:
    """Devolve, para cada módulo publicado do curso, se está liberado e concluído.

    Regra: o 1º módulo abre com a matrícula; os seguintes só liberam quando o
    anterior está concluído (aulas obrigatórias + aprovação na avaliação) — ou
    por liberação administrativa manual (``aluno_modulo_liberado``).
    """
    modulos = [
        dict(m)
        for m in conn.execute(
            "SELECT * FROM curso_modulos WHERE slug=? AND publicado=1 ORDER BY ordem, id",
            (slug,),
        ).fetchall()
    ]
    estados: list[dict] = []
    anterior_concluido = True  # o primeiro módulo não depende de nada
    for mod in modulos:
        manual = _modulo_liberado_manualmente(conn, aluno_id=aluno_id, modulo_id=mod["id"])
        liberado = anterior_concluido or manual
        concluido = liberado and _modulo_concluido(conn, aluno_id=aluno_id, modulo=mod)
        estados.append({"modulo": mod, "liberado": liberado, "concluido": concluido})
        # O próximo módulo depende deste estar concluído (a liberação manual de um
        # módulo intermediário também destrava a cascata a partir dele).
        anterior_concluido = concluido or (manual and concluido)
    return {"modulos": estados}


def modulo_liberado(conn, *, aluno_id: int, modulo_id: int) -> bool:
    linha = conn.execute("SELECT slug FROM curso_modulos WHERE id=?", (modulo_id,)).fetchone()
    if not linha:
        return False
    estado = estado_progressao(conn, aluno_id=aluno_id, slug=linha["slug"])
    for item in estado["modulos"]:
        if item["modulo"]["id"] == modulo_id:
            return item["liberado"]
    return False
