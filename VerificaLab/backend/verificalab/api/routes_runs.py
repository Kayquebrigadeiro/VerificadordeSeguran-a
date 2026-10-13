"""Rotas: perfis, execuções, fila, cancelamento, relatório, laboratório."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from .. import __version__, labctl
from ..analysis.correlate import correlate_run
from ..analysis.report import build_report, render_html
from ..db import utcnow
from ..ids import new_id
from ..models import ProfileIn, RunIn
from .helpers import profile_out, row_or_404, run_out

router = APIRouter(prefix="/api")


def _db(request: Request):
    return request.app.state.db


# ------------------------------------------------------------------ perfis
@router.get("/profiles")
def list_profiles(request: Request, project_id: str | None = None) -> dict:
    db = _db(request)
    if project_id:
        rows = db.query("SELECT * FROM test_profiles WHERE project_id = ? "
                        "ORDER BY created_at", (project_id,))
    else:
        rows = db.query("SELECT * FROM test_profiles ORDER BY created_at")
    return {"profiles": [profile_out(dict(r)) for r in rows]}


@router.post("/profiles", status_code=201)
def create_profile(payload: ProfileIn, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM projects WHERE id = ?",
                      (payload.project_id,)), "projeto")
    if db.one("SELECT id FROM test_profiles WHERE project_id = ? AND name = ?",
              (payload.project_id, payload.name)):
        raise HTTPException(409, "já existe perfil com esse nome")
    pid = new_id("prf")
    db.insert("test_profiles", {
        "id": pid, "project_id": payload.project_id, "name": payload.name,
        "kind": payload.kind,
        "config_json": json.dumps(payload.config, ensure_ascii=False),
        "created_at": utcnow(),
    })
    db.audit("profile.create", "profile", pid,
             {"name": payload.name, "kind": payload.kind})
    return profile_out(dict(db.one("SELECT * FROM test_profiles WHERE id = ?",
                                   (pid,))))


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM test_profiles WHERE id = ?", (profile_id)),
               "perfil")
    db.execute("DELETE FROM test_profiles WHERE id = ?", (profile_id,))
    db.audit("profile.delete", "profile", profile_id, {})
    return {"deleted": profile_id}



# ------------------------------------------------------------------ execuções
@router.post("/runs", status_code=201)
def create_run(payload: RunIn, request: Request) -> dict:
    db = _db(request)
    profile = row_or_404(db.one("SELECT * FROM test_profiles WHERE id = ?",
                                (payload.profile_id,)), "perfil")
    env = row_or_404(db.one("SELECT * FROM environments WHERE id = ?",
                            (payload.environment_id,)), "ambiente")
    if env["project_id"] != profile["project_id"]:
        raise HTTPException(422, "perfil e ambiente pertencem a projetos diferentes")
    rid = new_id("run")
    snapshot = {
        "profile_kind": profile["kind"],
        "profile_config": json.loads(profile["config_json"]),
        "target": {"origin": f"{env['scheme']}://{env['host']}:{env['port']}",
                   "environment_id": env["id"]},
        "tool_version": __version__,
    }
    db.insert("runs", {
        "id": rid, "project_id": profile["project_id"],
        "environment_id": env["id"], "profile_id": profile["id"],
        "kind": profile["kind"], "state": "queued", "queued_at": utcnow(),
        "config_json": json.dumps(snapshot, ensure_ascii=False),
        "tool_version": __version__,
        "summary": "Aguardando na fila (uma execução ativa por vez).",
    })
    db.audit("run.queue", "run", rid, {"profile": profile["name"],
                                       "target": snapshot["target"]["origin"]})
    return run_out(dict(db.one("SELECT * FROM runs WHERE id = ?", (rid,))))


@router.get("/runs")
def list_runs(request: Request, project_id: str | None = None,
              state: str | None = None,
              limit: int = Query(default=50, ge=1, le=200)) -> dict:
    db = _db(request)
    sql = "SELECT * FROM runs WHERE 1=1"
    params: list = []
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    if state:
        sql += " AND state = ?"
        params.append(state)
    sql += " ORDER BY queued_at DESC LIMIT ?"
    params.append(limit)
    return {"runs": [run_out(dict(r)) for r in db.query(sql, params)],
            "active_run": db.one(
                "SELECT id FROM runs WHERE state = 'running' LIMIT 1")}

@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    db = _db(request)
    run = row_or_404(db.one("SELECT * FROM runs WHERE id = ?", (run_id)),
                     "execução")
    return {
        "run": run_out(dict(run)),
        "checks": [dict(c) | {"evidence": json.loads(c["evidence_json"])}
                   for c in db.query("SELECT * FROM check_results "
                                     "WHERE run_id = ? ORDER BY seq", (run_id,))],
        "metrics": [dict(m) | {"details": json.loads(m["details_json"])}
                    for m in db.query("SELECT * FROM metrics WHERE run_id = ?",
                                      (run_id,))],
        "findings": [dict(f) | {"evidence": json.loads(f["evidence_json"])}
                     for f in db.query("SELECT * FROM findings WHERE run_id = ? "
                                       "ORDER BY created_at", (run_id,))],
        "artifacts": [dict(a) for a in db.query(
            "SELECT * FROM artifacts WHERE run_id = ?", (run_id,))],
        "events": [dict(e) for e in db.query(
            "SELECT id, ts, level, message FROM run_events WHERE run_id = ? "
            "ORDER BY id DESC LIMIT 200", (run_id,))][::-1],
        "imports": [dict(i) for i in db.query(
            "SELECT id, format, source_name, records, created_at "
            "FROM imports WHERE run_id = ? ORDER BY created_at", (run_id,))],
    }


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request) -> dict:
    db = _db(request)
    worker = request.app.state.worker
    status, message = worker.request_cancel(run_id)
    if status == "not_found":
        raise HTTPException(404, "execução inexistente")
    return {"status": status, "message": message}

@router.get("/runs/{run_id}/events")
def run_events(run_id: str, request: Request,
               after: int = Query(default=0, ge=0)) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM runs WHERE id = ?", (run_id)), "execução")
    rows = db.query(
        "SELECT id, ts, level, message FROM run_events "
        "WHERE run_id = ? AND id > ? ORDER BY id LIMIT 500", (run_id, after))
    return {"events": [dict(r) for r in rows]}


@router.get("/runs/{run_id}/report")
def run_report(run_id: str, request: Request, format: str = "json"):
    db = _db(request)
    report = build_report(db, run_id)
    if report is None:
        raise HTTPException(404, "execução inexistente")
    if format == "html":
        return HTMLResponse(
            render_html(report),
            headers={"Content-Disposition":
                     f'attachment; filename="verificalab-{run_id}.html"',
                     "Cache-Control": "no-store"})
    from fastapi.responses import JSONResponse
    return JSONResponse(
        report,
        headers={"Content-Disposition":
                 f'attachment; filename="verificalab-{run_id}.json"'})


@router.post("/runs/{run_id}/correlate")
def correlate(run_id: str, request: Request) -> dict:
    db = _db(request)
    run = row_or_404(db.one("SELECT * FROM runs WHERE id = ?", (run_id)),
                     "execução")
    result = correlate_run(db, run)
    if result.get("available"):
        # substitui correlações anteriores desta execução (idempotente)
        db.execute(
            "DELETE FROM findings WHERE run_id = ? AND evidence_json LIKE ?",
            (run_id, '%"correlation_marker": true%'))
        for f in result.get("findings", []):
            ev = dict(f.get("evidence", {}))
            ev["correlation_marker"] = True
            db.insert("findings", {
                "id": new_id("fnd"), "run_id": run_id,
                "environment_id": run["environment_id"],
                "severity": f.get("severity", "hypothesis"),
                "title": f.get("title", ""),
                "description": f.get("description", ""),
                "hypothesis": 1 if f.get("hypothesis") else 0,
                "evidence_json": json.dumps(ev, ensure_ascii=False),
                "created_at": utcnow(),
            })
        db.audit("run.correlate", "run", run_id,
                 {"findings": len(result.get("findings", []))})
    return result


# ------------------------------------------------------------------ laboratório
@router.get("/lab/status")
def lab_status() -> dict:
    return labctl.status()


@router.post("/lab/start")
def lab_start() -> dict:
    return labctl.start()


@router.post("/lab/stop")
def lab_stop() -> dict:
    return labctl.stop()


# ------------------------------------------------------------------ auditoria
@router.get("/audit")
def list_audit(request: Request,
               limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    db = _db(request)
    from ..security import redact_obj
    rows = db.query("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
                    (limit,))
    return {"events": [dict(r) | {"detail": json.loads(r["detail_json"]),
                                  "detail_json": None}
                       for r in rows],
            "note": redact_obj("detalhes de auditoria já são sanitizados")}
