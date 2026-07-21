from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar
from backend.frete import PRAZO_ENTREGA_DIAS_UTEIS
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_sessao_ou_chave_api, validar_sessao
from backend.rate_limit import limitar_requisicoes

# Endereço oficial de retirada — nunca inventar rua, CEP ou complemento além
# do que está definido aqui (Fase 3 — entrega ou retirada no checkout).
ENDERECO_LOJA = "Mística Presentes — Galeria Ody, nº 2400, sala 07, Centro, Pinhalzinho/SC"

logger = get_logger(__name__)

limitar_status_pedido = limitar_requisicoes("status_pedido", limite=20, janela_segundos=60)
limitar_cancelar_pedido = limitar_requisicoes("cancelar_pedido", limite=20, janela_segundos=60)

router = APIRouter(prefix="/api", tags=["pedidos-status"])

# Classificação persistida de cada item do pedido (pedidos_itens.tipo_item —
# ver database/migrations.py, coluna com CHECK travando estes três valores).
# Calculada pelo servidor a partir do produto autoritativo no momento da
# criação do pedido (nunca aceita de um campo enviado pelo cliente) e nunca
# mais reavaliada contra o catálogo depois: um produto sob encomenda tem
# estoque físico zero por definição, então a confirmação de pagamento nunca
# pode tentar baixar/repor estoque físico de um item TIPO_ITEM_SOB_ENCOMENDA.
#
# TIPO_ITEM_LEGADO_AMBIGUO é o valor padrão para itens de pedidos criados
# antes desta coluna existir cuja classificação real não pôde ser
# reconstruída com evidência confiável (ver
# database/migrations.py::_backfill_tipo_item_pedidos_itens). Nunca é tratado
# como físico nem como sob encomenda — bloqueia a baixa de estoque para
# conciliação administrativa (ver baixar_estoque_do_pedido), do mesmo jeito
# que qualquer outro valor não reconhecido (dado corrompido/editado por fora
# do fluxo normal).
TIPO_ITEM_FISICO = "fisico"
TIPO_ITEM_SOB_ENCOMENDA = "sob_encomenda"
TIPO_ITEM_LEGADO_AMBIGUO = "legado_ambiguo"
TIPOS_ITEM_VALIDOS = {TIPO_ITEM_FISICO, TIPO_ITEM_SOB_ENCOMENDA}

STATUS_PEDIDO_AGUARDANDO_ENCOMENDA = "Aguardando encomenda"

# "Comprovante enviado" e "Pagamento em análise" (ver
# backend/pedido_notificacao_routes.py) são estados intermediários entre a
# geração do Pix e a confirmação financeira: registram que o cliente indicou
# ter pago e que o comprovante está sob conferência administrativa, mas
# nunca, por si só, liberam estoque nem confirmam pagamento — isso continua
# exclusivo de POST /api/pagamentos (backend/payment_routes.py), sem
# alteração na lógica de conciliação já existente.
STATUS_PEDIDO_COMPROVANTE_ENVIADO = "Comprovante enviado"
STATUS_PEDIDO_PAGAMENTO_EM_ANALISE = "Pagamento em análise"

STATUS_PEDIDO = {
    "Aguardando pagamento",
    "Pagamento divergente",
    STATUS_PEDIDO_COMPROVANTE_ENVIADO,
    STATUS_PEDIDO_PAGAMENTO_EM_ANALISE,
    "Pagamento confirmado",
    STATUS_PEDIDO_AGUARDANDO_ENCOMENDA,
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
    "Concluído",
}

STATUS_BAIXA_ESTOQUE = {"Pagamento confirmado", "Separando pedido"}

# Status a partir dos quais o pedido já avançou além da confirmação de
# pagamento. Uma divergência de valor detectada nesse ponto (ex.: um segundo
# pagamento incompleto registrado por engano) não deve regredir o status do
# pedido de volta para "Pagamento divergente" — apenas fica registrada no
# histórico para conciliação administrativa.
STATUS_PEDIDO_CONCLUIDOS = {
    "Pagamento confirmado",
    STATUS_PEDIDO_AGUARDANDO_ENCOMENDA,
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Concluído",
}

STATUS_ALIASES = {"Pago": "Pagamento confirmado", "Em separação": "Separando pedido"}

MINUTOS_EXPIRACAO_PEDIDO_PENDENTE = int(os.environ.get("MISTICA_MINUTOS_EXPIRACAO_PEDIDO", "30") or "30")


def normalizar_status(status: str) -> str:
    status = str(status or "").strip()
    status = STATUS_ALIASES.get(status, status)
    if status not in STATUS_PEDIDO:
        raise HTTPException(status_code=400, detail="Status de pedido inválido.")
    return status


def bloquear_avanco_financeiro_sem_conciliacao(conn, venda_id: int, status_destino: str):
    """'Pagamento confirmado'/'Aguardando encomenda' (e a baixa de estoque que
    dela depende) só podem ser produzidos pela conciliação de valor em
    backend/payment_routes.py (POST /api/pagamentos ou o webhook Pix, que
    comparam o valor recebido com pedidos.total_final antes de confirmar). As
    rotas genéricas de status de pedido (esta e a duplicata em
    order_api_guard_inner_routes.py) aceitam esses dois valores como válidos
    de STATUS_PEDIDO para fins de consulta/histórico, mas nunca podem ser o
    caminho que produz esse estado — senão qualquer chamada com a chave de
    API confirmaria um pedido sem nenhum valor ter sido validado. Pelo mesmo
    motivo, "Separando pedido" (que também baixa estoque, ver
    STATUS_BAIXA_ESTOQUE) só é aceito depois que o pedido já estiver de fato
    confirmado."""
    if status_destino == STATUS_PEDIDO_AGUARDANDO_ENCOMENDA:
        raise HTTPException(
            status_code=409,
            detail="Aguardando encomenda só pode ser definido via POST /api/pagamentos, com o valor recebido conciliado contra o total do pedido.",
        )
    if status_destino not in STATUS_BAIXA_ESTOQUE:
        return
    if status_destino == "Pagamento confirmado":
        raise HTTPException(
            status_code=409,
            detail="Pagamento confirmado só pode ser definido via POST /api/pagamentos, com o valor recebido conciliado contra o total do pedido.",
        )
    venda = conn.execute("SELECT status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    status_atual = str(venda["status"] or "") if venda else ""
    if status_atual not in STATUS_PEDIDO_CONCLUIDOS:
        raise HTTPException(
            status_code=409,
            detail="Só é possível avançar para 'Separando pedido' depois que o pagamento for confirmado via POST /api/pagamentos.",
        )


class PedidoStatusIn(BaseModel):
    status: str = Field(min_length=1)
    usuario: str = "Admin"
    observacao: Optional[str] = None


class PedidoObservacaoIn(BaseModel):
    observacao: str = ""
    usuario: str = "Admin"


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.")


def expirar_pedidos_pendentes(conn, agora: str | None = None):
    """Cancela automaticamente pedidos cujo prazo (expira_em) já passou e cujo
    pagamento nunca foi confirmado com o valor correto, devolvendo ao estoque
    a reserva feita na criação do pedido (ver site_stock_routes.py).

    Cobre tanto 'Aguardando pagamento' quanto 'Pagamento divergente': um
    pagamento com valor incorreto (ver backend/payment_routes.py) não é
    tratado como pago, então a reserva de estoque não pode ficar presa para
    sempre só porque o pedido saiu de 'Aguardando pagamento' — ele continua
    expirando no mesmo prazo se ninguém resolver a divergência a tempo.

    Roda periodicamente em cada worker (ver backend/main.py), então mais de um
    processo pode disputar o mesmo pedido vencido ao mesmo tempo. O UPDATE
    abaixo só processa o pedido se conseguir reivindicá-lo (WHERE status ainda
    é um dos dois acima); o SQLite serializa escritores, então um worker que
    perder a disputa vê rowcount 0 e pula o pedido, evitando repor estoque em
    dobro."""
    agora = agora or datetime.now().isoformat(timespec="seconds")
    expirados = conn.execute(
        """
        SELECT id FROM pedidos
        WHERE COALESCE(status,'') IN ('Aguardando pagamento', 'Pagamento divergente')
          AND expira_em IS NOT NULL
          AND expira_em < ?
        """,
        (agora,),
    ).fetchall()
    total_expirados = 0
    for venda in expirados:
        claim = conn.execute(
            "UPDATE pedidos SET status='Cancelado', expirado_em=? WHERE id=? AND status IN ('Aguardando pagamento', 'Pagamento divergente')",
            (agora, venda["id"]),
        )
        if claim.rowcount == 0:
            continue
        repor_estoque_cancelamento(conn, venda["id"], "Sistema", agora)
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda["id"], "Cancelado", "Sistema", "Expirado automaticamente: pagamento não confirmado a tempo", agora),
        )
        total_expirados += 1
    if total_expirados:
        conn.commit()
    return total_expirados


def venda_para_pedido(conn, venda):
    itens = conn.execute(
        """
        SELECT id, pedido_id AS venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total, tipo_item
        FROM pedidos_itens
        WHERE pedido_id=?
        ORDER BY id ASC
        """,
        (venda["id"],),
    ).fetchall()
    historico = conn.execute(
        """
        SELECT id, venda_id, status, usuario, observacao, data_hora
        FROM pedido_status_log
        WHERE venda_id=?
        ORDER BY id DESC
        """,
        (venda["id"],),
    ).fetchall()
    data = dict(venda)
    data["itens"] = [dict(row) for row in itens]
    data["historico_status"] = [dict(row) for row in historico]
    return data


def buscar_produto_para_baixa(conn, item):
    codigo = str(item["codigo_p"] or "").strip()
    nome = str(item["nome_p"] or "").strip()

    if codigo:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (codigo,),
        ).fetchone()
        if produto:
            return produto

        if codigo.isdigit():
            produto = conn.execute(
                "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
                (int(codigo),),
            ).fetchone()
            if produto:
                return produto

    if nome:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE lower(trim(nome))=lower(trim(?)) AND COALESCE(ativo,1)=1",
            (nome,),
        ).fetchone()
        if produto:
            return produto

    return None


def _tipo_item_normalizado(item) -> str:
    """Lê pedidos_itens.tipo_item sem assumir nada: normaliza só
    maiúsculas/minúsculas e espaços (nunca localização/tradução de texto) e
    devolve como está — quem chama decide o que fazer com um valor fora de
    TIPOS_ITEM_VALIDOS (TIPO_ITEM_LEGADO_AMBIGUO ou qualquer outro dado
    corrompido/editado por fora do fluxo normal). Nunca tratado como físico
    por padrão — ver baixar_estoque_do_pedido/repor_estoque_cancelamento, que
    bloqueiam em vez de adivinhar."""
    return str(item["tipo_item"] or "").strip().lower()


def pedido_tem_item_sob_encomenda(conn, venda_id: int) -> bool:
    """Usado para decidir, na confirmação de pagamento, se o pedido deve ir
    para STATUS_PEDIDO_AGUARDANDO_ENCOMENDA em vez de 'Pagamento confirmado'
    — lê sempre a classificação persistida no item, nunca o catálogo atual."""
    row = conn.execute(
        "SELECT 1 FROM pedidos_itens WHERE pedido_id=? AND tipo_item=? LIMIT 1",
        (venda_id, TIPO_ITEM_SOB_ENCOMENDA),
    ).fetchone()
    return row is not None


def baixar_estoque_do_pedido(conn, venda_id: int, usuario: str, agora: str, motivo: str = "Baixa automática ao confirmar/separar pedido") -> bool:
    """Processa a baixa de estoque físico do pedido uma única vez (guarda de
    idempotência: pedidos.estoque_baixado). Itens sob encomenda (ver
    TIPO_ITEM_SOB_ENCOMENDA) nunca decrementam produtos.quantidade nem geram
    movimentação de saída — não têm estoque físico por definição. Retorna
    True somente se estoque físico foi de fato decrementado nesta chamada
    (usado por quem chama para saber se "baixou estoque agora", distinto do
    booleano interno de "baixa já processada")."""
    venda = conn.execute("SELECT id, estoque_baixado FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if int(venda["estoque_baixado"] or 0) == 1:
        return False

    itens = conn.execute(
        """
        SELECT id, codigo_p, nome_p, quantidade, tipo_item
        FROM pedidos_itens
        WHERE pedido_id=?
        ORDER BY id ASC
        """,
        (venda_id,),
    ).fetchall()
    if not itens:
        return False

    itens_fisicos_baixados = 0
    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        tipo_item = _tipo_item_normalizado(item)
        if tipo_item == TIPO_ITEM_SOB_ENCOMENDA:
            # Sob encomenda: nenhuma baixa física, nenhuma movimentação de
            # saída fictícia. O item continua rastreável em pedidos_itens.
            continue
        if tipo_item not in TIPOS_ITEM_VALIDOS:
            # Classificação ausente/corrompida: nunca assumimos "físico" por
            # padrão (isso reintroduziria o bug original para itens que na
            # verdade eram sob encomenda). Fica bloqueado para conciliação
            # administrativa em vez de confirmar/baixar estoque silenciosamente.
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Item '{item['nome_p'] or item['codigo_p']}' do pedido #{venda_id} está sem "
                    "classificação de estoque confiável (pedido legado ambíguo); requer conciliação "
                    "administrativa antes de aplicar a baixa de estoque."
                ),
            )
        produto = buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado para baixa: {item['nome_p'] or item['codigo_p']}")
        # UPDATE com guarda de saldo no próprio WHERE: a checagem e a escrita
        # acontecem no mesmo comando, então duas confirmações concorrentes para o
        # mesmo produto não conseguem, juntas, levar o estoque a negativo (ver
        # backend/site_stock_routes.py::baixar_estoque_atomico para o mesmo padrão).
        cur = conn.execute(
            "UPDATE produtos SET quantidade = quantidade - ? WHERE id=? AND quantidade >= ?",
            (quantidade, produto["id"], quantidade),
        )
        if cur.rowcount == 0:
            atual = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto["id"],)).fetchone()
            disponivel = int(atual["quantidade"] or 0) if atual else 0
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {disponivel}")
        itens_fisicos_baixados += 1

    # Marca a baixa como processada (idempotência) mesmo quando o pedido é só
    # sob encomenda e nenhum item físico foi decrementado: chamar de novo não
    # teria nada a fazer, mas o registro de log/auditoria abaixo não pode ser
    # duplicado numa reconfirmação. O booleano de retorno (não esta coluna) é
    # quem informa com precisão se estoque físico baixou nesta chamada.
    conn.execute("UPDATE pedidos SET estoque_baixado=1, estoque_baixado_em=? WHERE id=?", (agora, venda_id))
    if itens_fisicos_baixados:
        status_log = "Estoque baixado"
        observacao = motivo if itens_fisicos_baixados == len(itens) else f"{motivo} (parcial: {itens_fisicos_baixados} de {len(itens)} item(ns) exigiam baixa física; o restante é sob encomenda)"
    else:
        status_log = "Pedido aguarda encomenda"
        observacao = f"{motivo} — nenhum item físico: pedido é somente sob encomenda, aguarda compra/separação com o fornecedor."
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (venda_id, status_log, usuario or "Admin", observacao, agora),
    )
    registrar_auditoria(
        conn,
        "estoque",
        venda_id,
        "baixa_pedido",
        usuario,
        depois={"motivo": motivo, "itens": len(itens), "itens_fisicos_baixados": itens_fisicos_baixados},
    )
    return itens_fisicos_baixados > 0


def repor_estoque_cancelamento(conn, venda_id: int, usuario: str, agora: str):
    """Repõe o estoque físico baixado de um pedido cancelado, uma única vez.

    Reivindicação atômica: a checagem (o pedido teve baixa física e ainda
    não foi reposto) e a escrita (marca reposto=1) acontecem no mesmo
    UPDATE, com guarda no próprio WHERE — não um SELECT seguido de um
    UPDATE incondicional. Duas chamadas concorrentes para o mesmo pedido
    (dois cancelamentos simultâneos, cancelamento x expiração, retry da
    mesma requisição) nunca conseguem, juntas, repor o mesmo pedido duas
    vezes: só uma reivindica (rowcount==1); a outra vê rowcount==0 e não
    faz nada."""
    venda = conn.execute("SELECT id FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    claim = conn.execute(
        """
        UPDATE pedidos
        SET estoque_reposto_cancelamento=1, estoque_reposto_em=?
        WHERE id=? AND estoque_baixado=1 AND COALESCE(estoque_reposto_cancelamento,0)=0
        """,
        (agora, venda_id),
    )
    if claim.rowcount == 0:
        # Ou o pedido nunca teve baixa física (nada a repor, ex.: só sob
        # encomenda), ou outra chamada concorrente já reivindicou a
        # reposição — nos dois casos, não repor de novo.
        return False

    itens = conn.execute("SELECT id, codigo_p, nome_p, quantidade, tipo_item FROM pedidos_itens WHERE pedido_id=? ORDER BY id ASC", (venda_id,)).fetchall()
    total = 0
    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        if _tipo_item_normalizado(item) != TIPO_ITEM_FISICO:
            # sob_encomenda nunca teve estoque físico baixado (repor criaria
            # saldo positivo fictício). legado_ambiguo (não deveria coexistir
            # com estoque_baixado=1 depois do PR #313, já que
            # baixar_estoque_do_pedido bloqueia antes de chegar lá — mantido
            # defensivo aqui) também não é reposto: nunca assumimos "físico"
            # por padrão para um dado ambíguo. Pular aqui (em vez de
            # levantar) é deliberado: expirar_pedidos_pendentes processa
            # vários pedidos numa única transação, e uma exceção no meio
            # desfaria a expiração de todos os outros pedidos do lote.
            continue
        produto = buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado para reposição: {item['nome_p'] or item['codigo_p']}")
        conn.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (quantidade, produto["id"]))
        total += quantidade

    conn.execute(
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
        (venda_id, "Estoque reposto", usuario or "Admin", f"Reposição automática: {total} item(ns)", agora),
    )
    registrar_auditoria(conn, "estoque", venda_id, "reposicao_cancelamento", usuario, depois={"total_itens": total})
    return total > 0


# Estados a partir dos quais o cancelamento genérico (DELETE /api/pedidos/{id}
# e as rotas equivalentes) nunca é aplicado silenciosamente — exigem
# conciliação administrativa fora deste fluxo (ex.: processo de devolução,
# fora do escopo deste PR). "Cancelado" não está aqui porque tem tratamento
# próprio (idempotente, não bloqueado).
#
# Regra, status a status (este sistema não tem um status "Enviado" literal —
# STATUS_PEDIDO tem só os listados em order_status_routes.py):
# - Aguardando pagamento / Pagamento divergente: cancelável (nenhum estoque
#   físico comprometido além da reserva, que é sempre reposta).
# - Pagamento confirmado / Aguardando encomenda: cancelável — cancelamento de
#   pedido pago é uma ação administrativa própria (ver docstring de
#   cancelar_com_reposicao), não uma corrida com o pagamento em si.
# - Separando pedido: cancelável — o estoque ainda não saiu fisicamente da
#   loja, a separação é reversível operacionalmente.
# - Pronto para retirada / Entregue: bloqueados. "Pronto para retirada" é o
#   estado deste sistema mais próximo de um "Enviado"/handoff físico
#   avançado — sem uma regra comercial explícita para cancelamento
#   automático nesse ponto, a escolha conservadora é exigir conciliação
#   administrativa (409) em vez de assumir que ainda é seguro devolver o
#   item ao estoque sem confirmação humana de que ele não saiu fisicamente.
# - Concluído: bloqueado (pedido já finalizado).
STATUS_CANCELAMENTO_BLOQUEADO = {"Pronto para retirada", "Entregue", "Concluído"}


def _sanitizar_motivo_cancelamento(observacao: str | None) -> str:
    """Nunca aceita motivo arbitrário sem limite: trunca e remove
    caracteres de controle antes de gravar em histórico/auditoria."""
    texto = str(observacao or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:280]


def cancelar_com_reposicao(conn, venda_id: int, usuario: str, observacao: str | None, agora: str):
    """Cancela o pedido de forma atômica e idempotente.

    A leitura do estado atual, a decisão de cancelar e a escrita do novo
    status acontecem dentro de um único UPDATE com guarda no WHERE — nunca
    um SELECT seguido de um UPDATE incondicional. Isso torna a operação
    determinística sob concorrência: duas chamadas de cancelamento
    simultâneas, ou um cancelamento correndo contra uma confirmação de
    pagamento/expiração concorrente, nunca decidem com base no mesmo
    estado "antigo" lido por outra — só uma reivindica a transição
    (rowcount==1); a(s) outra(s) veem rowcount==0 e reagem ao estado JÁ
    ATUAL (resposta idempotente se o pedido já está cancelado; 409 se está
    num status que bloqueia cancelamento por esta rota).

    A prioridade de cancelamento sobre uma confirmação de pagamento
    simultânea é deliberada: uma ação explícita de cancelar (administrativa
    ou do cliente) tem precedência sobre um webhook de pagamento assíncrono
    chegando no mesmo instante (ver backend/payment_routes.py::
    _aplicar_resultado_confirmacao, que usa uma reivindicação própria e
    desiste — nunca reabre — se o pedido já mudou de status). Se o
    pagamento venceu a corrida antes do cancelamento ser solicitado,
    cancelar o pedido já confirmado continua sendo uma ação administrativa
    válida e separada, com a mesma reposição de estoque de qualquer outro
    cancelamento pós-pagamento."""
    venda = conn.execute("SELECT id, status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    status_antes = str(venda["status"] or "")

    # Os placeholders de STATUS_CANCELAMENTO_BLOQUEADO são gerados a partir
    # do próprio set (nunca hardcoded em paralelo) para que a lista de
    # status bloqueados nunca fique dessincronizada entre o guard em Python
    # e o WHERE deste UPDATE.
    placeholders_bloqueados = ",".join("?" for _ in STATUS_CANCELAMENTO_BLOQUEADO)
    claim = conn.execute(
        f"""
        UPDATE pedidos
        SET status='Cancelado'
        WHERE id=?
          AND lower(COALESCE(status,'')) NOT LIKE 'cancel%'
          AND COALESCE(status,'') NOT IN ({placeholders_bloqueados})
        """,
        (venda_id, *STATUS_CANCELAMENTO_BLOQUEADO),
    )
    if claim.rowcount == 0:
        status_atual = conn.execute("SELECT status FROM pedidos WHERE id=?", (venda_id,)).fetchone()["status"]
        status_atual = str(status_atual or "")
        if status_atual.lower().startswith("cancel"):
            return {"ok": True, "venda_id": venda_id, "status": "Cancelado", "estoque_reposto_agora": False, "ja_cancelado": True}
        raise HTTPException(
            status_code=409,
            detail=f"Pedido em '{status_atual}' não pode ser cancelado por esta rota; requer conciliação administrativa.",
        )

    estoque_reposto = repor_estoque_cancelamento(conn, venda_id, usuario, agora)
    motivo = _sanitizar_motivo_cancelamento(observacao) or "Cancelado"
    # Situação comercial (Parte 6): sempre separada da financeira, mas um
    # pedido cancelado nunca deve continuar aparecendo como "novo"/"em
    # preparação" no painel -- best-effort (não bloqueia o cancelamento se a
    # coluna ainda não existir em um banco muito antigo sem migração).
    conn.execute("UPDATE pedidos SET status_pedido='cancelado' WHERE id=?", (venda_id,))
    # Cancelar um pedido que já tinha pagamento confirmado não apaga nem
    # estorna o pagamento (fora de escopo — ver "fluxo de estorno
    # financeiro" nas exclusões deste PR); fica só marcado aqui para que a
    # auditoria explique por que um pedido "Cancelado" pode ter um
    # pagamento "Confirmado" associado (consultável via GET /api/pagamentos)
    # — o status por si só não distingue isso, e resolver essa ambiguidade
    # de exibição/estorno automático é uma pendência de UX/financeiro fora
    # do escopo deste PR.
    cancelado_apos_pagamento = status_antes in STATUS_PEDIDO_CONCLUIDOS
    conn.execute(
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
        (venda_id, "Cancelado", usuario or "Admin", motivo, agora),
    )
    registrar_auditoria(
        conn, "pedido", venda_id, "cancelar", usuario,
        antes={"status": status_antes},
        depois={
            "status": "Cancelado",
            "estoque_reposto": estoque_reposto,
            "motivo": motivo,
            "cancelado_apos_pagamento": cancelado_apos_pagamento,
        },
    )
    return {"ok": True, "venda_id": venda_id, "status": "Cancelado", "estoque_reposto_agora": estoque_reposto, "ja_cancelado": False}


@router.get("/pedidos")
def listar_pedidos(status: str = "", limite: int = Query(100, ge=1, le=500), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    with conectar() as conn:
        expirar_pedidos_pendentes(conn)
        if status:
            rows = conn.execute(
                """
                SELECT id, cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem, observacao_pedido, estoque_baixado, estoque_baixado_em,
                       estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente,
                       visualizado_admin_em, visualizado_admin_por, comprovante_enviado_em,
                       expirado_em, payment_provider, provider_payment_id,
                       email, forma_recebimento, endereco_cep, endereco_rua, endereco_numero,
                       endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf, frete,
                       payment_type_id, payment_method_id, parcelas, status_detail_sanitizado,
                       data_aprovacao, status_pedido, codigo_rastreio
                FROM pedidos
                WHERE COALESCE(status,'')=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (status, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem, observacao_pedido, estoque_baixado, estoque_baixado_em,
                       estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente,
                       visualizado_admin_em, visualizado_admin_por, comprovante_enviado_em,
                       expirado_em, payment_provider, provider_payment_id,
                       email, forma_recebimento, endereco_cep, endereco_rua, endereco_numero,
                       endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf, frete,
                       payment_type_id, payment_method_id, parcelas, status_detail_sanitizado,
                       data_aprovacao, status_pedido, codigo_rastreio
                FROM pedidos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return [venda_para_pedido(conn, row) for row in rows]


@router.get("/pedidos/status-log")
def listar_status_pedidos(limite: int = 100, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    limite = max(1, min(limite, 500))
    with conectar() as conn:
        rows = conn.execute(
            """
            SELECT l.id, l.venda_id, v.cliente, v.total_final, l.status, l.usuario, l.observacao, l.data_hora
            FROM pedido_status_log l
            LEFT JOIN pedidos v ON v.id = l.venda_id
            ORDER BY l.id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/pedidos/{venda_id}")
def obter_pedido(venda_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    with conectar() as conn:
        expirar_pedidos_pendentes(conn)
        venda = conn.execute(
            """
            SELECT id, cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                   forma_pagamento, vendedor, status, data_iso, dia_operacional,
                   origem, observacao_pedido, estoque_baixado, estoque_baixado_em,
                   estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente,
                       visualizado_admin_em, visualizado_admin_por, comprovante_enviado_em,
                       expirado_em, payment_provider, provider_payment_id,
                       email, forma_recebimento, endereco_cep, endereco_rua, endereco_numero,
                       endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf, frete,
                       payment_type_id, payment_method_id, parcelas, status_detail_sanitizado,
                       data_aprovacao, status_pedido, codigo_rastreio
            FROM pedidos
            WHERE id=?
            """,
            (venda_id,),
        ).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        return venda_para_pedido(conn, venda)


def _escape_html(valor) -> str:
    return (
        str(valor if valor is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _chave_api_valida(chave_recebida: str | None) -> bool:
    chaves_validas = [
        chave
        for chave in (os.environ.get("MISTICA_SITE_API_KEY", "").strip(), os.environ.get("MISTICA_SYNC_KEY", "").strip())
        if chave
    ]
    return bool(chave_recebida) and any(secrets.compare_digest(str(chave_recebida), chave) for chave in chaves_validas)


def _acesso_admin_valido(mistica_painel_sessao: str | None, x_mistica_api_key: str | None) -> bool:
    """Sessão administrativa do painel (cookie) ou X-Mistica-Api-Key válida
    liberam o acesso ao pedido sem precisar do pix_txid."""
    if validar_sessao(mistica_painel_sessao):
        return True
    return _chave_api_valida(x_mistica_api_key)


ACESSO_NEGADO_PEDIDO = "Acesso negado. Informe o código do pedido (txid) para consultar este pedido."


def _exigir_acesso_pedido(venda, txid: str | None, admin: bool):
    """Só libera o acesso público (sem sessão/chave de API) a um pedido se o
    pix_txid enviado bater com o do pedido. Quando o acesso é negado, a
    resposta é sempre o mesmo 403 genérico — inclusive quando o pedido não
    existe — para que o ID do pedido sozinho não sirva para varrer/enumerar
    pedidos alheios (o 404 só é revelado a quem já provou ter acesso)."""
    if admin:
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        return
    if not venda or not venda["pix_txid"] or not txid or not secrets.compare_digest(str(txid), str(venda["pix_txid"])):
        raise HTTPException(status_code=403, detail=ACESSO_NEGADO_PEDIDO)


@router.get("/pedidos/{venda_id}/recibo")
def recibo_pedido(
    venda_id: int,
    txid: str | None = None,
    x_mistica_api_key: str | None = Header(default=None),
    mistica_painel_sessao: str | None = Cookie(default=None),
):
    """Recibo simples e imprimível do pedido, gerado a partir dos dados
    persistidos (nunca de dados locais do navegador). O id do pedido sozinho
    não dá acesso: é preciso o pix_txid do próprio pedido (devolvido apenas na
    criação/no link de acompanhamento do cliente), a sessão administrativa do
    painel ou a chave da API — sem isso, qualquer pessoa poderia varrer ids
    sequenciais e coletar nome/telefone/itens de outros clientes."""
    admin = _acesso_admin_valido(mistica_painel_sessao, x_mistica_api_key)
    with conectar() as conn:
        venda = conn.execute(
            """
            SELECT id, cliente, telefone, data_venda, subtotal, desconto, taxa, frete, total_final,
                   forma_pagamento, vendedor, status, origem, observacao_pedido, pix_txid,
                   forma_recebimento, endereco_cep, endereco_rua, endereco_numero,
                   endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf
            FROM pedidos
            WHERE id=?
            """,
            (venda_id,),
        ).fetchone()
        _exigir_acesso_pedido(venda, txid, admin)
        itens = conn.execute(
            "SELECT nome_p, quantidade, valor_unitario, valor_total FROM pedidos_itens WHERE pedido_id=? ORDER BY id ASC",
            (venda_id,),
        ).fetchall()
        pagamentos = conn.execute(
            "SELECT forma, valor, status, data_hora FROM pagamentos WHERE venda_id=? ORDER BY id DESC",
            (venda_id,),
        ).fetchall()

    linhas_itens = "".join(
        f"<tr><td>{_escape_html(item['nome_p'])}</td><td>{int(item['quantidade'] or 0)}</td>"
        f"<td>R$ {float(item['valor_unitario'] or 0):.2f}</td><td>R$ {float(item['valor_total'] or 0):.2f}</td></tr>"
        for item in itens
    )
    linhas_pagamentos = "".join(
        f"<li>{_escape_html(pagamento['forma'])} — R$ {float(pagamento['valor'] or 0):.2f} — {_escape_html(pagamento['status'])} ({_escape_html(pagamento['data_hora'])})</li>"
        for pagamento in pagamentos
    ) or "<li>Nenhum pagamento registrado ainda.</li>"

    forma_recebimento = venda["forma_recebimento"]
    if forma_recebimento == "retirada":
        linha_recebimento = f"<strong>Retirada:</strong> {_escape_html(ENDERECO_LOJA)}"
        instrucao = (
            f"Você será avisado quando o pedido estiver pronto para retirada na {_escape_html(ENDERECO_LOJA)}."
        )
    elif forma_recebimento == "entrega":
        endereco = ", ".join(
            _escape_html(parte)
            for parte in [
                f"{venda['endereco_rua'] or ''}, {venda['endereco_numero'] or ''}".strip(", "),
                venda["endereco_complemento"],
                venda["endereco_bairro"],
                f"{venda['endereco_cidade'] or ''}/{venda['endereco_uf'] or ''}".strip("/"),
                venda["endereco_cep"],
            ]
            if parte
        )
        linha_recebimento = f"<strong>Entrega:</strong> {endereco or 'endereço não informado'}"
        instrucao = (
            f"Seu pedido será preparado para envio após a confirmação do pagamento. "
            f"O prazo estimado é de {PRAZO_ENTREGA_DIAS_UTEIS}."
        )
    else:
        linha_recebimento = "<strong>Recebimento:</strong> Forma de recebimento não definida"
        instrucao = ""

    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Recibo do pedido #{venda_id}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:480px;margin:24px auto;color:#222}}
h1{{font-size:18px}} table{{width:100%;border-collapse:collapse;margin:12px 0}}
td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left;font-size:13px}}
.total{{font-weight:bold;font-size:16px;margin-top:8px}}
</style></head><body>
<h1>Mística Presentes — Recibo do pedido #{venda_id}</h1>
<p><strong>Cliente:</strong> {_escape_html(venda['cliente'])}<br>
<strong>Telefone:</strong> {_escape_html(venda['telefone']) or '—'}<br>
<strong>Data:</strong> {_escape_html(venda['data_venda'])}<br>
<strong>Status:</strong> {_escape_html(venda['status'])}<br>
<strong>Origem:</strong> {_escape_html(venda['origem'])}<br>
{linha_recebimento}</p>
<table><thead><tr><th>Item</th><th>Qtd</th><th>Valor unit.</th><th>Total</th></tr></thead>
<tbody>{linhas_itens}</tbody></table>
<p>Subtotal: R$ {float(venda['subtotal'] or 0):.2f}<br>
Desconto: R$ {float(venda['desconto'] or 0):.2f}<br>
Frete: R$ {float(venda['frete'] or 0):.2f}</p>
<p class="total">Total do pedido: R$ {float(venda['total_final'] or 0):.2f}</p>
<p><strong>Pagamentos:</strong></p><ul>{linhas_pagamentos}</ul>
{f'<p>{_escape_html(instrucao)}</p>' if instrucao else ''}
<p><button onclick="window.print()">Imprimir</button></p>
</body></html>"""
    return HTMLResponse(content=html)


@router.get("/pedidos/{venda_id}/status")
def historico_status_pedido(
    venda_id: int,
    txid: str | None = None,
    x_mistica_api_key: str | None = Header(default=None),
    mistica_painel_sessao: str | None = Cookie(default=None),
):
    """Acompanhamento público do pedido: exige o pix_txid do próprio pedido
    (devolvido só na criação/no link do cliente) além do ID, para que IDs
    sequenciais não sirvam para varrer o status e o histórico de pedidos
    alheios. Sessão administrativa ou X-Mistica-Api-Key seguem liberadas."""
    admin = _acesso_admin_valido(mistica_painel_sessao, x_mistica_api_key)
    with conectar() as conn:
        venda = conn.execute(
            """
            SELECT id, status, estoque_baixado, estoque_baixado_em, pix_txid,
                   forma_recebimento, endereco_cep, endereco_rua, endereco_numero,
                   endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf,
                   frete, total_final
              FROM pedidos WHERE id=?
            """,
            (venda_id,),
        ).fetchone()
        _exigir_acesso_pedido(venda, txid, admin)
        historico = conn.execute(
            """
            SELECT id, venda_id, status, usuario, observacao, data_hora
            FROM pedido_status_log
            WHERE venda_id=?
            ORDER BY id DESC
            """,
            (venda_id,),
        ).fetchall()

    forma_recebimento = venda["forma_recebimento"]
    resposta = {
        "ok": True,
        "venda_id": venda_id,
        "status_atual": venda["status"],
        "estoque_baixado": bool(venda["estoque_baixado"]),
        "estoque_baixado_em": venda["estoque_baixado_em"],
        "historico": [dict(row) for row in historico],
        "forma_recebimento": forma_recebimento,
        "frete": float(venda["frete"] or 0),
        "total_final": float(venda["total_final"] or 0),
    }
    if forma_recebimento == "retirada":
        resposta["endereco_loja"] = ENDERECO_LOJA
        resposta["instrucao_recebimento"] = (
            f"Você será avisado quando o pedido estiver pronto para retirada na {ENDERECO_LOJA}."
        )
    elif forma_recebimento == "entrega":
        resposta["endereco_entrega"] = {
            "cep": venda["endereco_cep"],
            "rua": venda["endereco_rua"],
            "numero": venda["endereco_numero"],
            "complemento": venda["endereco_complemento"],
            "bairro": venda["endereco_bairro"],
            "cidade": venda["endereco_cidade"],
            "uf": venda["endereco_uf"],
        }
        resposta["prazo_entrega_dias_uteis"] = PRAZO_ENTREGA_DIAS_UTEIS
        resposta["instrucao_recebimento"] = (
            f"Seu pedido será preparado para envio após a confirmação do pagamento. "
            f"O prazo estimado é de {PRAZO_ENTREGA_DIAS_UTEIS}."
        )
    return resposta


@router.post("/pedidos/{venda_id}/status", dependencies=[Depends(limitar_status_pedido)])
def atualizar_status_pedido(venda_id: int, payload: PedidoStatusIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = normalizar_status(payload.status)

    agora = datetime.now().isoformat(timespec="seconds")
    estoque_baixado_agora = False
    with conectar() as conn:
        venda = conn.execute("SELECT id FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        if status == "Cancelado":
            retorno = cancelar_com_reposicao(conn, venda_id, payload.usuario or "Admin", payload.observacao, agora)
            conn.commit()
            return {**retorno, "data_hora": agora}

        bloquear_avanco_financeiro_sem_conciliacao(conn, venda_id, status)

        if status in STATUS_BAIXA_ESTOQUE:
            estoque_baixado_agora = baixar_estoque_do_pedido(conn, venda_id, payload.usuario or "Admin", agora)

        conn.execute("UPDATE pedidos SET status=? WHERE id=?", (status, venda_id))
        observacao = payload.observacao or ""
        if estoque_baixado_agora:
            observacao = (observacao + " | " if observacao else "") + "Estoque baixado automaticamente"
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, status, payload.usuario or "Admin", observacao, agora),
        )
        conn.commit()

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status,
        "estoque_baixado_agora": estoque_baixado_agora,
        "data_hora": agora,
    }


@router.post("/pedidos/{venda_id}/baixar-estoque")
def baixar_estoque_manual(venda_id: int, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        baixado = baixar_estoque_do_pedido(conn, venda_id, "Admin", agora, "Baixa manual pelo painel")
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "estoque_baixado_agora": baixado, "data_hora": agora}


@router.post("/pedidos/{venda_id}/observacao")
def atualizar_observacao_pedido(venda_id: int, payload: PedidoObservacaoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        venda = conn.execute("SELECT id, status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        conn.execute("UPDATE pedidos SET observacao_pedido=? WHERE id=?", (payload.observacao or "", venda_id))
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, venda["status"], payload.usuario or "Admin", "Observação atualizada", agora),
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "observacao": payload.observacao, "data_hora": agora}


@router.delete("/pedidos/{venda_id}", dependencies=[Depends(limitar_cancelar_pedido)])
def cancelar_pedido(venda_id: int, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        retorno = cancelar_com_reposicao(conn, venda_id, "Admin", "Pedido cancelado pelo painel", agora)
        conn.commit()
    return {**retorno, "data_hora": agora}

try:
    from backend.order_api_guard_inner_routes import router as order_api_guard_inner_router
    router.include_router(order_api_guard_inner_router)
except Exception as exc:
    logger.warning("rotas seguras de pedido não carregadas", extra={"evento": "startup_aviso", "erro": str(exc)})
