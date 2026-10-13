"""Infra de testes: diretório de dados temporário ANTES dos imports."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_TEST_DATA = tempfile.mkdtemp(prefix="vl-test-")
os.environ["VERIFICALAB_DATA"] = _TEST_DATA
os.environ["VERIFICALAB_AUTOLAB"] = "0"
os.environ["VERIFICALAB_LAB_PORT"] = "8479"

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def app():
    from verificalab.api.server import create_app
    return create_app(start_lab=False)


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture(scope="session")
def csrf_headers(client):
    tok = client.get("/api/session").json()["csrf_token"]
    return {"X-VerificaLab-CSRF": tok}


@pytest.fixture(scope="session")
def lab_server():
    """Laboratório real em thread (porta dedicada de teste)."""
    from verificalab import labctl
    result = labctl.start()
    assert result["running"], f"lab não subiu: {result}"
    yield result
    labctl.stop()


@pytest.fixture()
def unique(request):
    """Sufixo único para nomes de entidades nos testes."""
    import uuid
    return uuid.uuid4().hex[:8]
