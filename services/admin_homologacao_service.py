"""Checklist de homologação comercial (Fase 10 do painel administrativo).

Cada item devolve um indicador verde/amarelo/vermelho e uma descrição curta,
sem nunca expor segredo, chave, caminho de disco ou stack trace -- os
mesmos limites já aplicados por backend/system_status_routes.py e
backend/infra_diagnostics.py, que este módulo reaproveita em vez de
duplicar.

Itens que não podem ser aferidos automaticamente pelo backend (SSL do
domínio público, Lighthouse/Performance) voltam com indicador "info":
o painel os mostra como "verificação manual", nunca como um verde
inventado.
"""

from __future__ import annotations

from backend.database import conectar
from backend.infra_diagnostics import diagnostico_disco_completo, escrita_disco_segura
from backend.mercadopago_flags import mercado_pago_habilitado, mercado_pago_webhook_configurado
from backend.pix import config_pix
from database.backup import backup_habilitado

VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"
INFO = "info"


def _item(chave: str, titulo: str, status: str, detalhe: str) -> dict:
    return {"chave": chave, "titulo": titulo, "status": status, "detalhe": detalhe}


def _checar_banco(conn) -> dict:
    # Reaproveita a conexão já aberta por obter_checklist_homologacao em vez
    # de abrir uma segunda (o que banco_acessivel() faria por conta própria).
    try:
        conn.execute("SELECT 1").fetchone()
        ok = True
    except Exception:
        ok = False
    return _item("banco", "Banco de dados", VERDE if ok else VERMELHO, "Conexão e leitura ok." if ok else "Banco inacessível.")


def _checar_api() -> dict:
    return _item("api", "API interna", VERDE, "Processo respondendo (rota executada com sucesso).")


def _checar_mercadopago() -> dict:
    if not mercado_pago_habilitado():
        return _item("mercadopago", "Mercado Pago", AMARELO, "Integração desligada por flag/ambiente.")
    if not mercado_pago_webhook_configurado():
        return _item("mercadopago", "Mercado Pago", AMARELO, "Credenciais ok, mas webhook secret não configurado.")
    return _item("mercadopago", "Mercado Pago", VERDE, "Credenciais e webhook configurados.")


def _checar_pix() -> dict:
    cfg = config_pix()
    if cfg.get("chave"):
        return _item("pix", "Pix", VERDE, "Chave Pix configurada.")
    return _item("pix", "Pix", AMARELO, "Chave Pix não configurada.")


def _checar_ssl() -> dict:
    return _item("ssl", "SSL do domínio público", INFO, "Verificação manual (certificado do domínio, fora do processo da API).")


def _checar_backup() -> dict:
    ok = backup_habilitado()
    return _item("backup", "Backup", VERDE if ok else AMARELO, "Backup automático habilitado." if ok else "Backup automático desligado.")


def _checar_disco(conn) -> dict:
    disco = diagnostico_disco_completo()
    escrita_ok, _motivo = escrita_disco_segura()
    if not disco.get("acessivel") or not escrita_ok:
        return _item("uploads", "Disco / Uploads", VERMELHO, "Disco inacessível ou sem permissão de escrita.")
    if disco.get("classificacao") == "critico":
        return _item("uploads", "Disco / Uploads", VERMELHO, "Espaço em disco crítico.")
    if disco.get("classificacao") == "atencao":
        return _item("uploads", "Disco / Uploads", AMARELO, "Espaço em disco em atenção.")
    return _item("uploads", "Disco / Uploads", VERDE, "Disco acessível, gravável e com espaço saudável.")


def _checar_cursos(conn) -> dict:
    from backend.course_routes import garantir_tabela_cursos

    garantir_tabela_cursos(conn)
    total = conn.execute("SELECT COUNT(*) FROM cursos_materiais").fetchone()
    qtd = int(total[0] or 0) if total else 0
    return _item("cursos", "Cursos", VERDE if qtd > 0 else AMARELO, f"{qtd} material(is) cadastrado(s).")


def _checar_produtos(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1").fetchone()
    qtd = int(total[0] or 0) if total else 0
    return _item("produtos", "Produtos", VERDE if qtd > 0 else VERMELHO, f"{qtd} produto(s) ativo(s).")


def _checar_pedidos(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()
    qtd = int(total[0] or 0) if total else 0
    return _item("pedidos", "Pedidos", VERDE, f"{qtd} pedido(s) registrado(s) no total.")


def _checar_emails() -> dict:
    return _item("emails", "E-mails transacionais", INFO, "Verificação manual (nenhum provedor de e-mail integrado nesta versão).")


def _checar_whatsapp() -> dict:
    return _item("whatsapp", "WhatsApp", INFO, "Verificação manual (contato via link direto, sem integração automatizada).")


def _checar_seo() -> dict:
    return _item("seo", "SEO público", INFO, "Verificação manual (sitemap.xml/robots.txt não são reavaliados aqui para não tocar SEO público).")


def _checar_lighthouse() -> dict:
    return _item("lighthouse", "Lighthouse / Performance", INFO, "Verificação manual (rodar auditoria externa antes de publicar).")


def _checar_webhooks(conn) -> dict:
    row = conn.execute("SELECT COUNT(*) FROM webhook_eventos").fetchone()
    qtd = int(row[0] or 0) if row else 0
    if qtd == 0:
        return _item("webhooks", "Webhooks", AMARELO, "Nenhum evento de webhook recebido ainda.")
    return _item("webhooks", "Webhooks", VERDE, f"{qtd} evento(s) de webhook processado(s) até agora.")


def _checar_sistema(disco_item: dict, banco_item: dict) -> dict:
    if VERMELHO in (disco_item["status"], banco_item["status"]):
        return _item("sistema", "Sistema geral", VERMELHO, "Há item crítico pendente no checklist acima.")
    if AMARELO in (disco_item["status"], banco_item["status"]):
        return _item("sistema", "Sistema geral", AMARELO, "Sistema operacional, com pontos de atenção.")
    return _item("sistema", "Sistema geral", VERDE, "Nenhum item crítico identificado.")


def obter_checklist_homologacao() -> dict:
    with conectar() as conn:
        banco_item = _checar_banco(conn)
        disco_item = _checar_disco(conn)
        itens = [
            banco_item,
            _checar_api(),
            _checar_mercadopago(),
            _checar_pix(),
            _checar_ssl(),
            _checar_backup(),
            disco_item,
            _checar_cursos(conn),
            _checar_produtos(conn),
            _checar_pedidos(conn),
            _checar_emails(),
            _checar_whatsapp(),
            _checar_seo(),
            _checar_lighthouse(),
            _checar_webhooks(conn),
        ]
        itens.append(_checar_sistema(disco_item, banco_item))

    return {"itens": itens}
