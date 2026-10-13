"""Fixture de acesso ao laboratório HTTP real iniciado pela suíte."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from verificalab import config


@dataclass(frozen=True)
class LocalHTTPLab:
    target: str
    log_path: Path
    log_offset: int

    def new_log_lines(self) -> str:
        if not self.log_path.exists():
            return ""
        with self.log_path.open("r", encoding="utf-8", errors="replace") as log:
            log.seek(self.log_offset)
            return log.read()


@pytest.fixture
def local_http(lab_server) -> LocalHTTPLab:
    log_path = config.LOGS_DIR / "lab.log"
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    return LocalHTTPLab(
        target=f"{config.LAB_HOST}:{config.LAB_PORT}",
        log_path=log_path,
        log_offset=log_offset,
    )
