from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request

_LOCK = threading.Lock()
_HITS: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def limitar_requisicoes(chave: str, *, limite: int, janela_segundos: float):
    """Cria uma dependência FastAPI que limita requisições por IP dentro de uma janela deslizante.

    Implementação em memória: adequada para um único processo/instância. Se o serviço
    passar a rodar com múltiplos workers/instâncias, trocar por um backend compartilhado
    (Redis) para que o limite valha globalmente.
    """

    def dependencia(request: Request) -> None:
        agora = time.monotonic()
        ip = _client_ip(request)
        identificador = f"{chave}:{ip}"
        with _LOCK:
            registros = _HITS.setdefault(identificador, [])
            limite_inferior = agora - janela_segundos
            while registros and registros[0] < limite_inferior:
                registros.pop(0)
            if len(registros) >= limite:
                raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em instantes.")
            registros.append(agora)

    return dependencia
