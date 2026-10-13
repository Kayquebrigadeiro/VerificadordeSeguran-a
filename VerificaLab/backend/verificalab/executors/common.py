"""Cliente HTTP seguro dos testes — política aplicada antes de CADA envio.

- trust_env=False: proxies do ambiente são ignorados (nenhum proxy herdado).
- follow_redirects=False: cada Location passa pela política de alvo; destino
  não cadastrado é recusado ANTES da chamada.
- Resposta limitada a config.HTTP_MAX_RESPONSE_BYTES.
- Timeout obrigatório em toda requisição.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from .. import config
from ..targetpolicy import TargetPolicy, TargetPolicyError


@dataclass
class HttpOutcome:
    url: str
    method: str
    status: int | None = None
    headers: dict = field(default_factory=dict)
    content: bytes = b""
    truncated: bool = False
    duration_ms: float | None = None
    redirects: list = field(default_factory=list)
    blocked_redirect: str | None = None
    error: str | None = None
    error_detail: str = ""

    @property
    def ok_transport(self) -> bool:
        return self.error is None


def make_client(timeout_s: float = config.HTTP_DEFAULT_TIMEOUT_S) -> httpx.Client:
    return httpx.Client(
        trust_env=False,           # sem proxies herdados do ambiente
        follow_redirects=False,    # redirect validado manualmente pela política
        timeout=httpx.Timeout(timeout_s),
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
    )


def send_checked(
    client: httpx.Client,
    policy: TargetPolicy,
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    max_redirects: int = 3,
) -> HttpOutcome:
    """Envia uma requisição validada; segue redirects apenas dentro da origem."""
    outcome = HttpOutcome(url=url, method=method)
    current = policy.validate_url(url)   # pode levantar TargetPolicyError (antes de enviar)
    start = time.perf_counter()
    try:
        for _hop in range(max_redirects + 1):
            t0 = time.perf_counter()
            try:
                with client.stream(method, current, headers=headers) as resp:
                    chunks: list[bytes] = []
                    size = 0
                    truncated = False
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > config.HTTP_MAX_RESPONSE_BYTES:
                            truncated = True
                            keep = len(chunk) - (size - config.HTTP_MAX_RESPONSE_BYTES)
                            if keep > 0:
                                chunks.append(chunk[:keep])
                            break
                        chunks.append(chunk)
                    # última resposta da cadeia prevalece (após redirects)
                    outcome.status = resp.status_code
                    outcome.headers = {k.lower(): v for k, v in resp.headers.items()}
                    outcome.content = b"".join(chunks)
                    outcome.truncated = truncated
                    loc = resp.headers.get("location")
                    if resp.is_redirect and loc:
                        try:
                            current = policy.validate_redirect(current, loc)
                        except TargetPolicyError as exc:
                            outcome.blocked_redirect = (
                                f"redirect recusado antes da chamada: {exc.reason} "
                                f"(Location: {loc[:200]})"
                            )
                            outcome.redirects.append(
                                {"to": loc[:200], "allowed": False,
                                 "reason": exc.reason})
                            break
                        outcome.redirects.append({"to": current, "allowed": True})
                        continue
                    break
            except httpx.TimeoutException as exc:
                outcome.error = "timeout"
                outcome.error_detail = str(type(exc).__name__)
                outcome.duration_ms = (time.perf_counter() - t0) * 1000
                break
            except httpx.ConnectError as exc:
                outcome.error = "connection_error"
                outcome.error_detail = str(type(exc).__name__)
                outcome.duration_ms = (time.perf_counter() - t0) * 1000
                break
            except httpx.HTTPError as exc:
                outcome.error = "transport_error"
                outcome.error_detail = f"{type(exc).__name__}: {exc}"[:300]
                outcome.duration_ms = (time.perf_counter() - t0) * 1000
                break
        if outcome.duration_ms is None:
            outcome.duration_ms = (time.perf_counter() - start) * 1000
    finally:
        pass
    return outcome
