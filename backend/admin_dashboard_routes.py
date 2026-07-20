"""Rotas do Centro de Operações administrativo (Fases 1, 3 e 10).

Somente leitura: nenhuma rota aqui grava em pedidos, estoque, pagamentos ou
qualquer outra entidade de negócio. Reaproveita a mesma dependência de
sessão/chave de API já usada pelo restante do painel administrativo
(backend/panel_sessions.py) -- nenhum mecanismo de autenticação novo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.panel_sessions import exigir_sessao_ou_chave_api
from services.admin_dashboard_service import obter_kpis_operacionais
from services.admin_homologacao_service import obter_checklist_homologacao

router = APIRouter(prefix="/api/painel", tags=["painel-operacoes"])


@router.get("/operacoes/dashboard")
def dashboard_operacional(sessao: dict = Depends(exigir_sessao_ou_chave_api("vendedor"))):
    return obter_kpis_operacionais()


@router.get("/operacoes/alertas")
def alertas_operacionais(sessao: dict = Depends(exigir_sessao_ou_chave_api("vendedor"))):
    dados = obter_kpis_operacionais()
    return {"gerado_em": dados["gerado_em"], "alertas": dados["alertas"]}


@router.get("/operacoes/homologacao")
def checklist_homologacao(sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    return obter_checklist_homologacao()
