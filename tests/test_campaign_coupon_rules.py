from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from backend.campaign_routes import buscar_cupom_ativo, calcular_desconto_cupom


def _conexao() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE campanhas (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL DEFAULT 0,
            codigo_cupom TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            data_inicio TEXT,
            data_fim TEXT
        )
        """
    )
    return conn


def _inserir_campanha(
    conn: sqlite3.Connection,
    *,
    codigo: str,
    tipo: str = "desconto_percentual",
    valor: float = 10,
    ativo: int = 1,
    inicio: datetime | None = None,
    fim: datetime | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO campanhas
            (titulo, tipo, valor, codigo_cupom, ativo, data_inicio, data_fim)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"Campanha {codigo}",
            tipo,
            valor,
            codigo,
            ativo,
            inicio.isoformat(timespec="seconds") if inicio else None,
            fim.isoformat(timespec="seconds") if fim else None,
        ),
    )
    conn.commit()


def test_desconto_fixo_nunca_ultrapassa_subtotal():
    conn = _conexao()
    try:
        _inserir_campanha(conn, codigo="FIXO50", tipo="desconto_fixo", valor=50)
        campanha = buscar_cupom_ativo(conn, "fixo50")

        assert campanha is not None
        resultado = calcular_desconto_cupom(campanha, subtotal=30)
        assert resultado["desconto"] == 30.0
        assert resultado["frete_gratis"] is False
    finally:
        conn.close()


def test_desconto_percentual_calcula_e_arredonda_corretamente():
    conn = _conexao()
    try:
        _inserir_campanha(conn, codigo="PERC15", tipo="desconto_percentual", valor=15)
        campanha = buscar_cupom_ativo(conn, "perc15")

        assert campanha is not None
        # 15% de 33.33 = 4.9995, que deve arredondar para 5.00 (ROUND_HALF_UP).
        resultado = calcular_desconto_cupom(campanha, subtotal=33.33)
        assert resultado["desconto"] == 5.0
        assert resultado["frete_gratis"] is False
    finally:
        conn.close()


def test_desconto_percentual_nunca_ultrapassa_subtotal():
    conn = _conexao()
    try:
        _inserir_campanha(conn, codigo="PERC120", tipo="desconto_percentual", valor=120)
        campanha = buscar_cupom_ativo(conn, "perc120")

        assert campanha is not None
        resultado = calcular_desconto_cupom(campanha, subtotal=40)
        # 120% de 40 seria 48, mas o desconto nunca pode ultrapassar o subtotal.
        assert resultado["desconto"] == 40.0
    finally:
        conn.close()


def test_frete_gratis_nao_altera_subtotal():
    conn = _conexao()
    try:
        _inserir_campanha(conn, codigo="FRETEGRATIS", tipo="frete_gratis", valor=0)
        campanha = buscar_cupom_ativo(conn, "fretegratis")

        assert campanha is not None
        resultado = calcular_desconto_cupom(campanha, subtotal=125.90)
        assert resultado["desconto"] == 0.0
        assert resultado["frete_gratis"] is True
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("codigo", "ativo", "inicio_delta", "fim_delta"),
    [
        ("INATIVO", 0, None, None),
        ("FUTURO", 1, 1, 3),
        ("EXPIRADO", 1, -3, -1),
    ],
)
def test_cupom_fora_de_vigencia_nao_e_encontrado(codigo, ativo, inicio_delta, fim_delta):
    agora = datetime.now()
    conn = _conexao()
    try:
        _inserir_campanha(
            conn,
            codigo=codigo,
            ativo=ativo,
            inicio=agora + timedelta(days=inicio_delta) if inicio_delta is not None else None,
            fim=agora + timedelta(days=fim_delta) if fim_delta is not None else None,
        )

        assert buscar_cupom_ativo(conn, codigo.lower()) is None
    finally:
        conn.close()


def test_cupom_vigente_e_localizado_sem_diferenciar_maiusculas():
    agora = datetime.now()
    conn = _conexao()
    try:
        _inserir_campanha(
            conn,
            codigo="VIGENTE10",
            inicio=agora - timedelta(days=1),
            fim=agora + timedelta(days=1),
        )

        campanha = buscar_cupom_ativo(conn, " vigente10 ")
        assert campanha is not None
        assert campanha["codigo_cupom"] == "VIGENTE10"
    finally:
        conn.close()
