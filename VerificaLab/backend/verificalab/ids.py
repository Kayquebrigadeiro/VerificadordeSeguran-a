"""Geração de identificadores e caminhos — sempre decidida pelo backend."""

from __future__ import annotations

import hashlib
import secrets
import time


def new_id(prefix: str) -> str:
    """ID opaco com prefixo, gerado no backend. Ex.: run_01j2xk..."""
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"{prefix}_{ts:x}{rand}"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_filename(name: str, default: str = "upload.bin") -> str:
    """Reduz um nome de arquivo ao basename seguro (sem caminhos).

    O nome nunca é usado como caminho de destino; apenas como rótulo.
    """
    if not name:
        return default
    base = name.replace("\\", "/").split("/")[-1]
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ()[]").strip(" .")
    cleaned = cleaned[:120]
    if not cleaned or cleaned in {".", ".."}:
        return default
    return cleaned
