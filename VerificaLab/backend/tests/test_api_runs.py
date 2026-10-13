"""Orçamento de carga, cancelamento na fila/ativo e recuperação pós-reinício."""

from __future__ import annotations

import json as _json
import time

from .test_api_flow import make_project_env, wait_run


def test_load_run_respects_budget(client, csrf_headers, unique, lab_server):
    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"carga-{unique}", "kind": "load",
        "config": {"path": "/ok", "rps": 5, "duration_s": 2,
                   "concurrency": 2, "max_attempts": 6, "timeout_s": 3,
                   "expect_status": 200}}, headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    data = wait_run(client, run["id"], timeout=60)
    assert data["run"]["state"] == "passed"
    failed_metric = next(m for m in data["metrics"]
                         if m["name"].startswith("count"))
    details = failed_metric["details"]
    total = (details["ok"] + details["bad_status"] + details["timeout"]
             + details["connection_error"] + details["other_error"])
    assert total <= 6  # orçamento nunca excedido


def test_cancel_running_run(client, csrf_headers, unique, lab_server):
    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"carga-longa-{unique}", "kind": "load",
        "config": {"path": "/ok", "rps": 1, "duration_s": 25,
                   "concurrency": 1, "max_attempts": 25, "timeout_s": 5,
                   "expect_status": 200}}, headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    for _ in range(100):
        state = client.get(f"/api/runs/{run['id']}").json()["run"]["state"]
        if state == "running":
            break
        time.sleep(0.3)
    r = client.post(f"/api/runs/{run['id']}/cancel", headers=csrf_headers)
    assert r.json()["status"] in ("cancelling", "cancelled")
    data = wait_run(client, run["id"], timeout=60)
    assert data["run"]["state"] == "cancelled"


def test_cancel_queued_run(client, csrf_headers, unique, lab_server):
    prj, env = make_project_env(client, csrf_headers, unique)
    profiles = []
    for i in range(2):
        profiles.append(client.post("/api/profiles", json={
            "project_id": prj["id"], "name": f"fila-{unique}-{i}",
            "kind": "load",
            "config": {"path": "/ok", "rps": 1, "duration_s": 8,
                       "concurrency": 1, "max_attempts": 8, "timeout_s": 3,
                       "expect_status": 200}}, headers=csrf_headers).json())
    r1 = client.post("/api/runs", json={"profile_id": profiles[0]["id"],
                                        "environment_id": env["id"]},
                     headers=csrf_headers).json()
    r2 = client.post("/api/runs", json={"profile_id": profiles[1]["id"],
                                        "environment_id": env["id"]},
                     headers=csrf_headers).json()
    res = client.post(f"/api/runs/{r2['id']}/cancel", headers=csrf_headers).json()
    assert res["status"] in ("cancelled", "cancelling")
    data2 = wait_run(client, r2["id"], timeout=60)
    assert data2["run"]["state"] == "cancelled"
    wait_run(client, r1["id"], timeout=90)


def test_restart_recovery_marks_interrupted(client, csrf_headers, unique):
    """Reinício: running -> interrupted, nunca aprovada."""
    from verificalab.db import utcnow
    from verificalab.ids import new_id
    from verificalab.worker import Worker

    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"rec-{unique}", "kind": "load",
        "config": {"path": "/ok"}}, headers=csrf_headers).json()
    fake_id = new_id("run")
    db = client.app.state.db
    db.insert("runs", {
        "id": fake_id, "project_id": prj["id"], "environment_id": env["id"],
        "profile_id": profile["id"], "kind": "load", "state": "running",
        "queued_at": utcnow(), "started_at": utcnow(),
        "config_json": _json.dumps({"profile_kind": "load",
                                    "profile_config": {}}),
    })
    Worker(db).recover_interrupted()
    data = client.get(f"/api/runs/{fake_id}").json()
    assert data["run"]["state"] == "interrupted"
    assert data["run"]["interrupted_reason"]
