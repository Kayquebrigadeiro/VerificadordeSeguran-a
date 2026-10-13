from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser

import pytest

from verificalab import config
from verificalab.core.authorization import AuthorizationError, require_authorization
from verificalab.core.orchestrator import Orchestrator
from verificalab.db import Database
from verificalab.stress.registry import ToolRegistry
from tests.fixtures.e2e_helper import count_tool_processes, start_local_lab


class _HTMLDocumentParser(HTMLParser):
    pass


def test_e2e_full_flow():
    processes_before = count_tool_processes()
    assert processes_before == 0

    processes_after = None
    processes_after_wait = None
    try:
        with start_local_lab() as lab:
            response = lab.check_ok()
            assert b'"status": "ok"' in response
            connections_after_healthcheck = lab.connection_count
            assert connections_after_healthcheck >= 1

            auth = require_authorization(lab.target)
            with pytest.raises(AuthorizationError):
                require_authorization("example.com")

            data_dir = config.DATA_DIR
            db = Database(data_dir / "e2e-stress.sqlite3")
            try:
                orchestrator = Orchestrator(registry=ToolRegistry.load(), db=db)
                plan = orchestrator.plan(
                    lab.target,
                    ["slowloris"],
                    duration_s=3,
                    threads=10,
                )
                assert plan.tools[0].duration_s == 3
                assert plan.tools[0].threads == 10
                summary = orchestrator.run(plan, auth)
                persisted = db.one(
                    "SELECT config_json FROM runs WHERE orchestrator_id = ?",
                    (summary.run_id,),
                )
                persisted_config = json.loads(persisted["config_json"])
                assert persisted_config["duration_s"] == 3
                assert persisted_config["threads"] == 10
            finally:
                db.close()

            assert summary.ok is True
            assert lab.connection_count > connections_after_healthcheck
            artifact = config.ARTIFACTS_DIR / summary.run_id / "slowloris.log"
            assert artifact.is_file()
            assert artifact.stat().st_size > 0
            assert b"10 sockets" in artifact.read_bytes()

            report_paths = dict(summary.report_paths)
            assert set(report_paths) == {"json", "markdown", "html"}
            json_path = config.EXPORTS_DIR / f"{summary.run_id}.json"
            markdown_path = config.EXPORTS_DIR / f"{summary.run_id}.md"
            html_path = config.EXPORTS_DIR / f"{summary.run_id}.html"
            assert all(path.is_file() for path in (json_path, markdown_path, html_path))
            report_data = json.loads(json_path.read_text(encoding="utf-8"))
            assert report_data["executions"][0]["tool_name"] == "Slowloris"
            assert "Slowloris" in markdown_path.read_text(encoding="utf-8")

            html_report = html_path.read_text(encoding="utf-8")
            assert "Slowloris" in html_report
            assert lab.target in html_report
            assert re.search(r"<dt>Duração total</dt><dd>[^<]+ s</dd>", html_report)
            _HTMLDocumentParser().feed(html_report)
    finally:
        processes_after = count_tool_processes()
        time.sleep(2)
        processes_after_wait = count_tool_processes()

    assert processes_before == 0
    assert processes_after == 0
    assert processes_after_wait == 0
