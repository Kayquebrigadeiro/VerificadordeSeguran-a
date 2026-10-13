from __future__ import annotations

import json

import pytest

from verificalab import config
from verificalab.core import report
from verificalab.core.orchestrator import Orchestrator


@pytest.fixture
def summary(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "ARTIFACTS_DIR", data_dir / "artifacts")
    monkeypatch.setattr(config, "EXPORTS_DIR", data_dir / "exports")
    return {
        "run_id": "stress_report-123",
        "target": "127.0.0.1:8477",
        "started_at": "2026-10-12T12:00:00+00:00",
        "ended_at": "2026-10-12T12:00:02+00:00",
        "total_duration": 2.0,
        "ok": False,
        "executions": [
            {
                "run_id": "run-1",
                "tool_id": "slowloris",
                "tool_name": "Slowloris",
                "target": "127.0.0.1:8477",
                "started_at": "2026-10-12T12:00:00+00:00",
                "ended_at": "2026-10-12T12:00:02+00:00",
                "returncode": 1,
                "ok": False,
                "total_duration": 2.0,
                "artifact_path": "/data/artifacts/stress_report-123/slowloris.log",
            }
        ],
    }


def test_json_report_is_valid_json(summary):
    path = report.to_json(summary)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == summary["run_id"]
    assert data["executions"][0]["tool_id"] == "slowloris"


def test_json_report_is_created_in_exports(summary):
    path = report.to_json(summary)
    assert path.parent == config.EXPORTS_DIR
    assert path.name == "stress_report-123.json"


def test_markdown_contains_executed_tool_names(summary):
    path = report.to_markdown(summary)
    assert "Slowloris" in path.read_text(encoding="utf-8")


def test_markdown_includes_result_and_limitations(summary):
    text = report.to_markdown(summary).read_text(encoding="utf-8")
    assert "Resultado geral:** Falha" in text
    assert "Limitações" in text
    assert "loopback" in text


def test_html_contains_document_and_execution_data(summary):
    text = report.to_html(summary).read_text(encoding="utf-8")
    assert "<html" in text
    assert "Slowloris" in text
    assert "127.0.0.1:8477" in text
    assert "Falha" in text


def test_html_escapes_untrusted_tool_names(summary):
    summary["executions"][0]["tool_name"] = "<script>alert(1)</script>"
    text = report.to_html(summary).read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_all_formats_include_limitation_section(summary):
    json_data = json.loads(report.to_json(summary).read_text(encoding="utf-8"))
    markdown = report.to_markdown(summary).read_text(encoding="utf-8")
    html_text = report.to_html(summary).read_text(encoding="utf-8")
    assert any("loopback" in item for item in json_data["limitations"])
    assert "## Limitações" in markdown
    assert "<h2>Limitações</h2>" in html_text
    assert any("amplificação" in item for item in json_data["limitations"])


def test_reports_redact_registered_secret(summary):
    from verificalab.security import register_secret

    register_secret("segredo-relatorio-987")
    summary["target"] = "http://127.0.0.1?token=segredo-relatorio-987"
    json_text = report.to_json(summary).read_text(encoding="utf-8")
    markdown_text = report.to_markdown(summary).read_text(encoding="utf-8")
    html_text = report.to_html(summary).read_text(encoding="utf-8")
    assert "segredo-relatorio-987" not in json_text + markdown_text + html_text
    assert "***" in json_text


def test_report_rejects_path_traversal_run_id(summary):
    summary["run_id"] = "../outside"
    with pytest.raises(ValueError, match="run_id"):
        report.to_json(summary)


def test_report_accepts_orchestrator_summary_object(summary):
    from datetime import datetime, timezone
    from verificalab.core.orchestrator import RunSummary, ToolRunSummary

    execution = summary["executions"][0]
    item = ToolRunSummary(
        run_id=execution["run_id"],
        tool_id=execution["tool_id"],
        tool_name=execution["tool_name"],
        target=execution["target"],
        started_at=datetime.fromisoformat(execution["started_at"]),
        ended_at=datetime.fromisoformat(execution["ended_at"]),
        returncode=execution["returncode"],
        ok=execution["ok"],
        artifact_path=execution["artifact_path"],
    )
    value = RunSummary(
        run_id=summary["run_id"],
        target=summary["target"],
        started_at=datetime(2026, 10, 12, 12, tzinfo=timezone.utc),
        ended_at=datetime(2026, 10, 12, 12, 0, 2, tzinfo=timezone.utc),
        executions=(item,),
    )
    assert report.to_json(value).exists()
