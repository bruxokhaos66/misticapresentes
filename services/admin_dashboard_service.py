"""Agregação de indicadores para o Centro de Operações administrativo.

Todas as consultas são somente leitura e reutilizam a mesma conexão SQLite
por chamada (evita abrir uma conexão por KPI). O resultado fica em cache por
CACHE_TTL_SEGUNDOS para que o polling do painel (Fase 1/Fase 3) não repita a
mesma bateria de consultas a cada poucos segundos quando várias abas/usuários
estão olhando o painel ao mesmo tempo.

Nenhuma função aqui grava dado nenhum -- só lê tabelas já existentes
(pedidos, pedidos_itens, produtos, clientes, campanhas, pedidos_cursos).
"""

from __future__ import annotations

import time
from datetime import datetime

from backend.database import conectar

CACHE_TTL_SEGUNDOS = 8
ESTOQUE_CRITICO_ATE = 3

_cache: dict = {"expira_em": 0.0, "dados": None}


def _hoje_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _mes_str() -> str:
    return datetime.now().strftime("%Y-%m")


def _contar(conn, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int((row[0] if row else 0) or 0)


def _somar(conn, sql: str, params: tuple = ()) -> float:
    row = conn.execute(sql, params).fetchone()
    return float((row[0] if row else 0) or 0.0)


def _calcular_kpis(conn) -> dict:
    hoje = _hoje_str()
    hoje_like = f"{hoje}%"
    mes_like = f"{_mes_str()}%"

    aguardando_pagamento = _contar(
        conn,
        "SELECT COUNT(*) FROM pedidos WHERE status IN ('Aguardando pagamento','Pagamento divergente')",
    )
    pagos_aguardando_envio = _contar(
        conn,
        """
        SELECT COUNT(*) FROM pedidos
         WHERE status NOT IN ('Aguardando pagamento','Pagamento divergente','Cancelado')
           AND COALESCE(status_pedido,'novo') IN ('novo','confirmado','em_preparacao','pronto_retirada')
        """,
    )
    enviados_hoje = _contar(
        conn,
        """
        SELECT COUNT(*) FROM pedido_status_log
         WHERE status='enviado' AND substr(COALESCE(data_hora,''),1,10)=?
        """,
        (hoje,),
    )

    faturamento_hoje = _somar(
        conn,
        "SELECT SUM(total_final) FROM pedidos WHERE status != 'Cancelado' AND substr(COALESCE(data_iso,''),1,10)=?",
        (hoje,),
    )
    faturamento_mes = _somar(
        conn,
        "SELECT SUM(total_final) FROM pedidos WHERE status != 'Cancelado' AND substr(COALESCE(data_iso,''),1,7)=?",
        (_mes_str(),),
    )
    qtd_pedidos_mes = _contar(
        conn,
        "SELECT COUNT(*) FROM pedidos WHERE status != 'Cancelado' AND substr(COALESCE(data_iso,''),1,7)=?",
        (_mes_str(),),
    )
    ticket_medio = round(faturamento_mes / qtd_pedidos_mes, 2) if qtd_pedidos_mes else 0.0

    produtos_sem_estoque = _contar(conn, "SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND COALESCE(quantidade,0)<=0")
    produtos_estoque_critico = _contar(
        conn,
        "SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND COALESCE(quantidade,0)>0 AND COALESCE(quantidade,0)<=?",
        (ESTOQUE_CRITICO_ATE,),
    )

    novos_clientes_hoje = _contar(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT lower(COALESCE(telefone,'')) AS chave, MIN(substr(COALESCE(data_iso,''),1,10)) AS primeira
              FROM pedidos
             WHERE COALESCE(telefone,'') != ''
             GROUP BY chave
        ) t WHERE t.primeira = ?
        """,
        (hoje,),
    )

    from backend.course_routes import garantir_tabela_pedidos_cursos

    garantir_tabela_pedidos_cursos(conn)
    cursos_vendidos_mes = _contar(
        conn,
        "SELECT COUNT(*) FROM pedidos_cursos WHERE status='Pago' AND substr(COALESCE(criado_em,''),1,7)=?",
        (_mes_str(),),
    )

    pedidos_pix_mes = _contar(
        conn,
        "SELECT COUNT(*) FROM pedidos WHERE status != 'Cancelado' AND substr(COALESCE(data_iso,''),1,7)=? AND forma_pagamento LIKE 'Pix%'",
        (_mes_str(),),
    )
    pedidos_cartao_mes = _contar(
        conn,
        """
        SELECT COUNT(*) FROM pedidos
         WHERE status != 'Cancelado' AND substr(COALESCE(data_iso,''),1,7)=?
           AND COALESCE(forma_pagamento,'') != '' AND forma_pagamento NOT LIKE 'Pix%'
        """,
        (_mes_str(),),
    )

    campanhas_ativas = _contar(
        conn,
        """
        SELECT COUNT(*) FROM campanhas
         WHERE COALESCE(ativo,1)=1
           AND (data_inicio IS NULL OR data_inicio='' OR data_inicio<=?)
           AND (data_fim IS NULL OR data_fim='' OR data_fim>=?)
        """,
        (hoje, hoje),
    )

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "pedidos_aguardando_pagamento": aguardando_pagamento,
        "pedidos_pagos_aguardando_envio": pagos_aguardando_envio,
        "pedidos_enviados_hoje": enviados_hoje,
        "faturamento_hoje": faturamento_hoje,
        "faturamento_mes": faturamento_mes,
        "ticket_medio_mes": ticket_medio,
        "produtos_sem_estoque": produtos_sem_estoque,
        "produtos_estoque_critico": produtos_estoque_critico,
        "novos_clientes_hoje": novos_clientes_hoje,
        "cursos_vendidos_mes": cursos_vendidos_mes,
        "pedidos_pix_mes": pedidos_pix_mes,
        "pedidos_cartao_mes": pedidos_cartao_mes,
        "campanhas_ativas": campanhas_ativas,
    }


def _montar_alertas(kpis: dict) -> list[dict]:
    alertas = []
    if kpis["produtos_sem_estoque"] > 0:
        alertas.append({"tipo": "estoque_zerado", "nivel": "alerta", "mensagem": f"{kpis['produtos_sem_estoque']} produto(s) sem estoque."})
    if kpis["produtos_estoque_critico"] > 0:
        alertas.append({"tipo": "estoque_critico", "nivel": "atencao", "mensagem": f"{kpis['produtos_estoque_critico']} produto(s) com estoque crítico."})
    if kpis["pedidos_aguardando_pagamento"] > 0:
        alertas.append({"tipo": "pedidos_aguardando_pagamento", "nivel": "info", "mensagem": f"{kpis['pedidos_aguardando_pagamento']} pedido(s) aguardando pagamento."})
    if kpis["pedidos_pagos_aguardando_envio"] > 0:
        alertas.append({"tipo": "pedidos_aguardando_envio", "nivel": "atencao", "mensagem": f"{kpis['pedidos_pagos_aguardando_envio']} pedido(s) pagos aguardando envio."})
    return alertas


def obter_kpis_operacionais(usar_cache: bool = True) -> dict:
    agora = time.monotonic()
    if usar_cache and _cache["dados"] is not None and agora < _cache["expira_em"]:
        return _cache["dados"]

    with conectar() as conn:
        kpis = _calcular_kpis(conn)
    kpis["alertas"] = _montar_alertas(kpis)

    _cache["dados"] = kpis
    _cache["expira_em"] = agora + CACHE_TTL_SEGUNDOS
    return kpis


def limpar_cache_kpis() -> None:
    """Usado pelos testes para garantir leitura fresca entre casos."""
    _cache["dados"] = None
    _cache["expira_em"] = 0.0
