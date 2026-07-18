"""Notificação administrativa de novos pedidos Pix + fluxo de comprovante
pelo WhatsApp (ver backend/pedido_notificacao_routes.py).

Cobre: status inicial do pedido, listagem/contador no painel, idempotência
e escopo do endpoint público de comprovante do cliente, rejeição de
transição inválida, exigência de administrador autenticado para confirmar
pagamento/cancelar pelo painel, e ausência de dado sensível no audit_log.
"""

import importlib
import json
import os
import uuid

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key-pedido-pix-notificacao"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    n = uuid.uuid4().int
    return f"198.{(n >> 16) % 256}.{(n >> 8) % 256}.{n % 256}"


def _headers(**extra):
    headers = {**HEADERS, "X-Forwarded-For": ip_unico()}
    headers.update(extra)
    return headers


def criar_produto(preco: float = 39.9, quantidade: int = 20) -> dict:
    codigo = f"PIXNOTIF-{uuid.uuid4().hex[:10]}"
    resposta = client.post(
        "/api/produtos",
        headers=_headers(),
        json={
            "nome": "Produto teste notificação Pix",
            "codigo_p": codigo,
            "preco": preco,
            "quantidade": quantidade,
            "categoria": "Testes",
        },
    )
    assert resposta.status_code == 200, resposta.text
    return {"id": resposta.json()["id"], "codigo_p": codigo.upper(), "preco": preco}


def criar_pedido_pix(cliente: str = "Cliente Teste Pix", telefone: str = "49988887777") -> dict:
    """Cria um pedido pelo checkout público real (mesmo caminho do site), com
    Pix gerado de verdade — devolve o pedido completo (com pix_txid) já
    persistido, sem tocar em nenhuma lógica de geração de QR/EMV/CRC16/chave."""
    produto = criar_produto()
    resposta = client.post(
        "/api/checkout/pedidos",
        json={
            "cliente": cliente,
            "telefone": telefone,
            "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": 1}],
        },
        headers=_headers(),
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["pix_txid"], "checkout deveria gerar pix_txid"
    return dados


def criar_admin_com_sessao(perfil: str = "adm") -> tuple[str, TestClient]:
    from config import hash_password_pbkdf2
    from backend.database import conectar

    login = f"admin-pix-notif-{uuid.uuid4().hex[:8]}"
    senha = "senha-forte-Teste123!"
    salt = "teste-pix-notif"
    senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
    with conectar() as conn:
        conn.execute(
            "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,1)",
            (login, login, senha_hash, salt, perfil),
        )
    sessao_client = TestClient(main.app)
    sessao_client.__enter__()
    resposta = sessao_client.post(
        "/api/auth/login",
        json={"login": login, "senha": senha},
        headers={"Origin": "http://localhost:3000", "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return login, sessao_client


# ---------------------------------------------------------------------------
# 1. Estado inicial do pedido
# ---------------------------------------------------------------------------


def test_pedido_criado_comeca_aguardando_pagamento():
    pedido = criar_pedido_pix()
    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS)
    assert consulta.status_code == 200
    assert consulta.json()["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 2. Painel administrativo lista o novo pedido / contador de não visualizados
# ---------------------------------------------------------------------------


def test_painel_lista_novo_pedido_e_conta_nao_visualizados():
    pedido = criar_pedido_pix()

    listagem = client.get("/api/pedidos/pix/pendentes", headers=HEADERS)
    assert listagem.status_code == 200
    corpo = listagem.json()
    ids = [p["id"] for p in corpo["pedidos"]]
    assert pedido["id"] in ids
    assert corpo["total_nao_visualizados"] >= 1

    marcado = client.post(f"/api/pedidos/{pedido['id']}/visualizar", headers=HEADERS)
    assert marcado.status_code == 200
    assert marcado.json()["ja_visualizado"] is False

    listagem2 = client.get("/api/pedidos/pix/pendentes", headers=HEADERS)
    pedido_atualizado = next(p for p in listagem2.json()["pedidos"] if p["id"] == pedido["id"])
    assert pedido_atualizado["visualizado_admin_em"]

    # Idempotente: visualizar de novo não é erro nem sobrescreve.
    marcado2 = client.post(f"/api/pedidos/{pedido['id']}/visualizar", headers=HEADERS)
    assert marcado2.status_code == 200
    assert marcado2.json()["ja_visualizado"] is True


def test_listar_pendentes_exige_autenticacao():
    resposta = client.get("/api/pedidos/pix/pendentes")
    assert resposta.status_code == 401


def test_pedido_aparece_no_painel_administrativo_imediatamente_apos_criado_sem_clicar_em_ja_paguei():
    """O painel administrativo (resumo em admin.html e painel completo em
    admin-pedidos-pix.html, ambos consumindo este mesmo endpoint) precisa
    saber de um pedido novo assim que ele é criado pelo checkout -- nunca
    apenas quando o cliente clica em "Já paguei"/abre o WhatsApp."""
    pedido = criar_pedido_pix()

    listagem = client.get("/api/pedidos/pix/pendentes", headers=HEADERS)
    assert listagem.status_code == 200
    corpo = listagem.json()
    encontrado = next((p for p in corpo["pedidos"] if p["id"] == pedido["id"]), None)
    assert encontrado is not None, "pedido recém-criado deveria aparecer no painel sem nenhuma ação do cliente"
    assert encontrado["status"] == "Aguardando pagamento"
    assert not encontrado["comprovante_enviado_em"]
    assert not encontrado["visualizado_admin_em"]


def test_listagem_pix_pendentes_nao_retorna_dados_sensiveis():
    """A listagem usada pelo resumo do painel principal e pelo painel
    completo nunca deve trafegar TXID, chaves ou tokens administrativos."""
    pedido = criar_pedido_pix()

    listagem = client.get("/api/pedidos/pix/pendentes", headers=HEADERS)
    assert listagem.status_code == 200
    corpo_bruto = listagem.text
    assert "pix_txid" not in corpo_bruto
    assert pedido["pix_txid"] not in corpo_bruto
    assert TEST_API_KEY not in corpo_bruto

    encontrado = next(p for p in listagem.json()["pedidos"] if p["id"] == pedido["id"])
    assert "pix_txid" not in encontrado
    assert "chave_pix" not in encontrado


# ---------------------------------------------------------------------------
# 3/4. Clique no WhatsApp não marca como pago; dados do pedido batem
# ---------------------------------------------------------------------------


def test_cliente_registra_comprovante_sem_marcar_como_pago():
    pedido = criar_pedido_pix()

    resposta = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "Comprovante enviado"
    assert corpo["ja_registrado"] is False

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Comprovante enviado"
    assert consulta["status"] != "Pagamento confirmado"

    # Os dados que a mensagem do WhatsApp usa (id e valor) continuam os
    # mesmos persistidos no pedido, nunca alterados por esta ação.
    assert consulta["id"] == pedido["id"]
    assert consulta["total_final"] == pedido["total_final"]


# ---------------------------------------------------------------------------
# 5. Cliente não altera pedido alheio
# ---------------------------------------------------------------------------


def test_cliente_nao_altera_pedido_alheio_sem_txid_correto():
    pedido = criar_pedido_pix()

    sem_txid = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={})
    assert sem_txid.status_code == 403

    txid_errado = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": "txid-de-outro-pedido"})
    assert txid_errado.status_code == 403

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 6. Ação duplicada é idempotente
# ---------------------------------------------------------------------------


def test_comprovante_cliente_e_idempotente():
    pedido = criar_pedido_pix()

    primeira = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})
    assert primeira.status_code == 200
    assert primeira.json()["ja_registrado"] is False
    carimbo_original = primeira.json()["comprovante_enviado_em"]

    segunda = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})
    assert segunda.status_code == 200
    assert segunda.json()["ja_registrado"] is True
    assert segunda.json()["comprovante_enviado_em"] == carimbo_original

    with main.conectar() as conn:
        total_logs = conn.execute(
            "SELECT COUNT(*) FROM pedido_status_log WHERE venda_id=? AND status='Comprovante enviado'",
            (pedido["id"],),
        ).fetchone()[0]
    assert total_logs == 1


# ---------------------------------------------------------------------------
# 7. Confirmação de pagamento pelo painel exige administrador autenticado
# ---------------------------------------------------------------------------


def test_confirmar_pagamento_painel_exige_sessao_admin():
    pedido = criar_pedido_pix()

    sem_auth = client.post(f"/api/pedidos/{pedido['id']}/confirmar-pagamento-painel", json={"valor": pedido["total_final"]})
    assert sem_auth.status_code == 401

    sem_auth_cancelar = client.post(f"/api/pedidos/{pedido['id']}/cancelar-painel")
    assert sem_auth_cancelar.status_code == 401

    _, sessao_admin = criar_admin_com_sessao()
    com_auth = sessao_admin.post(
        f"/api/pedidos/{pedido['id']}/confirmar-pagamento-painel",
        json={"valor": pedido["total_final"]},
        headers={"Origin": "http://localhost:3000"},
    )
    assert com_auth.status_code == 200, com_auth.text

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Pagamento confirmado"


# ---------------------------------------------------------------------------
# 8. Transição inválida é rejeitada
# ---------------------------------------------------------------------------


def test_marcar_comprovante_recebido_rejeita_status_incompativel():
    pedido = criar_pedido_pix()
    # Pedido ainda em "Aguardando pagamento": não passou por "Comprovante
    # enviado", então marcar como recebido deve ser rejeitado (409), nunca
    # aplicado "mais perto possível".
    resposta = client.post(f"/api/pedidos/{pedido['id']}/comprovante/recebido", headers=HEADERS, json={})
    assert resposta.status_code == 409

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 9. Dados sensíveis não aparecem em log/auditoria
# ---------------------------------------------------------------------------


def test_auditoria_comprovante_nao_expoe_telefone_nem_txid_completo():
    pedido = criar_pedido_pix(telefone="49999912345")
    client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})

    with main.conectar() as conn:
        linhas = conn.execute(
            "SELECT dados_antes, dados_depois FROM audit_log WHERE entidade='pedido' AND entidade_id=? AND acao='cliente_iniciou_envio_comprovante'",
            (str(pedido["id"]),),
        ).fetchall()
    assert linhas, "deveria existir um registro de auditoria para esta ação"
    for linha in linhas:
        bruto = json.dumps([linha["dados_antes"], linha["dados_depois"]])
        assert "49999912345" not in bruto
        assert pedido["pix_txid"] not in bruto


# ---------------------------------------------------------------------------
# 10. Pedido cancelado/expirado não reentra no fluxo financeiro por estas rotas
# ---------------------------------------------------------------------------


def test_pedido_cancelado_nao_aceita_comprovante_nem_acoes_administrativas():
    pedido = criar_pedido_pix()
    cancelado = client.delete(f"/api/pedidos/{pedido['id']}", headers=HEADERS)
    assert cancelado.status_code == 200
    assert cancelado.json()["status"] == "Cancelado"

    # Cliente tentando enviar comprovante de um pedido já cancelado: nunca
    # reabre nem muda o status, apenas devolve o estado atual.
    resposta = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "Cancelado"
    assert resposta.json()["ja_registrado"] is True

    # Admin tentando marcar comprovante recebido/rejeitar num pedido
    # cancelado: transição inválida, rejeitada com 409.
    recebido = client.post(f"/api/pedidos/{pedido['id']}/comprovante/recebido", headers=HEADERS, json={})
    assert recebido.status_code == 409
    rejeitado = client.post(f"/api/pedidos/{pedido['id']}/comprovante/rejeitar", headers=HEADERS, json={})
    assert rejeitado.status_code == 409

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Cancelado"


def test_pedido_expirado_nao_reentra_no_fluxo_por_clique_do_cliente():
    pedido = criar_pedido_pix()
    # Força o prazo de expiração para o passado diretamente no banco (mesma
    # técnica usada pelos testes já existentes de expiração automática) —
    # nunca chama a lógica de geração de Pix de novo.
    with main.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", ("2000-01-01T00:00:00", pedido["id"]))
        conn.commit()

    resposta = client.post(f"/api/pedidos/{pedido['id']}/comprovante", json={"txid": pedido["pix_txid"]})
    assert resposta.status_code == 200
    # expirar_pedidos_pendentes roda no início do endpoint: o pedido já virou
    # "Cancelado" antes da checagem de transição, então o clique do cliente
    # nunca reabre um pedido expirado.
    assert resposta.json()["status"] == "Cancelado"

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Cancelado"
    assert consulta["expirado_em"]


# ---------------------------------------------------------------------------
# 11. CSRF/Origin nas rotas do painel autenticadas por cookie
# ---------------------------------------------------------------------------


def test_confirmar_pagamento_painel_rejeita_origem_nao_permitida():
    pedido = criar_pedido_pix()
    _, sessao_admin = criar_admin_com_sessao()

    resposta = sessao_admin.post(
        f"/api/pedidos/{pedido['id']}/confirmar-pagamento-painel",
        json={"valor": pedido["total_final"]},
        headers={"Origin": "http://evil.example.com"},
    )
    assert resposta.status_code == 403

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Aguardando pagamento"


def test_cancelar_painel_rejeita_origem_nao_permitida():
    pedido = criar_pedido_pix()
    _, sessao_admin = criar_admin_com_sessao()

    resposta = sessao_admin.post(
        f"/api/pedidos/{pedido['id']}/cancelar-painel",
        headers={"Origin": "http://evil.example.com"},
    )
    assert resposta.status_code == 403

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 12. Confirmação e cancelamento repetidos pelo painel são idempotentes
# ---------------------------------------------------------------------------


def test_confirmacao_repetida_pelo_painel_nao_duplica_estoque():
    pedido = criar_pedido_pix()
    _, sessao_admin = criar_admin_com_sessao()
    origem = {"Origin": "http://localhost:3000"}

    primeira = sessao_admin.post(
        f"/api/pedidos/{pedido['id']}/confirmar-pagamento-painel",
        json={"valor": pedido["total_final"]},
        headers=origem,
    )
    assert primeira.status_code == 200, primeira.text

    with main.conectar() as conn:
        produto_id = conn.execute(
            "SELECT codigo_p FROM pedidos_itens WHERE pedido_id=? LIMIT 1", (pedido["id"],)
        ).fetchone()["codigo_p"]
        estoque_apos_primeira = conn.execute(
            "SELECT quantidade FROM produtos WHERE codigo_p=?", (produto_id,)
        ).fetchone()["quantidade"]

    segunda = sessao_admin.post(
        f"/api/pedidos/{pedido['id']}/confirmar-pagamento-painel",
        json={"valor": pedido["total_final"]},
        headers=origem,
    )
    assert segunda.status_code == 200, segunda.text

    with main.conectar() as conn:
        estoque_apos_segunda = conn.execute(
            "SELECT quantidade FROM produtos WHERE codigo_p=?", (produto_id,)
        ).fetchone()["quantidade"]
        pedido_final = conn.execute("SELECT status FROM pedidos WHERE id=?", (pedido["id"],)).fetchone()

    # Confirmar duas vezes o mesmo valor nunca baixa estoque duas vezes e o
    # pedido continua exatamente "Pagamento confirmado" (nunca avança para
    # outro status nem regride).
    assert estoque_apos_segunda == estoque_apos_primeira
    assert pedido_final["status"] == "Pagamento confirmado"


def test_cancelamento_repetido_pelo_painel_e_idempotente():
    pedido = criar_pedido_pix()
    _, sessao_admin = criar_admin_com_sessao()
    origem = {"Origin": "http://localhost:3000"}

    primeiro = sessao_admin.post(f"/api/pedidos/{pedido['id']}/cancelar-painel", headers=origem)
    assert primeiro.status_code == 200, primeiro.text
    assert primeiro.json()["status"] == "Cancelado"

    segundo = sessao_admin.post(f"/api/pedidos/{pedido['id']}/cancelar-painel", headers=origem)
    assert segundo.status_code == 200, segundo.text
    assert segundo.json()["status"] == "Cancelado"
    assert segundo.json()["ja_cancelado"] is True

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 13. Webhook de provedor futuro: nenhum provedor configurado
# ---------------------------------------------------------------------------


def test_webhook_provedor_nao_configurado_retorna_501_e_nao_confirma_pedido():
    pedido = criar_pedido_pix()

    resposta = client.post(
        f"/api/webhooks/pagamentos/mercadopago",
        json={"venda_id": pedido["id"], "status": "approved"},
    )
    assert resposta.status_code == 501

    # Nome de provedor arbitrário/desconhecido também nunca passa: não há
    # bypass possível só trocando o nome na URL.
    resposta_arbitraria = client.post(
        f"/api/webhooks/pagamentos/{uuid.uuid4().hex}",
        json={"venda_id": pedido["id"], "status": "approved"},
    )
    assert resposta_arbitraria.status_code == 501

    consulta = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert consulta["status"] == "Aguardando pagamento"
