"""Gate de autorização para execução de ferramentas de stress."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from verificalab import config
from verificalab.core.authorization import (
    Authorization,
    AuthorizationError,
    require_authorization,
)


@pytest.fixture
def authorization_file(tmp_path, monkeypatch):
    path = tmp_path / "authorization.json"
    monkeypatch.setattr(config, "AUTHORIZATION_FILE", path)
    return path


def write_authorization(path, **overrides):
    data = {
        "target": "example.com",
        "owner": "security-team",
        "reason": "approved load test",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.mark.parametrize(
    "target",
    [
        "127.0.0.1",
        "::1",
        "localhost",
        "127.0.0.1:8080",
        "http://127.0.0.1:8080/path",
    ],
)
def test_loopback_targets_are_authorized_without_file(target, authorization_file):
    authorization = require_authorization(target)

    assert isinstance(authorization, Authorization)
    assert authorization.target == target
    assert not authorization_file.exists()


@pytest.mark.parametrize("target", ["8.8.8.8", "example.com"])
def test_non_loopback_without_file_is_rejected(target, authorization_file):
    with pytest.raises(AuthorizationError):
        require_authorization(target)


def test_authorized_target_is_allowed(authorization_file):
    expected = write_authorization(authorization_file)

    authorization = require_authorization("example.com")

    assert authorization == Authorization(**expected)


def test_authorization_with_optional_signature_is_allowed(authorization_file):
    expected = write_authorization(authorization_file, signature="approval-123")

    authorization = require_authorization("example.com")

    assert authorization.signature == expected["signature"]


def test_different_target_is_rejected(authorization_file):
    write_authorization(authorization_file, target="other.example")

    with pytest.raises(AuthorizationError, match="não corresponde"):
        require_authorization("example.com")


def test_expired_authorization_is_rejected(authorization_file):
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    write_authorization(authorization_file, expires_at=expired)

    with pytest.raises(AuthorizationError, match="expirou"):
        require_authorization("example.com")


def test_invalid_json_is_rejected(authorization_file):
    authorization_file.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(AuthorizationError, match="ler uma autorização válida"):
        require_authorization("example.com")


@pytest.mark.parametrize("missing", ["target", "owner", "reason", "expires_at"])
def test_missing_required_field_is_rejected(authorization_file, missing):
    data = {
        "target": "example.com",
        "owner": "security-team",
        "reason": "approved load test",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    del data[missing]
    authorization_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(AuthorizationError, match="campo obrigatório inválido"):
        require_authorization("example.com")


def test_naive_expiration_is_rejected(authorization_file):
    write_authorization(
        authorization_file,
        expires_at=(datetime.now() + timedelta(hours=1)).isoformat(),
    )

    with pytest.raises(AuthorizationError, match="incluir fuso horário"):
        require_authorization("example.com")


def test_private_network_is_not_treated_as_loopback(authorization_file):
    with pytest.raises(AuthorizationError):
        require_authorization("10.0.0.1")


def test_non_object_json_is_rejected(authorization_file):
    authorization_file.write_text("[]", encoding="utf-8")

    with pytest.raises(AuthorizationError, match="objeto JSON"):
        require_authorization("example.com")
