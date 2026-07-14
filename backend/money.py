from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def centavos(valor) -> Decimal:
    """Converte um valor monetário para Decimal arredondado em centavos
    (ROUND_HALF_UP), evitando comparação direta de float. Levanta ValueError
    para entradas ausentes/inválidas em vez de assumir um valor padrão."""
    if valor is None:
        raise ValueError("valor monetário ausente")
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("valor monetário inválido") from exc
