"""Adapter MikuMikuBeam para HTTP direto em loopback, sem proxies."""

from __future__ import annotations

import os
from pathlib import Path

from verificalab.core.runner import RunResult
from verificalab.stress.base import StressAdapter, StressRequest


class MikuMikuBeamAdapter(StressAdapter):
    tool_id = "mikumikubeam"

    def build_cmd(self, req: StressRequest) -> list[str]:
        limited = self.clamp(req)
        target = self._local_target_url(limited)
        tool_dir = self._tool_path()
        project_root = tool_dir.parent.parent
        return [
            "env",
            "HOME=/dev/null",
            f"GOMODCACHE={os.environ.get('GOMODCACHE', Path.home() / 'go/pkg/mod')}",
            f"GOCACHE={os.environ.get('GOCACHE', Path.home() / '.cache/go-build')}",
            "GOTOOLCHAIN=local",
            "GOPROXY=off",
            "go",
            "-C",
            str(project_root),
            "run",
            "./cmd/mmb-cli",
            "attack",
            "--duration",
            str(limited.duration_s),
            "--delay",
            "1000",
            "--packet-size",
            "512",
            "--threads",
            str(limited.threads),
            "--no-proxy",
            "http_flood",
            target,
        ]

    def run(self, req: StressRequest) -> RunResult:
        limited = self._authorize_and_limit(req)
        return self._execute(
            self.build_cmd(limited),
            limited,
            startup_grace_s=30,
        )
