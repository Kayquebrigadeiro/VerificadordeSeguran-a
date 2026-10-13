"""Gate de autorização para execução controlada de ferramentas de stress test."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from verificalab import config


class AuthorizationError(Exception):
    """O alvo não possui autorização válida para execução."""


@dataclass(frozen=True)
class Authorization:
    target: str
    owner: str
    reason: str
    expires_at: str | None
    signature: str | None = None


_REQUIRED_FIELDS = ("target", "owner", "reason", "expires_at")


def _is_loopback_target(target: str) -> bool:
    """Reconhece apenas localhost, 127.0.0.1 e ::1 sem resolver DNS."""
    value = target.strip()
    if not value:
        return False

    if "://" in value:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        if parsed.scheme.lower() not in ("http", "https"):
            return False
    else:
        try:
            address = ip_address(value.strip("[]"))
        except ValueError:
            address = None
        if address is not None:
            return str(address) in ("127.0.0.1", "::1")
        try:
            parsed = urlsplit(f"//{value}")
        except ValueError:
            return False

    try:
        hostname = parsed.hostname
    except ValueError:
        return False
    if hostname is None:
        return False
    try:
        address = ip_address(hostname)
    except ValueError:
        return hostname.lower() == "localhost"
    return str(address) in ("127.0.0.1", "::1")


def _read_authorization(path: Path) -> Authorization:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorizationError(
            f"não foi possível ler uma autorização válida: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise AuthorizationError("authorization.json deve conter um objeto JSON")
    for field in _REQUIRED_FIELDS:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise AuthorizationError(
                f"authorization.json contém campo obrigatório inválido: {field}"
            )
    if "signature" in data and (
        not isinstance(data["signature"], str) or not data["signature"].strip()
    ):
        raise AuthorizationError("campo signature inválido")

    expires_at = data["expires_at"]
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError("expires_at deve ser uma data ISO 8601 válida") from exc
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise AuthorizationError("expires_at deve incluir fuso horário")
    if expiry <= datetime.now(timezone.utc):
        raise AuthorizationError("authorization.json expirou")

    return Authorization(
        target=data["target"],
        owner=data["owner"],
        reason=data["reason"],
        expires_at=expires_at,
        signature=data.get("signature"),
    )


def require_authorization(target: str) -> Authorization:
    """Libera loopback definido explicitamente ou exige autorização do alvo."""
    if not isinstance(target, str) or not target.strip():
        raise AuthorizationError("target deve ser uma string não vazia")

    if _is_loopback_target(target):
        return Authorization(
            target=target,
            owner="local",
            reason="alvo loopback",
            expires_at=None,
        )

    authorization = _read_authorization(config.AUTHORIZATION_FILE)
    if authorization.target != target.strip():
        raise AuthorizationError("target da autorização não corresponde ao alvo pedido")
    return authorization
