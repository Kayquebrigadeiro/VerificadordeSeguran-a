"""Adapter fail-closed para Overload, cuja interface upstream é interativa."""

from __future__ import annotations

from verificalab.core.runner import RunResult
from verificalab.stress.base import (
    AdapterExecutionError,
    StressAdapter,
    StressRequest,
)


class OverloadAdapter(StressAdapter):
    tool_id = "overload"

    def build_cmd(self, req: StressRequest) -> list[str]:
        self._local_target_url(self.clamp(req))
        raise AdapterExecutionError(
            "Overload não oferece CLI não interativa segura para o VerificaLab"
        )

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        command = self.build_cmd(limited)
        return self._execute(command, limited)
