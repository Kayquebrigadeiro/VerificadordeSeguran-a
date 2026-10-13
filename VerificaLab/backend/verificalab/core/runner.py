"""Execução segura de subprocessos com limite de saída e encerramento em árvore."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .. import config

MAX_OUTPUT_BYTES = config.SUITE_MAX_OUTPUT_BYTES
KILL_GRACE_S = config.SUITE_KILL_GRACE_S
ALLOWED_CWD_ROOTS = (config.BACKEND_DIR, config.SUITE_PROJECTS_DIR)
RUNNER_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


@dataclass(frozen=True)
class RunResult:
    started_at: datetime
    ended_at: datetime
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False
    cancelled: bool = False
    truncated: bool = False


def _validated_cwd(cwd: Path) -> Path:
    try:
        resolved = Path(cwd).resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise RuntimeError(f"cwd inválido ou inexistente: {cwd}") from exc
    if not resolved.is_dir():
        raise RuntimeError(f"cwd não é um diretório: {resolved}")

    roots = []
    for root in ALLOWED_CWD_ROOTS:
        try:
            roots.append(Path(root).resolve(strict=True))
        except (OSError, RuntimeError):
            continue
    if not any(resolved.is_relative_to(root) for root in roots):
        raise RuntimeError(f"cwd fora das raízes permitidas: {resolved}")
    return resolved


def _kill_process_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def run_subprocess(
    cmd: list[str],
    cwd: Path,
    timeout_s: int,
    cancel_event: threading.Event | None = None,
) -> RunResult:
    """Executa ``cmd`` sem shell e encerra todo o grupo em timeout/cancelamento."""
    if not isinstance(cmd, list):
        raise TypeError("cmd deve ser uma lista de strings")
    if not cmd or any(not isinstance(arg, str) for arg in cmd):
        raise TypeError("cmd deve ser uma lista não vazia de strings")
    if any("\x00" in arg for arg in cmd):
        raise ValueError("cmd não pode conter bytes nulos")
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or timeout_s <= 0:
        raise ValueError("timeout_s deve ser um inteiro positivo")
    if cancel_event is not None and not isinstance(cancel_event, threading.Event):
        raise TypeError("cancel_event deve ser threading.Event ou None")

    resolved_cwd = _validated_cwd(cwd)
    started_at = datetime.now(timezone.utc)
    proc = subprocess.Popen(
        cmd,
        cwd=resolved_cwd,
        env={
            "PATH": RUNNER_PATH,
            "HOME": str(resolved_cwd),
            "LC_ALL": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    output_lock = threading.Lock()
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    captured_bytes = 0
    truncated = False

    def drain(stream_name: str, stream) -> None:
        nonlocal captured_bytes, truncated
        for chunk in iter(lambda: stream.read(4096), b""):
            with output_lock:
                available = max(0, MAX_OUTPUT_BYTES - captured_bytes)
                kept = chunk[:available]
                if kept:
                    outputs[stream_name].extend(kept)
                    captured_bytes += len(kept)
                if len(kept) != len(chunk):
                    truncated = True

    assert proc.stdout is not None and proc.stderr is not None
    readers = (
        threading.Thread(target=drain, args=("stdout", proc.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", proc.stderr), daemon=True),
    )
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout_s
    timed_out = False
    cancelled = False
    while proc.poll() is None or any(reader.is_alive() for reader in readers):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            _kill_process_group(proc)
            break
        if time.monotonic() >= deadline:
            timed_out = True
            _kill_process_group(proc)
            break
        time.sleep(0.05)

    returncode = proc.wait()
    for reader in readers:
        reader.join()
    ended_at = datetime.now(timezone.utc)

    return RunResult(
        started_at=started_at,
        ended_at=ended_at,
        returncode=returncode,
        stdout=outputs["stdout"].decode("utf-8", errors="replace"),
        stderr=outputs["stderr"].decode("utf-8", errors="replace"),
        timeout=timed_out,
        cancelled=cancelled,
        truncated=truncated,
    )
