"""Cria um curso demonstrativo da Escola Mística — SOMENTE em desenvolvimento.

Uso:
    MISTICA_SEED_DEMO=1 python -m scripts.seed_lms_demo

Salvaguarda: o script se recusa a rodar sem a variável de ambiente
``MISTICA_SEED_DEMO=1`` definida explicitamente, para nunca inserir dados
demonstrativos em produção por engano. Ele é idempotente: se o curso demo já
existir (mesmo slug), não duplica módulos/aulas.

Gera:
    * curso "escola-demo" publicado (nota mínima 70%);
    * 2 módulos, com 2 aulas obrigatórias cada;
    * 1 avaliação por módulo com perguntas de teste.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

SLUG = "escola-demo"


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    if os.environ.get("MISTICA_SEED_DEMO") != "1":
        print("Recusado: defina MISTICA_SEED_DEMO=1 para semear o curso demo (evita rodar em produção).")
        return 2

    from backend.database import conectar
    from backend.lms import garantir_tabelas_lms

    with conectar() as conn:
        garantir_tabelas_lms(conn)
        ja = conn.execute("SELECT 1 FROM curso_modulos WHERE slug=? LIMIT 1", (SLUG,)).fetchone()
        if ja:
            print(f"Curso demo '{SLUG}' já existe — nada a fazer (idempotente).")
            return 0

        conn.execute(
            """
            INSERT INTO curso_config (slug, titulo, descricao, nota_minima, certificado, publicado, atualizado_em)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(slug) DO NOTHING
            """,
            (SLUG, "Curso Demonstrativo da Escola Mística", "Curso de exemplo para validar a plataforma progressiva.", 70, 1, 1, _agora()),
        )

        def add_modulo(titulo, ordem):
            return int(conn.execute(
                "INSERT INTO curso_modulos (slug, titulo, descricao, ordem, publicado, criado_em) VALUES (?,?,?,?,?,?)",
                (SLUG, titulo, f"Descrição do {titulo}.", ordem, 1, _agora()),
            ).lastrowid)

        def add_aula(modulo_id, titulo, ordem, tipo="texto", video=None):
            conn.execute(
                """
                INSERT INTO curso_aulas
                (modulo_id, titulo, descricao, tipo, conteudo, video_url, ordem, obrigatoria, publicado, criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (modulo_id, titulo, "Conteúdo de exemplo.", tipo, f"<p>Conteúdo de exemplo da aula <strong>{titulo}</strong>.</p>", video, ordem, 1, 1, _agora()),
            )

        def add_quiz(modulo_id):
            qid = int(conn.execute(
                "INSERT INTO curso_quizzes (modulo_id, titulo, nota_minima, embaralhar_perguntas, embaralhar_opcoes, publicado, criado_em) VALUES (?,?,?,?,?,?,?)",
                (modulo_id, "Avaliação do módulo", 70, 1, 1, 1, _agora()),
            ).lastrowid)
            return qid

        def add_pergunta(quiz_id, enunciado, opcoes, correta_idx, explicacao):
            pid = int(conn.execute(
                "INSERT INTO quiz_perguntas (quiz_id, enunciado, tipo, explicacao, ordem, ativa, criado_em) VALUES (?,?,?,?,?,?,?)",
                (quiz_id, enunciado, "unica", explicacao, 0, 1, _agora()),
            ).lastrowid)
            for i, texto in enumerate(opcoes):
                conn.execute(
                    "INSERT INTO quiz_opcoes (pergunta_id, texto, correta, ordem) VALUES (?,?,?,?)",
                    (pid, texto, 1 if i == correta_idx else 0, i),
                )

        m1 = add_modulo("Módulo 1 — Fundamentos", 0)
        add_aula(m1, "Introdução", 0)
        add_aula(m1, "Conteúdo principal", 1)
        add_aula(m1, "Vídeo de apoio", 2, tipo="video", video="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        q1 = add_quiz(m1)
        add_pergunta(q1, "Qual é o primeiro passo na trilha da Escola Mística?", ["Concluir as aulas obrigatórias", "Pular para o certificado", "Ignorar a avaliação"], 0, "A progressão começa concluindo as aulas obrigatórias do módulo.")
        add_pergunta(q1, "A nota mínima padrão para aprovação é:", ["50%", "70%", "100%"], 1, "O padrão configurável sugerido é 70%.")

        m2 = add_modulo("Módulo 2 — Aprofundamento", 1)
        add_aula(m2, "Revisão", 0)
        add_aula(m2, "Prática guiada", 1)
        q2 = add_quiz(m2)
        add_pergunta(q2, "O próximo módulo é liberado quando o aluno:", ["Paga novamente", "É aprovado na avaliação anterior", "Fecha o navegador"], 1, "A liberação ocorre após aprovação na avaliação do módulo anterior.")
        add_pergunta(q2, "O progresso do aluno é salvo:", ["Somente no navegador", "No backend, vinculado ao aluno", "Em nenhum lugar"], 1, "O progresso oficial vive no backend, associado ao aluno.")

    print(f"Curso demo '{SLUG}' criado com 2 módulos, aulas e avaliações. Matricule um aluno via painel para testar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
