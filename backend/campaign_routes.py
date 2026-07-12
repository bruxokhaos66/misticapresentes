from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar, listar, obter
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api", tags=["campanhas"])

TIPOS_CAMPANHA = {"banner", "desconto_percentual", "desconto_fixo", "frete_gratis"}
TIPOS_COM_DESCONTO = {"desconto_percentual", "desconto_fixo", "frete_gratis"}

limitar_validar_cupom = limitar_requisicoes("validar_cupom", limite=30, janela_segundos=60)


def _centavos(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def buscar_cupom_ativo(conn, codigo: str):
    """Busca uma campanha vigente cujo código de cupom bate com `codigo`
    (case-insensitive). Só campanhas ativas e dentro do período retornam."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    agora = datetime.now().isoformat(timespec="seconds")
    return conn.execute(
        """
        SELECT id, titulo, tipo, valor, codigo_cupom
        FROM campanhas
        WHERE COALESCE(ativo,1)=1
          AND codigo_cupom IS NOT NULL
          AND UPPER(TRIM(codigo_cupom)) = ?
          AND (data_inicio IS NULL OR data_inicio <= ?)
          AND (data_fim IS NULL OR data_fim >= ?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (codigo, agora, agora),
    ).fetchone()


def calcular_desconto_cupom(campanha, subtotal: float) -> dict:
    """Calcula, no servidor, o desconto de um cupom sobre o subtotal. O valor do
    desconto NUNCA vem do cliente: é sempre derivado do tipo/valor da campanha
    salva no banco. Retorna o desconto em reais e um flag de frete grátis."""
    tipo = str(campanha["tipo"] or "").strip().lower()
    valor = _centavos(campanha["valor"])
    sub = _centavos(subtotal)
    desconto = Decimal("0.00")
    frete_gratis = False
    if tipo == "desconto_percentual":
        desconto = _centavos(sub * valor / Decimal("100"))
    elif tipo == "desconto_fixo":
        desconto = valor
    elif tipo == "frete_gratis":
        frete_gratis = True
    # O desconto nunca ultrapassa o subtotal (total mínimo é zero).
    desconto = min(desconto, sub)
    if desconto < 0:
        desconto = Decimal("0.00")
    return {
        "campanha_id": int(campanha["id"]),
        "codigo": (campanha["codigo_cupom"] or "").strip().upper(),
        "titulo": campanha["titulo"],
        "tipo": tipo,
        "desconto": float(desconto),
        "frete_gratis": frete_gratis,
    }


class CupomValidarIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    subtotal: float = Field(default=0.0, ge=0)


class CampanhaIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    descricao: str = Field(default="", max_length=500)
    tipo: str = Field(default="banner")
    valor: float = Field(default=0.0, ge=0)
    codigo_cupom: Optional[str] = Field(default=None, max_length=40)
    link: Optional[str] = Field(default=None, max_length=300)
    ativo: bool = True
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None


def _validar_tipo(tipo: str) -> str:
    tipo = (tipo or "banner").strip().lower()
    if tipo not in TIPOS_CAMPANHA:
        raise HTTPException(status_code=400, detail=f"Tipo de campanha inválido. Use um de: {', '.join(sorted(TIPOS_CAMPANHA))}.")
    return tipo


@router.get("/campanhas/ativas")
def listar_campanhas_ativas():
    """Rota pública: só campanhas ativas e dentro do período vigente, usada
    para exibir banners/descontos no site."""
    agora = datetime.now().isoformat(timespec="seconds")
    return listar(
        """
        SELECT id, titulo, descricao, tipo, valor, codigo_cupom, link, data_inicio, data_fim
        FROM campanhas
        WHERE COALESCE(ativo,1)=1
          AND (data_inicio IS NULL OR data_inicio <= ?)
          AND (data_fim IS NULL OR data_fim >= ?)
        ORDER BY id DESC
        """,
        (agora, agora),
    )


@router.post("/cupons/validar", dependencies=[Depends(limitar_validar_cupom)])
def validar_cupom(payload: CupomValidarIn):
    """Rota pública usada pelo carrinho para pré-visualizar o desconto de um
    cupom antes de gerar o Pix. O desconto é sempre calculado no servidor a
    partir da campanha vigente; o cliente só informa o código e o subtotal."""
    with conectar() as conn:
        campanha = buscar_cupom_ativo(conn, payload.codigo)
    if not campanha:
        return {"valido": False, "motivo": "Cupom inválido ou expirado.", "desconto": 0.0, "frete_gratis": False}
    resultado = calcular_desconto_cupom(campanha, payload.subtotal)
    total = round(max(float(payload.subtotal or 0) - resultado["desconto"], 0.0), 2)
    return {"valido": True, "total_com_desconto": total, **resultado}


@router.get("/campanhas")
def listar_campanhas_admin(sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    return listar("SELECT * FROM campanhas ORDER BY id DESC")


@router.post("/campanhas")
def criar_campanha(campanha: CampanhaIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    tipo = _validar_tipo(campanha.tipo)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO campanhas (
                titulo, descricao, tipo, valor, codigo_cupom, link, ativo,
                data_inicio, data_fim, criado_em, atualizado_em
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                campanha.titulo.strip(),
                campanha.descricao.strip(),
                tipo,
                campanha.valor,
                (campanha.codigo_cupom or "").strip().upper() or None,
                (campanha.link or "").strip() or None,
                1 if campanha.ativo else 0,
                campanha.data_inicio,
                campanha.data_fim,
                agora,
                agora,
            ),
        )
        campanha_id = int(cur.lastrowid)
        registrar_auditoria(conn, "campanha", campanha_id, "criar", "Admin", depois=campanha.model_dump())
        conn.commit()
    return {"ok": True, "id": campanha_id}


@router.put("/campanhas/{campanha_id}")
def atualizar_campanha(campanha_id: int, campanha: CampanhaIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    tipo = _validar_tipo(campanha.tipo)
    existente = obter("SELECT id FROM campanhas WHERE id=?", (campanha_id,))
    if not existente:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        conn.execute(
            """
            UPDATE campanhas
               SET titulo=?, descricao=?, tipo=?, valor=?, codigo_cupom=?, link=?,
                   ativo=?, data_inicio=?, data_fim=?, atualizado_em=?
             WHERE id=?
            """,
            (
                campanha.titulo.strip(),
                campanha.descricao.strip(),
                tipo,
                campanha.valor,
                (campanha.codigo_cupom or "").strip().upper() or None,
                (campanha.link or "").strip() or None,
                1 if campanha.ativo else 0,
                campanha.data_inicio,
                campanha.data_fim,
                agora,
                campanha_id,
            ),
        )
        registrar_auditoria(conn, "campanha", campanha_id, "atualizar", "Admin", depois=campanha.model_dump())
        conn.commit()
    return {"ok": True, "id": campanha_id}


@router.delete("/campanhas/{campanha_id}")
def excluir_campanha(campanha_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    existente = obter("SELECT id FROM campanhas WHERE id=?", (campanha_id,))
    if not existente:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    with conectar() as conn:
        conn.execute("DELETE FROM campanhas WHERE id=?", (campanha_id,))
        registrar_auditoria(conn, "campanha", campanha_id, "excluir", "Admin")
        conn.commit()
    return {"ok": True}
