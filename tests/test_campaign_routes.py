"""Testes HTTP das rotas administrativas de campanhas promocionais
(backend/campaign_routes.py).

Cobre a auditoria do módulo de Campanhas: listar/criar/atualizar/excluir,
a nova ação dedicada "encerrar campanha" (idempotente, sem excluir o
registro), a rota pública /api/campanhas/ativas e a regra de autorização
adotada (perfil "adm" para toda escrita; leitura aceita "vendedor").

Usa o banco temporário isolado configurado por tests/conftest.py -- nunca
toca no banco real da aplicação.
"""
from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key-campanhas"  # pragma: allowlist secret
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")

ORIGIN_HEADER = {"Origin": "http://localhost:3000"}


def _ip_unico() -> str:
    n = uuid.uuid4().int
    return f"198.{(n >> 16) % 256}.{(n >> 8) % 256}.{n % 256}"


def _criar_usuario_com_sessao(perfil: str) -> TestClient:
    """Cria um usuário com o perfil informado e faz login num TestClient
    próprio (cookie jar isolado por instância), devolvendo o client já
    autenticado por cookie de sessão."""
    from config import hash_password_pbkdf2
    from backend.database import conectar

    login = f"{perfil}-campanhas-{uuid.uuid4().hex[:8]}"
    senha = "Senha-Forte-Teste123!"
    salt = f"salt-{login}"
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
        headers={"X-Forwarded-For": _ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return sessao_client


@pytest.fixture(scope="module")
def admin_client() -> TestClient:
    return _criar_usuario_com_sessao("adm")


@pytest.fixture(scope="module")
def vendedor_client() -> TestClient:
    return _criar_usuario_com_sessao("vendedor")


def _titulo(prefixo: str) -> str:
    return f"{prefixo} {uuid.uuid4().hex[:10]}"


def _payload_campanha(**overrides) -> dict:
    payload = {
        "titulo": _titulo("Campanha Teste"),
        "descricao": "Descrição de teste",
        "tipo": "desconto_percentual",
        "valor": 10.0,
        "codigo_cupom": None,
        "link": None,
        "ativo": True,
        "data_inicio": None,
        "data_fim": None,
    }
    payload.update(overrides)
    return payload


def _criar_campanha_via_api(admin_client: TestClient, **overrides) -> dict:
    payload = _payload_campanha(**overrides)
    resposta = admin_client.post("/api/campanhas", json=payload, headers=ORIGIN_HEADER)
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert isinstance(corpo["id"], int)
    return {**payload, "id": corpo["id"]}


# ---------------------------------------------------------------------------
# 1-2. Autenticação para listar
# ---------------------------------------------------------------------------


def test_listar_campanhas_sem_sessao_retorna_401():
    client_anonimo = TestClient(main.app)
    with client_anonimo:
        resposta = client_anonimo.get("/api/campanhas")
    assert resposta.status_code == 401


def test_listar_campanhas_com_sessao_vendedor_retorna_lista(vendedor_client, admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Listagem Vendedor"))

    resposta = vendedor_client.get("/api/campanhas")

    assert resposta.status_code == 200
    ids = [item["id"] for item in resposta.json()]
    assert campanha["id"] in ids


# ---------------------------------------------------------------------------
# 3. Criar
# ---------------------------------------------------------------------------


def test_criar_campanha_persiste_campos_corretamente(admin_client):
    payload = _payload_campanha(
        titulo=_titulo("Criação"),
        descricao="Banner de criação",
        tipo="desconto_fixo",
        valor=25.5,
        codigo_cupom="criar-teste",
        link="https://exemplo.com/promo",
    )
    resposta = admin_client.post("/api/campanhas", json=payload, headers=ORIGIN_HEADER)
    assert resposta.status_code == 200, resposta.text
    campanha_id = resposta.json()["id"]

    listagem = admin_client.get("/api/campanhas").json()
    salva = next(item for item in listagem if item["id"] == campanha_id)
    assert salva["titulo"] == payload["titulo"]
    assert salva["descricao"] == payload["descricao"]
    assert salva["tipo"] == "desconto_fixo"
    assert salva["valor"] == 25.5
    assert salva["codigo_cupom"] == "CRIAR-TESTE"  # normalizado em maiúsculas
    assert salva["link"] == payload["link"]
    assert bool(salva["ativo"]) is True


def test_criar_campanha_como_vendedor_e_negado(vendedor_client):
    resposta = vendedor_client.post(
        "/api/campanhas", json=_payload_campanha(titulo=_titulo("Vendedor Não Pode Criar")), headers=ORIGIN_HEADER
    )
    assert resposta.status_code == 403


# ---------------------------------------------------------------------------
# 4. Atualizar
# ---------------------------------------------------------------------------


def test_atualizar_campanha_persiste_alteracoes(admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Antes de editar"))
    payload_editado = _payload_campanha(
        titulo=_titulo("Depois de editar"),
        tipo="frete_gratis",
        valor=0,
        ativo=False,
    )

    resposta = admin_client.put(f"/api/campanhas/{campanha['id']}", json=payload_editado, headers=ORIGIN_HEADER)

    assert resposta.status_code == 200, resposta.text
    listagem = admin_client.get("/api/campanhas").json()
    salva = next(item for item in listagem if item["id"] == campanha["id"])
    assert salva["titulo"] == payload_editado["titulo"]
    assert salva["tipo"] == "frete_gratis"
    assert bool(salva["ativo"]) is False


def test_atualizar_campanha_inexistente_retorna_404(admin_client):
    resposta = admin_client.put(
        "/api/campanhas/999999999", json=_payload_campanha(), headers=ORIGIN_HEADER
    )
    assert resposta.status_code == 404


def test_atualizar_campanha_como_vendedor_e_negado(vendedor_client, admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Vendedor Não Pode Editar"))

    resposta = vendedor_client.put(
        f"/api/campanhas/{campanha['id']}", json=_payload_campanha(titulo="Tentativa"), headers=ORIGIN_HEADER
    )

    assert resposta.status_code == 403


# ---------------------------------------------------------------------------
# 5. Excluir
# ---------------------------------------------------------------------------


def test_excluir_campanha_remove_e_some_da_listagem(admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Para excluir"))

    resposta = admin_client.delete(f"/api/campanhas/{campanha['id']}", headers=ORIGIN_HEADER)

    assert resposta.status_code == 200
    listagem = admin_client.get("/api/campanhas").json()
    assert campanha["id"] not in [item["id"] for item in listagem]


def test_excluir_campanha_inexistente_retorna_404(admin_client):
    resposta = admin_client.delete("/api/campanhas/999999999", headers=ORIGIN_HEADER)
    assert resposta.status_code == 404


def test_excluir_campanha_como_vendedor_e_negado(vendedor_client, admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Vendedor Não Pode Excluir"))

    resposta = vendedor_client.delete(f"/api/campanhas/{campanha['id']}", headers=ORIGIN_HEADER)

    assert resposta.status_code == 403
    listagem = admin_client.get("/api/campanhas").json()
    assert campanha["id"] in [item["id"] for item in listagem]


# ---------------------------------------------------------------------------
# 6. Encerrar campanha
# ---------------------------------------------------------------------------


def test_encerrar_campanha_desativa_e_atualiza_data_fim_mantendo_demais_dados(admin_client):
    fim_futuro = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
    campanha = _criar_campanha_via_api(
        admin_client,
        titulo=_titulo("Para encerrar"),
        codigo_cupom="encerrar-mantem",
        tipo="desconto_percentual",
        valor=15,
        data_fim=fim_futuro,
    )
    antes = datetime.now().isoformat(timespec="seconds")

    resposta = admin_client.post(f"/api/campanhas/{campanha['id']}/encerrar", headers=ORIGIN_HEADER)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert corpo["ja_encerrada"] is False

    listagem = admin_client.get("/api/campanhas").json()
    salva = next(item for item in listagem if item["id"] == campanha["id"])
    assert bool(salva["ativo"]) is False
    assert salva["data_fim"] != fim_futuro
    assert salva["data_fim"] >= antes  # data_fim virou "agora", não a data futura original
    assert salva["atualizado_em"] >= antes
    # Não altera cupom, título nem os demais dados da campanha.
    assert salva["codigo_cupom"] == "ENCERRAR-MANTEM"
    assert salva["titulo"] == campanha["titulo"]
    assert salva["tipo"] == "desconto_percentual"
    assert salva["valor"] == 15.0


def test_encerrar_campanha_inexistente_retorna_404(admin_client):
    resposta = admin_client.post("/api/campanhas/999999999/encerrar", headers=ORIGIN_HEADER)
    assert resposta.status_code == 404


def test_encerrar_campanha_repetido_e_idempotente(admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Encerrar duas vezes"))

    primeira = admin_client.post(f"/api/campanhas/{campanha['id']}/encerrar", headers=ORIGIN_HEADER)
    assert primeira.status_code == 200
    assert primeira.json()["ja_encerrada"] is False
    data_fim_primeira = admin_client.get("/api/campanhas").json()
    data_fim_primeira = next(item for item in data_fim_primeira if item["id"] == campanha["id"])["data_fim"]

    segunda = admin_client.post(f"/api/campanhas/{campanha['id']}/encerrar", headers=ORIGIN_HEADER)

    assert segunda.status_code == 200
    assert segunda.json()["ja_encerrada"] is True
    listagem = admin_client.get("/api/campanhas").json()
    salva = next(item for item in listagem if item["id"] == campanha["id"])
    assert bool(salva["ativo"]) is False
    # Repetir a operação não altera de novo data_fim/atualizado_em: o estado
    # final permanece o mesmo, sem inconsistência entre chamadas.
    assert salva["data_fim"] == data_fim_primeira


def test_encerrar_campanha_como_vendedor_e_negado(vendedor_client, admin_client):
    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Vendedor Não Pode Encerrar"))

    resposta = vendedor_client.post(f"/api/campanhas/{campanha['id']}/encerrar", headers=ORIGIN_HEADER)

    assert resposta.status_code == 403
    listagem = admin_client.get("/api/campanhas").json()
    salva = next(item for item in listagem if item["id"] == campanha["id"])
    assert bool(salva["ativo"]) is True


# ---------------------------------------------------------------------------
# 7. Rota pública /api/campanhas/ativas
# ---------------------------------------------------------------------------


def test_rota_publica_lista_apenas_campanhas_ativas_e_vigentes(admin_client):
    client_publico = TestClient(main.app)
    with client_publico:
        ativa = _criar_campanha_via_api(admin_client, titulo=_titulo("Pública ativa"))

        futura = _criar_campanha_via_api(
            admin_client,
            titulo=_titulo("Pública futura"),
            data_inicio=(datetime.now() + timedelta(days=5)).isoformat(timespec="seconds"),
        )

        expirada = _criar_campanha_via_api(
            admin_client,
            titulo=_titulo("Pública expirada"),
            data_fim=(datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"),
        )

        encerrada = _criar_campanha_via_api(admin_client, titulo=_titulo("Pública encerrada"))
        resposta_encerrar = admin_client.post(f"/api/campanhas/{encerrada['id']}/encerrar", headers=ORIGIN_HEADER)
        assert resposta_encerrar.status_code == 200

        resposta = client_publico.get("/api/campanhas/ativas")
        assert resposta.status_code == 200
        ids_publicos = [item["id"] for item in resposta.json()]

        assert ativa["id"] in ids_publicos
        assert futura["id"] not in ids_publicos
        assert expirada["id"] not in ids_publicos
        # Some da rota pública imediatamente após o encerramento, sem esperar
        # a data_fim original.
        assert encerrada["id"] not in ids_publicos


# ---------------------------------------------------------------------------
# 8. Auditoria
# ---------------------------------------------------------------------------


def test_encerrar_campanha_registra_auditoria(admin_client):
    from backend.database import listar

    campanha = _criar_campanha_via_api(admin_client, titulo=_titulo("Auditoria encerrar"))

    resposta = admin_client.post(f"/api/campanhas/{campanha['id']}/encerrar", headers=ORIGIN_HEADER)
    assert resposta.status_code == 200

    registros = listar(
        "SELECT * FROM audit_log WHERE entidade='campanha' AND entidade_id=? AND acao='encerrar'",
        (str(campanha["id"]),),
    )
    assert len(registros) == 1
    assert registros[0]["usuario"]
