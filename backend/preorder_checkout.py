from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, Request

from backend.audit import registrar_auditoria
from backend.campaign_routes import buscar_cupom_ativo, calcular_desconto_cupom
from backend.database import conectar
from backend.frete import PRAZO_ENTREGA_DIAS_UTEIS, calcular_frete
from backend.idempotency import (
    concluir_chave_idempotente,
    liberar_chave_idempotente,
    reivindicar_chave_idempotente,
)
from backend.order_status_routes import MINUTOS_EXPIRACAO_PEDIDO_PENDENTE, TIPO_ITEM_SOB_ENCOMENDA
from backend.pix import gerar_pix_do_pedido
from backend.product_commercial_rules import garantir_colunas_comerciais
from backend.site_stock_routes import (
    VendaSiteIn,
    payload_idempotencia_venda,
    registrar_venda_site,
    validar_site_api_key,
)


def _centavos(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _buscar_produto(conn, item):
    if item.produto_id:
        row = conn.execute(
            """
            SELECT id, codigo_p, nome, quantidade, preco, custo,
                   COALESCE(ativo,1) AS ativo,
                   COALESCE(sob_encomenda,0) AS sob_encomenda,
                   COALESCE(limite_encomenda,10) AS limite_encomenda
              FROM produtos
             WHERE id=? AND COALESCE(ativo,1)=1
            """,
            (item.produto_id,),
        ).fetchone()
        if row:
            return row
    if item.codigo_p:
        return conn.execute(
            """
            SELECT id, codigo_p, nome, quantidade, preco, custo,
                   COALESCE(ativo,1) AS ativo,
                   COALESCE(sob_encomenda,0) AS sob_encomenda,
                   COALESCE(limite_encomenda,10) AS limite_encomenda
              FROM produtos
             WHERE codigo_p=? AND COALESCE(ativo,1)=1
            """,
            (item.codigo_p,),
        ).fetchone()
    return None


def registrar_checkout_publico(
    venda: VendaSiteIn,
    request: Request,
    chave_api: str | None,
    idempotency_key: str | None = None,
):
    validar_site_api_key(chave_api)
    if not venda.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado.")

    with conectar() as conn:
        garantir_colunas_comerciais(conn)
        validados = []
        for item in venda.itens:
            produto = _buscar_produto(conn, item)
            if not produto:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produto não encontrado ou inativo: {item.codigo_p or item.nome_p or item.produto_id}",
                )
            validados.append((item, produto))

        flags = {bool(produto["sob_encomenda"]) for _, produto in validados}

    if flags == {False}:
        return registrar_venda_site(venda, request, chave_api, idempotency_key)

    if len(flags) > 1:
        raise HTTPException(
            status_code=400,
            detail="Produtos disponíveis em estoque e produtos sob encomenda devem ser finalizados em pedidos separados.",
        )

    if not bool(getattr(venda, "ciente_sob_encomenda", False)):
        raise HTTPException(
            status_code=400,
            detail="Confirme que está ciente das condições do produto sob encomenda.",
        )

    resposta_existente = reivindicar_chave_idempotente(
        conectar, "criar_pedido", idempotency_key, payload_idempotencia_venda(venda)
    )
    if resposta_existente is not None:
        return resposta_existente

    agora = datetime.now()
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    dia_operacional = venda.dia_operacional or agora.strftime("%Y-%m-%d")
    expira_em = (agora + timedelta(minutes=MINUTOS_EXPIRACAO_PEDIDO_PENDENTE)).isoformat(timespec="seconds")
    telefone = "".join(ch for ch in str(venda.telefone or "") if ch.isdigit() or ch in "+ ").strip()[:32]

    try:
        with conectar() as conn:
            garantir_colunas_comerciais(conn)
            itens_calculados = []
            subtotal = Decimal("0.00")
            for item in venda.itens:
                produto = _buscar_produto(conn, item)
                if not produto or not bool(produto["sob_encomenda"]):
                    raise HTTPException(status_code=409, detail="O catálogo mudou. Atualize a página e tente novamente.")
                limite = int(produto["limite_encomenda"] or 10)
                if item.quantidade > limite:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Quantidade máxima sob encomenda para {produto['nome']}: {limite}.",
                    )
                preco = _centavos(produto["preco"])
                custo = _centavos(produto["custo"])
                total_item = _centavos(preco * item.quantidade)
                subtotal += total_item
                itens_calculados.append((item, produto, preco, custo, total_item))

            subtotal = _centavos(subtotal)
            codigo_cupom = str(venda.cupom or "").strip().upper()
            desconto = 0.0
            cupom_info = None
            if codigo_cupom:
                campanha = buscar_cupom_ativo(conn, codigo_cupom)
                if not campanha:
                    raise HTTPException(status_code=400, detail="Cupom inválido ou expirado.")
                cupom_info = calcular_desconto_cupom(campanha, float(subtotal))
                desconto = float(cupom_info["desconto"])

            # Fase 3 — entrega ou retirada (mesma regra de site_stock_routes.py::
            # registrar_venda_site, aplicada aqui porque o caminho sob encomenda
            # tem seu próprio INSERT em pedidos): endereço só é gravado quando a
            # forma é "entrega"; para "retirada" é sempre ignorado/NULL.
            forma_recebimento = venda.forma_recebimento
            frete_gratis = bool(cupom_info["frete_gratis"]) if cupom_info else False
            if forma_recebimento == "entrega":
                endereco_cep = venda.endereco_cep
                endereco_rua = (venda.endereco_rua or "").strip()[:200] or None
                endereco_numero = (venda.endereco_numero or "").strip()[:20] or None
                endereco_complemento = (venda.endereco_complemento or "").strip()[:120] or None
                endereco_bairro = (venda.endereco_bairro or "").strip()[:120] or None
                endereco_cidade = (venda.endereco_cidade or "").strip()[:120] or None
                endereco_uf = venda.endereco_uf
            else:
                endereco_cep = endereco_rua = endereco_numero = None
                endereco_complemento = endereco_bairro = endereco_cidade = endereco_uf = None

            frete = calcular_frete(forma_recebimento, endereco_cidade, endereco_uf, frete_gratis=frete_gratis)
            total_final = float(_centavos(_centavos(subtotal) - _centavos(desconto) + _centavos(frete)))
            email = (venda.email or "").strip()[:180] or None

            cur = conn.execute(
                """
                INSERT INTO pedidos (
                    cliente, telefone, email, data_venda, subtotal, desconto, taxa, frete, total_final,
                    forma_pagamento, vendedor, status, data_iso, dia_operacional,
                    origem, expira_em, cupom, estoque_baixado, estoque_reservado, forma_recebimento,
                    endereco_cep, endereco_rua, endereco_numero, endereco_complemento,
                    endereco_bairro, endereco_cidade, endereco_uf
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    venda.cliente,
                    telefone or None,
                    email,
                    data_venda,
                    float(subtotal),
                    desconto,
                    0.0,
                    frete,
                    total_final,
                    "Pix site/celular",
                    "Site/Celular",
                    "Aguardando pagamento",
                    data_iso,
                    dia_operacional,
                    "site",
                    expira_em,
                    codigo_cupom or None,
                    0,
                    0,
                    forma_recebimento,
                    endereco_cep,
                    endereco_rua,
                    endereco_numero,
                    endereco_complemento,
                    endereco_bairro,
                    endereco_cidade,
                    endereco_uf,
                ),
            )
            pedido_id = int(cur.lastrowid)

            for item, produto, preco, custo, total_item in itens_calculados:
                conn.execute(
                    """
                    INSERT INTO pedidos_itens
                    (pedido_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total, tipo_item)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        pedido_id,
                        produto["codigo_p"],
                        produto["nome"],
                        item.quantidade,
                        float(custo),
                        float(preco),
                        float(total_item),
                        TIPO_ITEM_SOB_ENCOMENDA,
                    ),
                )

            pix = gerar_pix_do_pedido(pedido_id, total_final)
            if pix:
                conn.execute(
                    "UPDATE pedidos SET pix_txid=?, pix_copia_cola=? WHERE id=?",
                    (pix["txid"], pix["copia_cola"], pedido_id),
                )

            resposta = {
                "ok": True,
                "id": pedido_id,
                "status": "criado",
                "subtotal": float(subtotal),
                "desconto": desconto,
                "cupom": codigo_cupom or None,
                "frete_gratis": frete_gratis,
                "frete": frete,
                "forma_recebimento": forma_recebimento,
                "prazo_entrega_dias_uteis": PRAZO_ENTREGA_DIAS_UTEIS if forma_recebimento == "entrega" else None,
                "total_final": total_final,
                "estoque_baixado": False,
                "estoque_reservado": False,
                "sob_encomenda": True,
                "expira_em": expira_em,
                "pix_txid": pix["txid"] if pix else None,
                "pix_copia_cola": pix["copia_cola"] if pix else None,
                "pix": pix["info"] if pix else None,
            }
            registrar_auditoria(
                conn,
                "pedido",
                pedido_id,
                "criar_sob_encomenda",
                "Site/Celular",
                depois={"total_final": total_final, "itens": len(itens_calculados), "estoque_baixado": False},
            )
            concluir_chave_idempotente(conn, "criar_pedido", idempotency_key, resposta)
            conn.commit()
    except Exception:
        liberar_chave_idempotente(conectar, "criar_pedido", idempotency_key)
        raise

    return resposta
