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
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_sessao_ou_chave_api, validar_sessao
from backend.rate_limit import limitar_requisicoes

logger = get_logger(__name__)

limitar_status_pedido = limitar_requisicoes("status_pedido", limite=20, janela_segundos=60)
limitar_cancelar_pedido = limitar_requisicoes("cancelar_pedido", limite=20, janela_segundos=60)

router = APIRouter(prefix="/api", tags=["pedidos-status"])

# Classificação persistida de cada item do pedido (pedidos_itens.tipo_item —
# ver database/migrations.py). Decidida no momento da criação do pedido e
# nunca mais reavaliada contra o catálogo depois: um produto sob encomenda tem
# estoque físico zero por definição, então a confirmação de pagamento nunca
# pode tentar baixar/repor estoque físico de um item classificado como
# TIPO_ITEM_SOB_ENCOMENDA, nem tratar como físico um item cuja classificação
# não seja reconhecida (ver baixar_estoque_do_pedido).
TIPO_ITEM_FISICO = "fisico"
TIPO_ITEM_SOB_ENCOMENDA = "sob_encomenda"
TIPOS_ITEM_VALIDOS = {TIPO_ITEM_FISICO, TIPO_ITEM_SOB_ENCOMENDA}

STATUS_PEDIDO_AGUARDANDO_ENCOMENDA = "Aguardando encomenda"

STATUS_PEDIDO = {
    "Aguardando pagamento",
    "Pagamento divergente",
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
            "UPDATE pedidos SET status='Cancelado' WHERE id=? AND status IN ('Aguardando pagamento', 'Pagamento divergente')",
            (venda["id"],),
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
    """Lê pedidos_itens.tipo_item sem assumir nada: só os dois valores
    conhecidos (TIPO_ITEM_FISICO/TIPO_ITEM_SOB_ENCOMENDA) são aceitos. Um
    valor vazio/nulo ou desconhecido (dado corrompido, coluna alterada por
    fora do fluxo normal) não é tratado como física por padrão — ver
    baixar_estoque_do_pedido/repor_estoque_cancelamento, que bloqueiam em vez
    de adivinhar."""
    return str(item["tipo_item"] or "").strip()


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
    venda = conn.execute("SELECT id, estoque_baixado, estoque_reposto_cancelamento FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if int(venda["estoque_baixado"] or 0) != 1:
        return False
    if int(venda["estoque_reposto_cancelamento"] or 0) == 1:
        return False

    itens = conn.execute("SELECT id, codigo_p, nome_p, quantidade, tipo_item FROM pedidos_itens WHERE pedido_id=? ORDER BY id ASC", (venda_id,)).fetchall()
    total = 0
    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        if _tipo_item_normalizado(item) == TIPO_ITEM_SOB_ENCOMENDA:
            # Sob encomenda nunca teve estoque físico baixado (ver
            # baixar_estoque_do_pedido): repor criaria saldo positivo
            # fictício. Itens com classificação ausente/desconhecida também
            # não são repostos aqui pelo mesmo motivo — nunca assumimos
            # "físico" por padrão para um dado ambíguo.
            continue
        if _tipo_item_normalizado(item) not in TIPOS_ITEM_VALIDOS:
            continue
        produto = buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado para reposição: {item['nome_p'] or item['codigo_p']}")
        conn.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (quantidade, produto["id"]))
        total += quantidade

    conn.execute("UPDATE pedidos SET estoque_reposto_cancelamento=1, estoque_reposto_em=? WHERE id=?", (agora, venda_id))
    conn.execute(
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
        (venda_id, "Estoque reposto", usuario or "Admin", f"Reposição automática: {total} item(ns)", agora),
    )
    registrar_auditoria(conn, "estoque", venda_id, "reposicao_cancelamento", usuario, depois={"total_itens": total})
    return total > 0


def cancelar_com_reposicao(conn, venda_id: int, usuario: str, observacao: str | None, agora: str):
    venda = conn.execute("SELECT id, status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ja_cancelado = str(venda["status"] or "").lower().startswith("cancel")
    estoque_reposto = False if ja_cancelado else repor_estoque_cancelamento(conn, venda_id, usuario, agora)
    conn.execute("UPDATE pedidos SET status='Cancelado' WHERE id=?", (venda_id,))
    conn.execute(
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
        (venda_id, "Cancelado", usuario or "Admin", observacao or ("Cancelado" if not ja_cancelado else "Já estava cancelado; estoque não reposto novamente"), agora),
    )
    registrar_auditoria(conn, "pedido", venda_id, "cancelar", usuario, antes={"status": venda["status"]}, depois={"status": "Cancelado", "estoque_reposto": estoque_reposto})
    return {"ok": True, "venda_id": venda_id, "status": "Cancelado", "estoque_reposto_agora": estoque_reposto, "ja_cancelado": ja_cancelado}


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
                       estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente
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
                       estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente
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
                   estoque_reservado, expira_em, pix_txid, pix_copia_cola, confirmado_automaticamente
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
            SELECT id, cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                   forma_pagamento, vendedor, status, origem, observacao_pedido, pix_txid
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
<strong>Origem:</strong> {_escape_html(venda['origem'])}</p>
<table><thead><tr><th>Item</th><th>Qtd</th><th>Valor unit.</th><th>Total</th></tr></thead>
<tbody>{linhas_itens}</tbody></table>
<p class="total">Total do pedido: R$ {float(venda['total_final'] or 0):.2f}</p>
<p><strong>Pagamentos:</strong></p><ul>{linhas_pagamentos}</ul>
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
        venda = conn.execute("SELECT id, status, estoque_baixado, estoque_baixado_em, pix_txid FROM pedidos WHERE id=?", (venda_id,)).fetchone()
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
    return {
        "ok": True,
        "venda_id": venda_id,
        "status_atual": venda["status"],
        "estoque_baixado": bool(venda["estoque_baixado"]),
        "estoque_baixado_em": venda["estoque_baixado_em"],
        "historico": [dict(row) for row in historico],
    }


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
