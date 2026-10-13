"""Fluxo integrado via API: CSRF, cadastro, execução e exportação."""

from __future__ import annotations

import time

FINAL = {"passed", "failed", "cancelled", "timed_out", "interrupted", "error"}


def wait_run(client, run_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/runs/{run_id}").json()
        if data["run"]["state"] in FINAL:
            return data
        time.sleep(0.5)
    raise AssertionError(f"execução {run_id} não finalizou em {timeout}s")


def make_project_env(client, headers, unique, endpoint="http://127.0.0.1:8479"):
    prj = client.post("/api/projects", json={
        "name": f"proj-{unique}",
        "description": "teste"}, headers=headers).json()
    env = client.post("/api/environments", json={
        "project_id": prj["id"], "name": f"env-{unique}",
        "endpoint": endpoint, "kind": "lab"}, headers=headers).json()
    return prj, env


def test_session_and_health(client):
    s = client.get("/api/session").json()
    assert s["csrf_token"] and s["limits"]["load_max_rps"] == 5.0
    h = client.get("/api/health").json()
    assert h["ok"] is True


def test_mutation_without_csrf_rejected(client):
    r = client.post("/api/projects", json={"name": "x"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_mutation_with_foreign_origin_rejected(client, csrf_headers):
    r = client.post("/api/projects", json={"name": "x"},
                    headers={**csrf_headers, "Origin": "http://evil.example"})
    assert r.status_code == 403


def test_non_loopback_host_rejected(client):
    r = client.get("/api/health", headers={"Host": "evil.example"})
    assert r.status_code == 403


def test_environment_non_loopback_endpoint_rejected(client, csrf_headers, unique):
    prj = client.post("/api/projects", json={"name": f"p-{unique}"},
                      headers=csrf_headers).json()
    for endpoint in ("http://example.com", "http://192.168.0.10:80",
                     "http://localhost:8479", "http://user:pw@127.0.0.1:1"):
        r = client.post("/api/environments", json={
            "project_id": prj["id"], "name": f"e-{endpoint[-5:]}",
            "endpoint": endpoint}, headers=csrf_headers)
        assert r.status_code == 422, endpoint


def test_load_profile_manipulation_rejected(client, csrf_headers, unique):
    prj, env = make_project_env(client, csrf_headers, unique)
    r = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": "carga-ilegal", "kind": "load",
        "config": {"rps": 100, "duration_s": 600, "concurrency": 50,
                   "max_attempts": 99999, "method": "POST"}},
        headers=csrf_headers)
    assert r.status_code == 422


def test_http_flow_with_intentional_failures(client, csrf_headers, unique,
                                             lab_server):
    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"contrato-{unique}", "kind": "http",
        "config": {
            "checks": [
                {"name": "ok", "type": "status", "path": "/ok",
                 "expected_status": 200},
                {"name": "intencional_201", "type": "status", "path": "/ok",
                 "expected_status": 201},
                {"name": "redirect_ext", "type": "status",
                 "path": "/redirect-external", "expected_status": 200},
            ],
            "include_config_checks": True, "timeout_s": 5,
        }}, headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    data = wait_run(client, run["id"])
    by_name = {c["name"]: c["status"] for c in data["checks"]}
    # estado failed, falhas REAIS visíveis (não mascaradas)
    assert data["run"]["state"] == "failed"
    assert by_name["ok"] == "pass"
    assert by_name["intencional_201"] == "fail"
    assert by_name["redirect_ext"] == "fail"
    redirect_check = next(c for c in data["checks"] if c["name"] == "redirect_ext")
    assert "redirect recusado" in redirect_check["message"]
    assert any(f["severity"] == "info" for f in data["findings"])
    latency = next(m for m in data["metrics"] if m["name"].startswith("latency"))
    assert latency["samples"] >= 1 and latency["population"]
    rep = client.get(f"/api/runs/{run['id']}/report?format=json").json()
    assert rep["limitations"] and rep["run"]["state"] == "failed"
    html = client.get(f"/api/runs/{run['id']}/report?format=html").text
    assert "intencional_201" in html and "s-fail" in html
    corr = client.post(f"/api/runs/{run['id']}/correlate",
                       headers=csrf_headers).json()
    assert corr["available"] is True
