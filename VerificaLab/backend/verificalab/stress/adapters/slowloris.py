"""Adapter limitado para o executável Slowloris original."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from verificalab import config
from verificalab.core import authorization
from verificalab.core.runner import RunResult, run_subprocess
from verificalab.stress.base import StressAdapter, StressRequest

_ALLOWED_EXTRA_ARGS = {"-v", "--verbose", "-ua", "--randuseragents"}
_SUPERVISOR = """\
import signal
import subprocess
import sys
import time

duration = float(sys.argv[1])
command = sys.argv[2:]
process = subprocess.Popen(command)
deadline = time.monotonic() + duration
while process.poll() is None and time.monotonic() < deadline:
    time.sleep(min(0.05, deadline - time.monotonic()))

stopped_by_deadline = process.poll() is None
if stopped_by_deadline:
    process.terminate()
try:
    returncode = process.wait(timeout=2)
except subprocess.TimeoutExpired:
    process.terminate()
    try:
        returncode = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait()

if stopped_by_deadline and returncode == -signal.SIGTERM:
    returncode = 0
sys.exit(returncode)
"""


class SlowlorisAdapter(StressAdapter):
    tool_id = "slowloris"

    def _target_parts(self, req: StressRequest) -> tuple[str, int]:
        if not isinstance(req.target, str) or not req.target.strip():
            raise ValueError("target deve ser uma string não vazia")
        if req.path != "/":
            raise ValueError("o executável Slowloris só suporta o caminho raiz '/'")
        if req.port is not None and (
            type(req.port) is not int or not 1 <= req.port <= 65535
        ):
            raise ValueError("port deve estar entre 1 e 65535")

        value = req.target.strip()
        parsed = urlsplit(value if "://" in value else f"//{value}")
        if parsed.scheme and parsed.scheme.lower() != "http":
            raise ValueError("somente HTTP sem TLS é suportado por este adapter")
        if (
            parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("target deve conter somente host e porta opcionais")
        try:
            embedded_port = parsed.port
        except ValueError as exc:
            raise ValueError("porta inválida em target") from exc
        if embedded_port is not None and req.port is not None:
            if embedded_port != req.port:
                raise ValueError("port não corresponde à porta de target")

        port = req.port or embedded_port or 80
        return parsed.hostname, port

    def build_cmd(self, req: StressRequest) -> list[str]:
        limited = self.clamp(req)
        self._local_target_url(limited, allow_extra_args=True)
        host, port = self._target_parts(limited)
        if not isinstance(limited.extra_args, (tuple, list)) or any(
            not isinstance(arg, str) or arg not in _ALLOWED_EXTRA_ARGS
            for arg in limited.extra_args
        ):
            raise ValueError("extra_args contém opções não permitidas")

        script_path = (
            config.BASE_DIR.parent / "slowloris" / "slowloris.py"
        ).resolve(strict=True)
        return [
            sys.executable,
            str(script_path),
            host,
            "--port",
            str(port),
            "--sockets",
            str(limited.threads),
            *limited.extra_args,
        ]

    def run(self, req: StressRequest) -> RunResult:
        authorization.require_authorization(req.target)
        limited = self.clamp(req)
        command = self.build_cmd(limited)
        supervised_command = [
            sys.executable,
            "-c",
            _SUPERVISOR,
            str(limited.duration_s),
            *command,
        ]
        return run_subprocess(
            supervised_command,
            cwd=config.BACKEND_DIR,
            timeout_s=limited.duration_s + 5,
        )
