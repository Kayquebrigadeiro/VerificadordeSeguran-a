from __future__ import annotations

import time

import pytest

from verificalab.core.authorization import AuthorizationError
from verificalab.core.runner import RunResult
from verificalab.stress.adapters.slowloris import SlowlorisAdapter
from verificalab.stress.base import StressRequest

from tests.fixtures.local_http import local_http


@pytest.fixture
def adapter() -> SlowlorisAdapter:
    return SlowlorisAdapter()


def test_clamp_limits_duration_to_catalog_maximum(adapter):
    request = adapter.clamp(StressRequest("localhost", duration_s=999))

    assert request.duration_s == 30


def test_clamp_limits_threads_to_catalog_maximum(adapter):
    request = adapter.clamp(StressRequest("localhost", threads=999))

    assert request.threads == 50


def test_clamp_never_increases_duration(adapter):
    request = adapter.clamp(StressRequest("localhost", duration_s=5))

    assert request.duration_s == 5


def test_clamp_never_increases_threads(adapter):
    request = adapter.clamp(StressRequest("localhost", threads=1))

    assert request.threads == 1


def test_build_cmd_targets_localhost(adapter):
    command = adapter.build_cmd(
        StressRequest("localhost", duration_s=3, threads=10, port=8477)
    )

    assert command[1].endswith("/slowloris/slowloris.py")
    assert command[2:] == [
        "localhost",
        "--port",
        "8477",
        "--sockets",
        "10",
    ]


def test_build_cmd_extracts_port_from_target(adapter):
    command = adapter.build_cmd(
        StressRequest("127.0.0.1:8477", duration_s=3, threads=10)
    )

    assert command[2:6] == ["127.0.0.1", "--port", "8477", "--sockets"]
    assert command[6] == "10"


def test_run_rejects_external_target_without_authorization(adapter, monkeypatch):
    from verificalab.core import authorization

    monkeypatch.setattr(
        authorization.config, "AUTHORIZATION_FILE", authorization.config.DATA_DIR / "missing.json"
    )
    with pytest.raises(AuthorizationError):
        adapter.run(StressRequest("example.com", duration_s=1, threads=1))


def test_run_executes_against_real_local_lab(adapter, local_http):
    result = adapter.run(
        StressRequest(local_http.target, duration_s=2, threads=10)
    )
    log_lines = local_http.new_log_lines()

    assert isinstance(result, RunResult)
    assert result.returncode == 0
    assert "KeyboardInterrupt" not in result.stderr
    assert "[lab] TCP 127.0.0.1" in log_lines


def test_run_stops_after_requested_duration(adapter, local_http):
    started_at = time.monotonic()
    result = adapter.run(
        StressRequest(local_http.target, duration_s=1, threads=4)
    )
    elapsed = time.monotonic() - started_at

    assert result.returncode == 0
    assert not result.timeout
    assert elapsed >= 1
    assert elapsed < 4
