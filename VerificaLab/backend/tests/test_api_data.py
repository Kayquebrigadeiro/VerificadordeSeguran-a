"""Dados: logs, importações, artefatos, segredos, XSS e comparação."""

from __future__ import annotations

from .test_api_flow import make_project_env, wait_run


def test_log_upload_parse_and_correlation(client, csrf_headers, unique,
                                          lab_server):
    from datetime import datetime, timedelta

    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"c-log-{unique}", "kind": "http",
        "config": {"checks": [{"name": "ok", "type": "status", "path": "/ok",
                               "expected_status": 201}],
                   "include_config_checks": False, "timeout_s": 5}},
        headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    data = wait_run(client, run["id"], timeout=60)
    assert data["run"]["state"] == "failed"

    start = datetime.fromisoformat(data["run"]["started_at"])
    t1 = (start + timedelta(seconds=1)).isoformat()
    t2 = (start + timedelta(seconds=2)).isoformat()
    log = (
        f'{t1} INFO servico iniciado\n'
        f'{t2} ERROR falha 500 na rota /ok request_id=abc12345\n'
        'linha sem data\n'
        'X-Powered-By: Express\n'
    ).encode()
    res = client.post(f"/api/environments/{env['id']}/logs?filename=app.log",
                      content=log, headers=csrf_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["entries"] == 4 and body["sha256"]

    entries = client.get(f"/api/environments/{env['id']}/logs").json()
    assert entries["total"] == 4

    corr = client.post(f"/api/runs/{run['id']}/correlate",
                       headers=csrf_headers).json()
    assert corr["available"] is True
    assert corr["entries_in_window"] >= 2
    detail = client.get(f"/api/runs/{run['id']}").json()
    hyp = [f for f in detail["findings"] if f["hypothesis"] == 1]
    assert hyp, "esperava hipótese de correlação temporal"
    assert "hipótese" in hyp[0]["description"].lower()


def test_import_junit_attach_and_malformed(client, csrf_headers, unique):
    junit = (b'<?xml version="1.0"?><testsuite name="s" tests="2" '
            b'failures="1"><testcase classname="t" name="a"/>'
            b'<testcase classname="t" name="b"><failure message="x"/>'
            b'</testcase></testsuite>')
    r = client.post("/api/imports?format=junit-xml&filename=j.xml",
                    content=junit, headers=csrf_headers)
    assert r.status_code == 201
    imp = r.json()
    assert imp["records"] == 2 and imp["attached_to_run"] is None

    r2 = client.post("/api/imports?format=junit-xml",
                     content=b"<?xml version='1.0'?><testsuite><x",
                     headers=csrf_headers)
    assert r2.status_code == 422
    r3 = client.post("/api/imports?format=json",
                     content=b'{"nao": "e lista"}', headers=csrf_headers)
    assert r3.status_code == 422

    detail = client.get(f"/api/imports/{imp['id']}").json()
    assert detail["records_detail"] is not None


def test_artifact_path_traversal_blocked(client, csrf_headers, unique):
    """Upload nunca escolhe destino; rel_path indevido é recusado."""
    from verificalab.db import utcnow
    from verificalab.ids import new_id

    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"p-art-{unique}", "kind": "http",
        "config": {"checks": [{"name": "ok", "type": "status", "path": "/ok",
                               "expected_status": 200}],
                   "include_config_checks": False, "timeout_s": 5}},
        headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    wait_run(client, run["id"], timeout=60)
    db = client.app.state.db
    art_id = new_id("art")
    db.insert("artifacts", {
        "id": art_id, "run_id": run["id"], "kind": "file",
        "filename": "evil.txt", "rel_path": "../../etc/passwd",
        "sha256": "0" * 64, "size": 1, "preview": "", "created_at": utcnow()})
    r = client.get(f"/api/artifacts/{art_id}/download")
    assert r.status_code == 400

def test_secret_never_exposed(client, csrf_headers, unique):
    prj = client.post("/api/projects", json={"name": f"p-sec-{unique}"},
                      headers=csrf_headers).json()
    env = client.post("/api/environments", json={
        "project_id": prj["id"], "name": f"sec-{unique}",
        "endpoint": "http://127.0.0.1:8479", "kind": "lab",
        "secret_header_name": "X-Api-Key",
        "secret_header_value": "super-secreto-demo-999"},
        headers=csrf_headers).json()
    listing = client.get(f"/api/environments?project_id={prj['id']}").json()
    assert "super-secreto-demo-999" not in str(listing)
    assert listing["environments"][0]["has_secret"] is True
    db_bytes = client.app.state.db.path.read_bytes()
    assert b"super-secreto-demo-999" not in db_bytes  # cifrado em arquivo à parte


def test_xss_escaped_in_html_report(client, csrf_headers, unique, lab_server):
    payload = "<img src=x onerror=alert(1)>"
    prj, env = make_project_env(client, csrf_headers, unique)
    profile = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"xss-{unique}", "kind": "http",
        "config": {"checks": [{"name": payload, "type": "status", "path": "/ok",
                               "expected_status": 200}],
                   "include_config_checks": False, "timeout_s": 5}},
        headers=csrf_headers).json()
    run = client.post("/api/runs", json={"profile_id": profile["id"],
                                         "environment_id": env["id"]},
                      headers=csrf_headers).json()
    wait_run(client, run["id"], timeout=60)
    html = client.get(f"/api/runs/{run['id']}/report?format=html").text
    assert "<img src=x" not in html
    assert "&lt;img" in html


def test_compare_two_runs(client, csrf_headers, unique, lab_server):
    prj, env = make_project_env(client, csrf_headers, unique)
    p_bad = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"cmp-bad-{unique}", "kind": "http",
        "config": {"checks": [{"name": "c1", "type": "status", "path": "/ok",
                               "expected_status": 201}],
                   "include_config_checks": False, "timeout_s": 5}},
        headers=csrf_headers).json()
    p_good = client.post("/api/profiles", json={
        "project_id": prj["id"], "name": f"cmp-good-{unique}", "kind": "http",
        "config": {"checks": [{"name": "c1", "type": "status", "path": "/ok",
                               "expected_status": 200}],
                   "include_config_checks": False, "timeout_s": 5}},
        headers=csrf_headers).json()
    r_bad = client.post("/api/runs", json={"profile_id": p_bad["id"],
                                           "environment_id": env["id"]},
                        headers=csrf_headers).json()
    r_good = client.post("/api/runs", json={"profile_id": p_good["id"],
                                            "environment_id": env["id"]},
                         headers=csrf_headers).json()
    wait_run(client, r_bad["id"], timeout=60)
    wait_run(client, r_good["id"], timeout=60)
    cmp = client.get(f"/api/compare?a={r_bad['id']}&b={r_good['id']}").json()
    assert cmp["checks"]["c1"]["change"] == "melhorou"
    assert cmp["state_change"] == "failed -> passed"


def test_audit_trail_exists(client):
    events = client.get("/api/audit?limit=10").json()["events"]
    assert events, "esperava eventos de auditoria"
