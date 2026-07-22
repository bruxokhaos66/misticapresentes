"""Testes de backend/whatsapp_flags.py -- configuração, validação e
normalização/mascaramento de números administrativos. Nenhum teste aqui
chama rede."""
import importlib
import os


def _reload():
    import backend.whatsapp_flags as mod
    importlib.reload(mod)
    return mod


def _limpar_env(monkeypatch):
    for chave in list(os.environ):
        if chave.startswith("WHATSAPP_"):
            monkeypatch.delenv(chave, raising=False)


def test_desligado_por_padrao(monkeypatch):
    _limpar_env(monkeypatch)
    mod = _reload()
    assert mod.whatsapp_notificacoes_ligadas_por_flag() is False
    assert mod.whatsapp_habilitado() is False


def test_normalizar_numero_10_digitos_recebe_codigo_pais(monkeypatch):
    mod = _reload()
    assert mod.normalizar_numero_whatsapp("11999998888") == "5511999998888"


def test_normalizar_numero_ja_com_codigo_pais(monkeypatch):
    mod = _reload()
    assert mod.normalizar_numero_whatsapp("+55 (11) 99999-8888") == "5511999998888"


def test_normalizar_numero_invalido_curto(monkeypatch):
    mod = _reload()
    assert mod.normalizar_numero_whatsapp("12345") is None


def test_normalizar_numero_invalido_longo(monkeypatch):
    mod = _reload()
    assert mod.normalizar_numero_whatsapp("1" * 20) is None


def test_normalizar_numero_vazio(monkeypatch):
    mod = _reload()
    assert mod.normalizar_numero_whatsapp("") is None
    assert mod.normalizar_numero_whatsapp(None) is None


def test_mascarar_numero_nunca_expoe_completo(monkeypatch):
    mod = _reload()
    mascarado = mod.mascarar_numero_whatsapp("5511999998888")
    assert mascarado != "5511999998888"
    assert mascarado.startswith("55")
    assert mascarado.endswith("8888")
    assert "999998" not in mascarado


def test_destinatarios_admin_normaliza_e_deduplica(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "11999998888, 5511999998888, 21999997777,curto")
    mod = _reload()
    destinatarios = mod.destinatarios_admin_whatsapp()
    assert destinatarios == ["5511999998888", "5521999997777"]


def test_validar_configuracao_incompleta_reporta_erros(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
    mod = _reload()
    resultado = mod.validar_configuracao_whatsapp()
    assert resultado.valido is False
    assert any("WHATSAPP_PHONE_NUMBER_ID" in erro for erro in resultado.erros)
    assert mod.whatsapp_habilitado() is False


def _configuracao_completa(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-teste")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-teste")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-teste")
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "5511999998888")
    for evento, env_var in {
        "PEDIDO_CRIADO": "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO",
        "PIX_GERADO": "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
        "PAGAMENTO_APROVADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO",
        "PAGAMENTO_PENDENTE": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
        "PAGAMENTO_RECUSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO",
        "PAGAMENTO_EXPIRADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
        "PAGAMENTO_CANCELADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO",
        "PAGAMENTO_REEMBOLSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
        "CHARGEBACK_RECEBIDO": "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK",
        "FALHA_DE_RECONCILIACAO": "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
    }.items():
        monkeypatch.setenv(env_var, f"template_{evento.lower()}")
    return _reload()


def test_validar_configuracao_completa_habilita(monkeypatch):
    mod = _configuracao_completa(monkeypatch)
    resultado = mod.validar_configuracao_whatsapp()
    assert resultado.valido is True
    assert mod.whatsapp_habilitado() is True


def test_diagnostico_nunca_expoe_segredo(monkeypatch):
    mod = _configuracao_completa(monkeypatch)
    diagnostico = mod.diagnostico_configuracao_whatsapp()
    textos = " ".join(str(v) for v in diagnostico.values())
    assert "token-teste" not in textos
    assert "segredo-teste" not in textos
    assert "verify-teste" not in textos
    assert "5511999998888" not in textos


def test_provider_desconhecido_cai_para_disabled(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("WHATSAPP_PROVIDER", "algo_nao_suportado")
    mod = _reload()
    assert mod.whatsapp_provider_nome() == "disabled"
