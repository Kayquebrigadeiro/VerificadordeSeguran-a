"""Segurança local: Host/Origin/CSRF, sanitização, redação de segredos.

- Servidor escuta somente em loopback (config.HOST).
- Requisições mutantes exigem header CSRF + Origin same-origin.
- Textos de logs/relatórios são sanitizados (sem controle, sem execução).
- Segredos de ambiente são cifrados em repouso (Fernet, chave 0600) e
  nunca aparecem em API, banco em claro, stdout ou exportações.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import config
from .ids import new_token

# ---------------------------------------------------------------------------
# CSRF / Host / Origin
# ---------------------------------------------------------------------------

_csrf_lock = threading.Lock()
_csrf_token: str | None = None
CSRF_HEADER = "X-VerificaLab-CSRF"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_token() -> str:
    global _csrf_token
    with _csrf_lock:
        if _csrf_token is None:
            token_path = config.DATA_DIR / "csrf.token"
            if token_path.exists():
                _csrf_token = token_path.read_text(encoding="utf-8").strip()
            else:
                _csrf_token = new_token()
                token_path.write_text(_csrf_token, encoding="utf-8")
                try:
                    token_path.chmod(0o600)
                except OSError:
                    pass
        return _csrf_token


def host_allowed(host_header: str | None) -> bool:
    """Hostname do header Host deve ser loopback (controle de acesso local)."""
    if not host_header:
        return False
    hostname = host_header.rsplit(":", 1)[0].strip().lower()
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]
    return hostname in config.ALLOWED_HOSTNAMES


def origin_allowed(origin: str | None) -> bool:
    """Origin ausente (curl ou same-origin) é aceito; externo é recusado."""
    if origin is None or origin == "null":
        return True
    return origin.rstrip("/") in config.ALLOWED_ORIGINS


def check_mutation(method: str, host: str | None, origin: str | None,
                   headers_get) -> str | None:
    """Retorna mensagem de erro ou None se a requisição mutante é aceitável."""
    if method.upper() not in UNSAFE_METHODS:
        return None
    if not host_allowed(host):
        return "Header Host não é loopback"
    if not origin_allowed(origin):
        return f"Origin não permitido: {origin}"
    token = headers_get(CSRF_HEADER)
    if not token or token != csrf_token():
        return "Token CSRF ausente ou inválido"
    return None


# ---------------------------------------------------------------------------
# Sanitização e redação
# ---------------------------------------------------------------------------

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*(?:\x07|\x1b\\)")

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:authorization|proxy-authorization)\b\s*[:=]\s*\S+(?:\s+\S+)?"),
    re.compile(r"(?i)[\"']?\b(?:api[_-]?key|token|secret|password|passwd|pwd)\b"
               r"[\"']?\s*[:=]\s*[\"']?[^\"'\s,;}]{4,}"),
    re.compile(r"(?i)([?&](?:token|key|api_key|apikey|password|secret)=)[^&\s\"']+"),
]

_extra_secrets: set[str] = set()
_extra_lock = threading.Lock()


def register_secret(value: str) -> None:
    """Registra um segredo real para redação em qualquer texto exportado."""
    if value and len(value) >= 4:
        with _extra_lock:
            _extra_secrets.add(value)


def sanitize_text(text: str, max_len: int = config.MAX_LOG_LINE_CHARS) -> str:
    """Remove ANSI e caracteres de controle; limita tamanho. Nunca interpreta."""
    if not isinstance(text, str):
        text = str(text)
    text = _ANSI_RE.sub("", text)
    text = _CTRL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > max_len:
        text = text[:max_len] + "…[truncado]"
    return text


def redact(text: str) -> str:
    """Substitui padrões de credenciais e segredos registrados por ***."""
    if not text:
        return text
    with _extra_lock:
        secrets_list = list(_extra_secrets)
    for s in secrets_list:
        if s in text:
            text = text.replace(s, "***")
    for pat in _SECRET_PATTERNS:
        text = pat.sub("***", text)
    return text


def redact_obj(obj):
    """Redação profunda para objetos JSON-izáveis (relatórios/exports)."""
    if isinstance(obj, str):
        return redact(sanitize_text(obj, max_len=8000))
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r"(?i)secret|token|password|api[_-]?key|authorization", str(k)):
                out[k] = "***" if v not in (None, "", 0) else v
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


def redact_json_dump(obj) -> str:
    return json.dumps(redact_obj(obj), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Segredos cifrados em repouso
# ---------------------------------------------------------------------------

class SecretsVault:
    """Armazena valores sensíveis de ambientes cifrados (Fernet).

    A chave vive em data/secrets/secret.key (0600). O banco guarda apenas
    o ciphertext. A API nunca devolve o valor — somente máscara.
    """

    def __init__(self) -> None:
        config.ensure_dirs()
        from cryptography.fernet import Fernet

        key_path: Path = config.KEY_PATH
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            try:
                key_path.chmod(0o600)
            except OSError:
                pass
        self._f = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._f.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._f.decrypt(token.encode("ascii")).decode("utf-8")


_vault: SecretsVault | None = None
_vault_lock = threading.Lock()


def get_vault() -> SecretsVault:
    global _vault
    with _vault_lock:
        if _vault is None:
            _vault = SecretsVault()
        return _vault
