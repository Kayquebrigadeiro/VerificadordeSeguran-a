"""Política de alvo — o coração da segurança dos testes HTTP.

Regras do piloto (todas obrigatórias, verificadas ANTES de cada envio):
- Esquema somente http(s).
- Host deve ser endereço IP literal de loopback (sem resolução DNS).
- Porta deve ser a porta cadastrada do ambiente (origem exata).
- Sem credenciais embutidas na URL.
- Sem proxies do ambiente (cliente httpx com trust_env=False).
- Redirects NÃO seguem automaticamente; cada Location passa por esta
  política e precisa pertencer à mesma origem cadastrada — caso contrário
  o redirect é recusado ANTES de qualquer chamada ao destino.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urljoin, urlsplit, urlunsplit

from . import config


class TargetPolicyError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TargetPolicy:
    """Limita todas as requisições à origem cadastrada do ambiente."""

    def __init__(self, scheme: str, host: str, port: int) -> None:
        if scheme not in ("http", "https"):
            raise TargetPolicyError("esquema diferente de HTTP(S)")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise TargetPolicyError("host não é endereço IP literal") from exc
        if not ip.is_loopback:
            raise TargetPolicyError("host não é loopback")
        if not (1 <= int(port) <= 65535):
            raise TargetPolicyError("porta inválida")
        self.scheme = scheme
        self.host = str(ip)
        self.port = int(port)

    @property
    def origin(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}:{self.port}"

    def validate_url(self, url: str) -> str:
        """Valida e normaliza uma URL; levanta TargetPolicyError se recusada."""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise TargetPolicyError(f"esquema não permitido: {parts.scheme or '(vazio)'}")
        if parts.username or parts.password:
            raise TargetPolicyError("credenciais embutidas na URL")
        try:
            ip = ipaddress.ip_address(parts.hostname or "")
        except ValueError:
            raise TargetPolicyError("host não é endereço IP literal (DNS bloqueado)")
        if not ip.is_loopback:
            raise TargetPolicyError("host não é loopback")
        host = str(ip)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if parts.scheme != self.scheme or host != self.host or port != self.port:
            raise TargetPolicyError(
                f"destino fora da origem cadastrada ({self.origin})"
            )
        normalized = urlunsplit((
            parts.scheme,
            f"[{host}]:{port}" if ":" in host else f"{host}:{port}",
            parts.path or "/",
            parts.query,
            "",  # fragmento nunca viaja
        ))
        return normalized

    def build(self, path: str) -> str:
        """Monta URL absoluta a partir de path relativo e valida."""
        if not path.startswith("/"):
            path = "/" + path
        return self.validate_url(urljoin(self.origin + "/", path))

    def validate_redirect(self, current_url: str, location: str) -> str:
        """Valida Location de redirect; recusa destinos não cadastrados."""
        absolute = urljoin(current_url, location)
        return self.validate_url(absolute)

    def describe(self) -> dict:
        return {"origin": self.origin, "loopback_only": True,
                "dns_resolution": "bloqueada (IP literal obrigatório)"}


def policy_from_environment(env_row) -> TargetPolicy:
    return TargetPolicy(env_row["scheme"], env_row["host"], env_row["port"])


def parse_endpoint(url: str) -> tuple[str, str, int]:
    """Valida endpoint cadastrado (somente loopback literal) -> (scheme, host, port)."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise TargetPolicyError("endpoint deve usar http:// ou https://")
    if parts.username or parts.password:
        raise TargetPolicyError("endpoint não pode conter credenciais")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise TargetPolicyError("endpoint deve ser apenas esquema://host:porta")
    try:
        ip = ipaddress.ip_address(parts.hostname or "")
    except ValueError:
        raise TargetPolicyError("endpoint deve usar IP literal (sem DNS)")
    if not ip.is_loopback:
        raise TargetPolicyError("endpoint deve ser loopback (127.0.0.0/8 ou ::1)")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.scheme, str(ip), int(port)
