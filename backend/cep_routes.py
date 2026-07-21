from __future__ import annotations

"""Consulta opcional de CEP (Fase 3 — entrega ou retirada no checkout).

Proxy simples para o ViaCEP, feito no backend por dois motivos:
- nenhuma chave/segredo é necessário aqui (ViaCEP é público), mas manter a
  chamada no servidor evita adicionar um host externo ao CSP connect-src do
  frontend;
- o resultado é só uma SUGESTÃO para preencher o formulário — nunca decide
  sozinho o frete (isso é sempre feito a partir da cidade/UF persistidas,
  ver backend/frete.py) e o cliente sempre revisa antes de confirmar.

Falhas (timeout, CEP não encontrado, serviço fora do ar) nunca devem
bloquear o preenchimento manual do endereço — por isso o timeout é curto e
o erro devolvido é sempre genérico, sem detalhe interno.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api", tags=["cep"])

limitar_consulta_cep = limitar_requisicoes("consultar_cep", limite=30, janela_segundos=60)

TIMEOUT_CONSULTA_CEP = 2.5


@router.get("/cep/{cep}", dependencies=[Depends(limitar_consulta_cep)])
def consultar_cep(cep: str):
    digitos = "".join(ch for ch in str(cep) if ch.isdigit())
    if len(digitos) != 8:
        raise HTTPException(status_code=400, detail="CEP inválido: informe 8 dígitos.")

    try:
        resposta = httpx.get(f"https://viacep.com.br/ws/{digitos}/json/", timeout=TIMEOUT_CONSULTA_CEP)
        dados = resposta.json()
    except Exception:
        raise HTTPException(status_code=503, detail="Consulta de CEP indisponível no momento. Preencha o endereço manualmente.")

    if not isinstance(dados, dict) or dados.get("erro"):
        raise HTTPException(status_code=404, detail="CEP não encontrado. Preencha o endereço manualmente.")

    return {
        "cep": digitos,
        "rua": str(dados.get("logradouro") or "")[:200],
        "bairro": str(dados.get("bairro") or "")[:120],
        "cidade": str(dados.get("localidade") or "")[:120],
        "uf": str(dados.get("uf") or "")[:2].upper(),
    }
