"""Adapter fail-closed porque o catálogo permite apenas análise estática UFONet."""

from __future__ import annotations

from verificalab.core.runner import RunResult
from verificalab.stress.base import (
    AdapterExecutionError,
    StressAdapter,
    StressRequest,
)


class UFONetAdapter(StressAdapter):
    tool_id = "ufonet"

    def build_cmd(self, req: StressRequest) -> list[str]:
        self._local_target_url(self.clamp(req))
        raise AdapterExecutionError(
            "UFONet está catalogado para análise estática; execução de tráfego está desabilitada"
        )

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        command = self.build_cmd(limited)
        return self._execute(command, limited)
