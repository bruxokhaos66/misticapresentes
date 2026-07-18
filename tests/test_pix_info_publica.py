"""Testes da apresentação pública das informações do Pix na tela de
confirmação do pedido (fluxo /api/checkout/pedidos).

Antes desta correção, a tela mostrava textos genéricos fixos no JavaScript
("Gerada pelo servidor ao confirmar o pedido", "Confira o nome no Pix copia
e cola abaixo") em vez dos dados reais devolvidos pelo servidor. Estes
testes cobrem: o bloco público `pix` na resposta da API (chave mascarada,
recebedor, nome da loja, cidade) e a garantia de que a chave Pix completa
configurada em MISTICA_PIX_KEY nunca aparece na resposta da API nem é
logada.
"""

import importlib
import io
import logging
import os
import uuid

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key"
CHAVE_PIX_TESTE = "0f1e2d3c-4b5a-4968-8c9d-232e3d201d24"
RECEBEDOR_TESTE = "Natália Grunwald"
NOME_LOJA_TESTE = "Mística Presentes"
CIDADE_LOJA_TESTE = "Pinhalzinho-SC"

os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_PIX_KEY", CHAVE_PIX_TESTE)

main = importlib.import_module("backend.main")
from backend.pix import config_pix, mascarar_chave_pix  # noqa: E402

HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def codigo_unico() -> str:
    return f"PIXINFO-{uuid.uuid4().hex[:10]}"


def criar_produto() -> dict:
    with TestClient(main.app) as client:
        resposta = client.post(
            "/api/produtos",
            headers=HEADERS,
            json={
                "codigo_p": codigo_unico(),
                "nome": "Produto de teste apresentação Pix",
                "preco": 49.9,
                "custo": 12.0,
                "quantidade": 5,
            },
        )
        assert resposta.status_code == 200, resposta.text
        return {"id": resposta.json()["id"]}


def _criar_pedido_com_chave(chave: str, ip_final: int) -> tuple[dict, str]:
    """Cria um pedido de teste com a MISTICA_PIX_KEY temporariamente trocada
    para `chave`, capturando também os logs emitidos durante a chamada."""
    produto = criar_produto()
    anterior = os.environ.get("MISTICA_PIX_KEY")
    os.environ["MISTICA_PIX_KEY"] = chave

    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    nivel_anterior = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    try:
        with TestClient(main.app) as client:
            resposta = client.post(
                "/api/checkout/pedidos",
                json={
                    "cliente": "Cliente teste apresentação Pix",
                    "telefone": "11999999999",
                    "itens": [{"produto_id": produto["id"], "quantidade": 1}],
                },
                headers={"X-Forwarded-For": f"198.51.100.{ip_final}"},
            )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(nivel_anterior)
        if anterior is None:
            os.environ.pop("MISTICA_PIX_KEY", None)
        else:
            os.environ["MISTICA_PIX_KEY"] = anterior

    assert resposta.status_code == 200, resposta.text
    return resposta.json(), log_buffer.getvalue()


def test_resposta_traz_bloco_pix_publico_com_recebedor_e_nome_da_loja():
    dados, _ = _criar_pedido_com_chave(CHAVE_PIX_TESTE, 71)

    assert dados["pix"] is not None
    assert dados["pix"]["recebedor"]
    assert dados["pix"]["nome_loja"]
    assert dados["pix"]["copia_e_cola"] == dados["pix_copia_cola"]
    assert dados["pix"]["qr_code"] == dados["pix_copia_cola"]


def test_chave_pix_e_mascarada_na_resposta():
    dados, _ = _criar_pedido_com_chave(CHAVE_PIX_TESTE, 72)

    chave_mascarada = dados["pix"]["chave_mascarada"]
    assert chave_mascarada
    assert chave_mascarada != CHAVE_PIX_TESTE
    assert chave_mascarada.endswith(CHAVE_PIX_TESTE.split("-")[-1])
    assert "•" in chave_mascarada


def test_chave_pix_completa_nunca_aparece_na_resposta_da_api():
    dados, _ = _criar_pedido_com_chave(CHAVE_PIX_TESTE, 73)

    # A chave completa só pode existir embutida no próprio BR Code
    # (obrigatório para o pagamento funcionar — ver campo 26/01 do EMV),
    # nos três campos que carregam esse payload. Fora deles, ela nunca pode
    # aparecer isolada em nenhum outro campo da resposta.
    assert CHAVE_PIX_TESTE in dados["pix_copia_cola"]
    assert CHAVE_PIX_TESTE in dados["pix"]["copia_e_cola"]
    assert CHAVE_PIX_TESTE in dados["pix"]["qr_code"]

    campos_com_payload_emv = {"pix_copia_cola", "pix"}
    for campo, valor in dados.items():
        if campo in campos_com_payload_emv:
            continue
        assert CHAVE_PIX_TESTE not in str(valor), f"chave completa vazou no campo {campo}"
    for campo, valor in dados["pix"].items():
        if campo in ("copia_e_cola", "qr_code"):
            continue
        assert CHAVE_PIX_TESTE not in str(valor), f"chave completa vazou no campo pix.{campo}"


def test_chave_pix_completa_nunca_aparece_nos_logs():
    _, logs = _criar_pedido_com_chave(CHAVE_PIX_TESTE, 74)
    assert CHAVE_PIX_TESTE not in logs


def test_mascarar_chave_pix_formato_uuid_mostra_so_ultimo_grupo():
    assert mascarar_chave_pix(CHAVE_PIX_TESTE) == "••••••••-••••-••••-••••-232e3d201d24"


def test_mascarar_chave_pix_formato_generico_mostra_so_ultimos_4():
    assert mascarar_chave_pix("11999999999") == "••••••••9999"
    assert mascarar_chave_pix("cliente@misticapresentes.com.br") == "••••••••m.br"


def test_config_pix_expõe_nome_da_loja_separado_do_recebedor():
    anterior_nome = os.environ.get("MISTICA_PIX_NOME")
    anterior_loja = os.environ.get("MISTICA_LOJA_NOME")
    os.environ["MISTICA_PIX_NOME"] = RECEBEDOR_TESTE
    os.environ["MISTICA_LOJA_NOME"] = NOME_LOJA_TESTE
    try:
        cfg = config_pix()
        assert cfg["nome"] == RECEBEDOR_TESTE
        assert cfg["nome_loja"] == NOME_LOJA_TESTE
        assert cfg["nome"] != cfg["nome_loja"]
    finally:
        for chave, valor in (("MISTICA_PIX_NOME", anterior_nome), ("MISTICA_LOJA_NOME", anterior_loja)):
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor
