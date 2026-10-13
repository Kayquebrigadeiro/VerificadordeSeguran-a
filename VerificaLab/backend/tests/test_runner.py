from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from verificalab.core import runner


@pytest.fixture
def allowed_cwd(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.setattr(runner, "ALLOWED_CWD_ROOTS", (root,))
    return root


def _active_sleep_pids() -> set[int]:
    active = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            state = stat.rsplit(")", 1)[1].split()[0]
            cmdline = (entry / "cmdline").read_bytes()
        except (OSError, IndexError):
            continue
        if b"sleep\x0030" in cmdline and state != "Z":
            active.add(int(entry.name))
    return active


def test_echo_returns_success_and_timestamps(allowed_cwd):
    result = runner.run_subprocess(["echo", "hello"], allowed_cwd, 5)

    assert result.returncode == 0
    assert result.stdout == "hello\n"
    assert result.started_at <= result.ended_at
    assert not result.timeout


def test_nonzero_exit_is_preserved(allowed_cwd):
    result = runner.run_subprocess(["bash", "-c", "exit 7"], allowed_cwd, 5)

    assert result.returncode == 7


def test_timeout_kills_process(allowed_cwd):
    result = runner.run_subprocess(["sleep", "30"], allowed_cwd, 1)

    assert result.timeout
    assert result.returncode != 0


def test_timeout_kills_child_process_group(allowed_cwd):
    before = _active_sleep_pids()
    result = runner.run_subprocess(["bash", "-c", "sleep 30 & wait"], allowed_cwd, 1)

    assert result.timeout
    assert not (_active_sleep_pids() - before)


def test_large_stdout_is_truncated_at_limit(allowed_cwd):
    result = runner.run_subprocess(
        ["python3", "-c", "print('x' * 1100000)"], allowed_cwd, 10
    )

    assert result.returncode == 0
    assert result.truncated
    assert len(result.stdout.encode()) + len(result.stderr.encode()) == runner.MAX_OUTPUT_BYTES


def test_stderr_is_captured_separately(allowed_cwd):
    result = runner.run_subprocess(
        ["python3", "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        allowed_cwd,
        5,
    )

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_cwd_outside_allowlist_is_rejected(allowed_cwd, tmp_path):
    rejected = tmp_path / "outside"
    rejected.mkdir()

    with pytest.raises(RuntimeError, match="fora das raízes"):
        runner.run_subprocess(["echo", "no"], rejected, 5)


def test_missing_cwd_is_rejected(allowed_cwd):
    with pytest.raises(RuntimeError, match="inexistente"):
        runner.run_subprocess(["echo", "no"], allowed_cwd / "missing", 5)


def test_string_command_is_rejected(allowed_cwd):
    with pytest.raises(TypeError, match="lista de strings"):
        runner.run_subprocess("echo unsafe", allowed_cwd, 5)


def test_cancellation_kills_process_group(allowed_cwd):
    cancel_event = threading.Event()
    before = _active_sleep_pids()
    outcome = {}

    thread = threading.Thread(
        target=lambda: outcome.update(
            runner.run_subprocess(
                ["bash", "-c", "sleep 30 & wait"],
                allowed_cwd,
                20,
                cancel_event=cancel_event,
            ).__dict__
        )
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not (_active_sleep_pids() - before) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert _active_sleep_pids() - before, "o subprocesso filho não iniciou"
    cancel_event.set()
    thread.join(timeout=10)

    assert not thread.is_alive()
    assert outcome["cancelled"]
    assert not (_active_sleep_pids() - before)


def test_environment_is_minimal(allowed_cwd):
    result = runner.run_subprocess(
        ["python3", "-c", "import os; print(','.join(sorted(os.environ)))"],
        allowed_cwd,
        5,
    )

    assert set(result.stdout.strip().split(",")) == {
        "HOME",
        "LC_ALL",
        "PATH",
        "PYTHONUNBUFFERED",
    }


def test_cwd_must_be_directory(allowed_cwd, tmp_path):
    file_path = allowed_cwd / "file"
    file_path.touch()

    with pytest.raises(RuntimeError, match="não é um diretório"):
        runner.run_subprocess(["echo", "no"], file_path, 5)
