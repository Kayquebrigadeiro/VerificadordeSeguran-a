"""Adapter MHDDoS restrito a GET direto, sem proxies."""

from __future__ import annotations

import sys

from verificalab.core.runner import RunResult
from verificalab.stress.base import StressAdapter, StressRequest


class MHDDOSAdapter(StressAdapter):
    tool_id = "mhddos"

    def build_cmd(self, req: StressRequest) -> list[str]:
        limited = self.clamp(req)
        target = self._local_target_url(limited)
        proxy_list = self._tool_path().parent / "files" / "proxies" / "0"
        if not proxy_list.is_file() or proxy_list.stat().st_size != 0:
            raise RuntimeError("MHDDoS exige a lista local de proxies vazia")
        return [
            sys.executable,
            str(self._tool_path()),
            "GET",
            target,
            "0",
            str(limited.threads),
            "0",
            "1",
            str(limited.duration_s),
        ]

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        return self._execute(self.build_cmd(limited), limited)
