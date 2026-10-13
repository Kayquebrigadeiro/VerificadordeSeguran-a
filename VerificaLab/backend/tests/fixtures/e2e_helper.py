"""Helpers para o E2E real de stress restrito ao loopback."""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.request import urlopen

from verificalab.labapp import LabHandler

_TOOL_PROCESS = re.compile(r"slowloris|ddoslayer|mhddos", re.IGNORECASE)


class _ConnectionCountingHandler(LabHandler):
    def setup(self) -> None:
        super().setup()
        server = self.server
        with server.connection_lock:
            server.connection_count += 1


class _CountingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self) -> None:
        self.connection_count = 0
        self.connection_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), _ConnectionCountingHandler)


@dataclass(frozen=True, slots=True)
class RunningLab:
    target: str
    server: _CountingHTTPServer
    thread: threading.Thread

    @property
    def connection_count(self) -> int:
        with self.server.connection_lock:
            return self.server.connection_count

    def check_ok(self) -> bytes:
        with urlopen(f"http://{self.target}/ok", timeout=3) as response:
            if response.status != 200:
                raise AssertionError(f"/ok retornou HTTP {response.status}")
            return response.read()


@contextmanager
def start_local_lab() -> Iterator[RunningLab]:
    """Sobe o handler HTTP real em uma porta loopback livre e sempre o encerra."""
    server = _CountingHTTPServer()
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, name="e2e-local-lab")
    thread.start()
    lab = RunningLab(target=f"{host}:{port}", server=server, thread=thread)
    try:
        yield lab
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        if thread.is_alive():
            raise RuntimeError("thread do laboratório E2E não encerrou")


def count_tool_processes(proc_root: Path = Path("/proc")) -> int:
    """Conta processos Slowloris, DDoSlayer ou MHDDoS por seus argumentos."""
    count = 0
    for process in proc_root.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            command = (process / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8",
                errors="replace",
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if _TOOL_PROCESS.search(command):
            count += 1
    return count
