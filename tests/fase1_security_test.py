from pathlib import Path
import importlib
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_api_token_default_not_exposed(monkeypatch):
    import api.security as security

    monkeypatch.delenv("MISTICA_API_TOKEN", raising=False)
    security = importlib.reload(security)

    assert security.api_token_configurado() is None
    assert security.token_padrao_em_uso() is False


def test_cors_is_not_wildcard(monkeypatch):
    import api.main as api_main

    monkeypatch.delenv("MISTICA_ALLOWED_ORIGINS", raising=False)
    api_main = importlib.reload(api_main)

    assert "*" not in api_main.app.user_middleware[0].kwargs.get("allow_origins", [])
