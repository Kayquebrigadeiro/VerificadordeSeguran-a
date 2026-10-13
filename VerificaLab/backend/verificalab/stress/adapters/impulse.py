"""Adapter Impulse limitado ao método HTTP e a alvos loopback."""

from __future__ import annotations

import sys

from verificalab.core.runner import RunResult
from verificalab.stress.base import StressAdapter, StressRequest


class ImpulseAdapter(StressAdapter):
    tool_id = "impulse"

    def build_cmd(self, req: StressRequest) -> list[str]:
        limited = self.clamp(req)
        target = self._local_target_url(limited)
        return [
            sys.executable,
            str(self._tool_path()),
            "--target",
            target,
            "--method",
            "HTTP",
            "--time",
            str(limited.duration_s),
            "--threads",
            str(limited.threads),
        ]

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        return self._execute(self.build_cmd(limited), limited)
