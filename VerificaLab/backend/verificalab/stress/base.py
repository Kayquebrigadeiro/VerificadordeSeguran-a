"""Contratos comuns para adapters de ferramentas de stress."""

from __future__ import annotations

import ipaddress
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit

from verificalab import config
from verificalab.core import authorization
from verificalab.core.runner import RunResult
from verificalab.stress.registry import MaxLimits, Tool, ToolRegistry

StressResult = RunResult


class AdapterExecutionError(RuntimeError):
    """A ferramenta não tem um modo de execução seguro suportado pelo adapter."""


@dataclass(frozen=True, slots=True)
class StressRequest:
    target: str
    duration_s: int = 5
    threads: int = 1
    port: int | None = None
    path: str = "/"
    extra_args: tuple[str, ...] = ()


class StressAdapter(ABC):
    """Base para executar ferramentas com limites declarados no catálogo."""

    tool_id: ClassVar[str]

    def _tool(self) -> Tool:
        tool = ToolRegistry.load().get(self.tool_id)
        if tool is None:
            raise ValueError(f"ferramenta ausente do catálogo: {self.tool_id}")
        return tool

    def clamp(self, req: StressRequest) -> StressRequest:
        if not isinstance(req, StressRequest):
            raise TypeError("req deve ser StressRequest")
        if type(req.duration_s) is not int or req.duration_s <= 0:
            raise ValueError("duration_s deve ser um inteiro positivo")
        if type(req.threads) is not int or req.threads <= 0:
            raise ValueError("threads deve ser um inteiro positivo")

        tool = self._tool()
        limits = tool.max_limits or MaxLimits(
            duration_s=tool.default_limits.duration_s,
            threads=tool.default_limits.threads,
        )
        return replace(
            req,
            duration_s=min(req.duration_s, limits.duration_s),
            threads=min(req.threads, limits.threads),
        )

    def _local_target_url(
        self, req: StressRequest, *, allow_extra_args: bool = False
    ) -> str:
        if not isinstance(req.target, str) or not req.target.strip():
            raise ValueError("target deve ser uma string não vazia")
        if (
            not isinstance(req.path, str)
            or not req.path.startswith("/")
            or req.path.startswith("//")
        ):
            raise ValueError("path deve ser um caminho HTTP absoluto local")
        if any(character in req.path for character in ("\r", "\n", "?", "#", "\\")):
            raise ValueError("path contém caracteres não permitidos")
        if req.port is not None and (
            type(req.port) is not int or not 1 <= req.port <= 65535
        ):
            raise ValueError("port deve estar entre 1 e 65535")
        if not isinstance(req.extra_args, (tuple, list)) or (
            req.extra_args and not allow_extra_args
        ):
            raise ValueError("extra_args não é suportado")

        value = req.target.strip()
        if value == "::1":
            value = "[::1]"
        parsed = urlsplit(value if "://" in value else f"//{value}")
        if parsed.scheme and parsed.scheme.lower() != "http":
            raise ValueError("somente HTTP sem TLS é suportado")
        if (
            parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("target deve conter somente host e porta")
        try:
            embedded_port = parsed.port
        except ValueError as exc:
            raise ValueError("porta inválida em target") from exc
        if embedded_port is not None and req.port is not None and embedded_port != req.port:
            raise ValueError("port não corresponde à porta de target")

        host = parsed.hostname.lower()
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = host == "localhost"
        if not is_loopback or host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("somente alvos loopback explícitos são permitidos")

        port = req.port or embedded_port or 80
        formatted_host = f"[{host}]" if ":" in host else host
        return f"http://{formatted_host}:{port}{req.path}"

    def _tool_path(self) -> Path:
        root = config.BASE_DIR.parent.resolve()
        tool_path = (root / self._tool().path).resolve(strict=True)
        if not tool_path.is_relative_to(root):
            raise RuntimeError(f"caminho da ferramenta fora da raiz: {tool_path}")
        return tool_path

    @staticmethod
    def _has_root() -> bool:
        return hasattr(os, "geteuid") and os.geteuid() == 0

    def _authorize_and_limit(self, req: StressRequest) -> StressRequest:
        authorization.require_authorization(req.target)
        limited = self.clamp(req)
        self._local_target_url(limited)
        if self._tool().requires_root and not self._has_root():
            raise PermissionError(f"{self.tool_id} requer privilégios de root")
        return limited

    @staticmethod
    def _execute(
        command: list[str],
        req: StressRequest,
        *,
        startup_grace_s: int = 5,
        cwd: Path | None = None,
    ) -> RunResult:
        from verificalab.core.runner import run_subprocess

        return run_subprocess(
            command,
            cwd=config.BACKEND_DIR if cwd is None else cwd,
            timeout_s=req.duration_s + startup_grace_s,
        )

    @abstractmethod
    def build_cmd(self, req: StressRequest) -> list[str]:
        """Monta argumentos sem shell para a ferramenta configurada."""

    @abstractmethod
    def run(self, req: StressRequest) -> RunResult:
        """Autoriza, limita e executa o teste."""
