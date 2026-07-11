"""Configuração de logging estruturado (JSON) para a API.

Cada linha de log é emitida como um objeto JSON em stdout, com campos
fixos (timestamp, level, logger, message) mais quaisquer atributos extras
passados via `logger.info(..., extra={...})`. Isso permite que provedores
de log (Render, Railway, Datadog, etc.) indexem e filtrem por campo em vez
de fazer parsing de texto livre.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_RESERVED_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configurar_logging() -> None:
    """Configura o logging raiz uma única vez (idempotente)."""
    root = logging.getLogger()
    if getattr(root, "_mistica_configurado", False):
        return

    nivel = os.environ.get("MISTICA_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)
    root._mistica_configurado = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    configurar_logging()
    return logging.getLogger(name)
