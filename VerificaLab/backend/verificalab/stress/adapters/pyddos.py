"""Adapter PyDDoS limitado ao modo HTTP em loopback."""

from __future__ import annotations

import sys
from urllib.parse import urlsplit

from verificalab.core import authorization
from verificalab.core.runner import RunResult
from verificalab.stress.base import StressAdapter, StressRequest


class PyDDoSAdapter(StressAdapter):
    tool_id = "pyddos"

    def build_cmd(self, req: StressRequest) -> list[str]:
        limited = self.clamp(req)
        target = self._local_target_url(limited)
        parsed = urlsplit(target)
        if parsed.hostname != "127.0.0.1":
            raise ValueError("somente o alvo loopback 127.0.0.1 é permitido")
        return [
            sys.executable,
            str(self._tool_path()),
            "-d",
            f"{parsed.hostname}:{parsed.port}",
            "-p",
            str(parsed.port),
            "-T",
            str(limited.threads),
            "-s",
            "5",
            "-Request",
        ]

    def run(self, req: StressRequest) -> RunResult:
        authorization.require_authorization(req.target)
        limited = self.clamp(req)
        command = self.build_cmd(limited)
        return self._execute(command, limited, cwd=self._tool_path().parent)
