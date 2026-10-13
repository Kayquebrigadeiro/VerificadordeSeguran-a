"""Helpers de serialização das rotas."""

from __future__ import annotations

import json

from fastapi import HTTPException

from ..db import Database


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def row_or_404(row, entity: str):
    if row is None:
        raise HTTPException(status_code=404, detail=f"{entity} não encontrado")
    return row


def profile_out(row: dict) -> dict:
    out = dict(row)
    out["config"] = json.loads(out.pop("config_json"))
    return out


def run_out(row: dict) -> dict:
    out = dict(row)
    out["config"] = json.loads(out.pop("config_json"))
    out.pop("cancel_requested", None)
    return out


def env_out(row: dict) -> dict:
    """Ambiente sem qualquer valor de segredo (só indicador)."""
    out = dict(row)
    out["has_secret"] = bool(out.pop("secret_header_value", None)) or bool(
        out.get("secret_header_name") and _secret_exists(out["id"]))
    return out


def _secret_exists(env_id: str) -> bool:
    from .. import config
    return (config.SECRETS_DIR / f"{env_id}.secret").exists()


def tool_out(row: dict) -> dict:
    out = dict(row)
    out["capabilities"] = json.loads(out.pop("capabilities_json"))
    out["import_formats"] = json.loads(out.pop("import_formats_json"))
    return out
