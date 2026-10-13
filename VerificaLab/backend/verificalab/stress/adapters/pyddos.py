"""Adapter fail-closed para o modo HTTP do PyDDoS, que ignora a porta pedida."""

from __future__ import annotations

from verificalab.core.runner import RunResult
from verificalab.stress.base import (
    AdapterExecutionError,
    StressAdapter,
    StressRequest,
)


class PyDDoSAdapter(StressAdapter):
    tool_id = "pyddos"

    def build_cmd(self, req: StressRequest) -> list[str]:
        self._local_target_url(self.clamp(req))
        raise AdapterExecutionError(
            "PyDDoS Requester não respeita a porta HTTP definida pelo VerificaLab"
        )

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        command = self.build_cmd(limited)
        return self._execute(command, limited)
