from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from verificalab import config
from verificalab.core import orchestrator
from verificalab.core.authorization import AuthorizationError
from verificalab.core.orchestrator import Orchestrator
from verificalab.core.runner import RunResult
from verificalab.db import Database
from verificalab.worker import Worker


class FakeAdapter:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


def _result(returncode=0, stdout="stdout", stderr=""):
    now = datetime.now(timezone.utc)
    return RunResult(
        started_at=now,
        ended_at=now,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.fixture
def harness(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    artifacts_dir = data_dir / "artifacts"
    exports_dir = data_dir / "exports"
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setattr(config, "EXPORTS_DIR", exports_dir)
    db = Database(data_dir / "test.sqlite3")
    app = Orchestrator(db=db)
    adapters = {}

    def adapter_for(tool_id):
        return adapters[tool_id]

    monkeypatch.setattr(app, "_adapter_for", adapter_for)
    yield app, adapters, db
    db.close()


def test_plan_with_one_registered_tool_has_one_entry(harness):
    app, _, _ = harness
    plan = app.plan("127.0.0.1:8477", ["slowloris"])
    assert len(plan.tools) == 1
    assert plan.tools[0].tool_id == "slowloris"


def test_plan_accepts_overrides_within_catalog_limits(harness):
    app, _, _ = harness
    plan = app.plan("127.0.0.1:8477", ["slowloris"], duration_s=3, threads=10)
    assert plan.tools[0].duration_s == 3
    assert plan.tools[0].threads == 10


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"duration_s": 31}, "duration_s"),
        ({"threads": 51}, "threads"),
        ({"duration_s": True}, "duration_s"),
        ({"threads": 0}, "threads"),
    ],
)
def test_plan_rejects_overrides_outside_catalog_limits(harness, overrides, message):
    app, _, _ = harness
    with pytest.raises(ValueError, match=message):
        app.plan("127.0.0.1:8477", ["slowloris"], **overrides)


def test_plan_with_three_registered_tools_has_three_entries(harness):
    app, adapters, _ = harness
    adapters["slowloris"] = FakeAdapter(_result())
    adapters["mikumikubeam"] = FakeAdapter(_result())
    adapters["pyddos"] = FakeAdapter(_result())
    plan = app.plan("127.0.0.1:8477", ["slowloris", "mikumikubeam", "pyddos"])
    assert [entry.tool_id for entry in plan.tools] == ["slowloris", "mikumikubeam", "pyddos"]


def test_plan_rejects_an_unregistered_tool(harness):
    app, _, _ = harness
    with pytest.raises(ValueError, match="não registrada"):
        app.plan("127.0.0.1:8477", ["unknown-tool"])


def test_plan_rejects_unsafe_or_malformed_target(harness):
    app, _, _ = harness
    with pytest.raises(ValueError, match="target"):
        app.plan("http://user:password@127.0.0.1:8477", ["slowloris"])


def test_plan_rejects_duplicate_tool_ids(harness):
    app, _, _ = harness
    with pytest.raises(ValueError, match="duplicados"):
        app.plan("127.0.0.1:8477", ["slowloris", "slowloris"])


def test_cancel_delegates_to_worker(harness):
    _, _, db = harness
    worker = Mock(spec=Worker)
    worker.request_cancel.return_value = ("cancelling", "cancelamento solicitado")
    app = Orchestrator(db=db, worker=worker)

    assert app.cancel("run_123") == ("cancelling", "cancelamento solicitado")
    worker.request_cancel.assert_called_once_with("run_123")


def test_cancel_nonexistent_run_returns_not_found(harness):
    _, _, db = harness
    app = Orchestrator(db=db, worker=Worker(db))

    assert app.cancel("run_inexistente") == ("not_found", "execução inexistente")


def test_cancel_without_worker_raises(harness):
    app, _, _ = harness

    with pytest.raises(RuntimeError, match="Orchestrator\\(worker=worker\\)"):
        app.cancel("run_123")


def test_invalid_authorization_aborts_before_adapter_or_database_run(harness):
    app, adapters, db = harness
    adapters["slowloris"] = FakeAdapter(_result())
    plan = app.plan("127.0.0.1:8477", ["slowloris"])
    with pytest.raises(AuthorizationError, match="auth deve"):
        app.run(plan, auth="invalid")
    assert adapters["slowloris"].requests == []
    assert db.one("SELECT id FROM runs") is None


def test_failing_adapter_does_not_prevent_later_tools(harness):
    app, adapters, db = harness
    adapters["slowloris"] = FakeAdapter(error=RuntimeError("adapter failed"))
    adapters["mikumikubeam"] = FakeAdapter(_result())
    plan = app.plan("127.0.0.1:8477", ["slowloris", "mikumikubeam"])
    summary = app.run(plan)
    assert summary.ok is False
    assert [item.ok for item in summary.executions] == [False, True]
    assert len(adapters["mikumikubeam"].requests) == 1
    assert db.one("SELECT COUNT(*) AS n FROM runs")["n"] == 2


def test_run_saves_stdout_and_stderr_artifact(harness):
    app, adapters, _ = harness
    adapters["slowloris"] = FakeAdapter(_result(stdout="hello", stderr="warning"))
    summary = app.run(app.plan("127.0.0.1:8477", ["slowloris"]))
    artifact = config.ARTIFACTS_DIR / summary.run_id / "slowloris.log"
    contents = artifact.read_text(encoding="utf-8")
    assert "stdout:\nhello" in contents
    assert "stderr:\nwarning" in contents


def test_summary_contains_timestamps_duration_and_overall_status(harness):
    app, adapters, _ = harness
    adapters["slowloris"] = FakeAdapter(_result())
    summary = app.run(app.plan("127.0.0.1:8477", ["slowloris"]))
    assert summary.started_at.tzinfo is not None
    assert summary.ended_at >= summary.started_at
    assert summary.total_duration >= 0
    assert summary.ok is True


def test_each_execution_is_persisted_with_required_fields(harness):
    app, adapters, db = harness
    adapters["slowloris"] = FakeAdapter(_result(returncode=7))
    summary = app.run(app.plan("127.0.0.1:8477", ["slowloris"]))
    row = db.one("SELECT * FROM runs WHERE orchestrator_id = ?", (summary.run_id,))
    assert row["tool_id"] == "slowloris"
    assert row["target"] == "127.0.0.1:8477"
    assert row["started_at"] and row["ended_at"]
    assert row["returncode"] == 7
    assert row["ok"] == 0


def test_check_result_and_artifact_metadata_are_recorded(harness):
    app, adapters, db = harness
    adapters["slowloris"] = FakeAdapter(_result())
    summary = app.run(app.plan("127.0.0.1:8477", ["slowloris"]))
    execution = summary.executions[0]
    check = db.one("SELECT * FROM check_results WHERE run_id = ?", (execution.run_id,))
    artifact = db.one("SELECT * FROM artifacts WHERE run_id = ?", (execution.run_id,))
    assert check["status"] == "pass"
    assert artifact["filename"] == "slowloris.log"
    assert artifact["size"] > 0
    assert len(artifact["sha256"]) == 64


def test_tool_specific_limits_are_passed_to_each_adapter(harness):
    app, adapters, _ = harness
    adapters["slowloris"] = FakeAdapter(_result())
    plan = app.plan("127.0.0.1:8477", ["slowloris"])
    app.run(plan)
    request = adapters["slowloris"].requests[0]
    assert request.duration_s == plan.tools[0].duration_s
    assert request.threads == plan.tools[0].threads


def test_run_generates_all_report_formats(harness):
    app, adapters, _ = harness
    adapters["slowloris"] = FakeAdapter(_result())
    summary = app.run(app.plan("127.0.0.1:8477", ["slowloris"]))
    paths = dict(summary.report_paths)
    assert set(paths) == {"json", "markdown", "html"}
    assert all(Path(path).is_file() for path in paths.values())
