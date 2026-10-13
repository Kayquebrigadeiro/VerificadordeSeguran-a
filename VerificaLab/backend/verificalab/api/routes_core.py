"""Rotas: sessão, projetos, ambientes, ferramentas."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import config, labctl
from ..catalog import INVENTORY_CAVEATS
from ..db import utcnow
from ..ids import new_id
from ..models import EnvironmentIn, ProjectIn
from ..security import get_vault, register_secret
from ..targetpolicy import parse_endpoint, TargetPolicyError
from .helpers import env_out, rows_to_dicts, row_or_404, tool_out

router = APIRouter(prefix="/api")


def _db(request: Request):
    return request.app.state.db


# ------------------------------------------------------------------ sessão
@router.get("/session")
def session(request: Request) -> dict:
    from .. import __version__, security
    return {
        "csrf_token": security.csrf_token(),
        "csrf_header": security.CSRF_HEADER,
        "version": __version__,
        "limits": {
            "load_max_rps": config.LOAD_MAX_RPS,
            "load_default_rps": config.LOAD_DEFAULT_RPS,
            "load_max_concurrency": config.LOAD_MAX_CONCURRENCY,
            "load_max_duration_s": config.LOAD_MAX_DURATION_S,
            "load_max_attempts": config.LOAD_MAX_ATTEMPTS,
            "load_allowed_methods": list(config.LOAD_ALLOWED_METHODS),
            "max_upload_bytes": config.MAX_UPLOAD_BYTES,
            "suite_allowed_commands": [list(c) for c in config.SUITE_ALLOWED_COMMANDS],
            "retention": config.RETENTION_NOTE,
        },
        "lab": labctl.status(),
    }


@router.get("/health")
def health(request: Request) -> dict:
    db = _db(request)
    return {"ok": True, "schema_version": db.schema_version,
            "worker_active_run": request.app.state.worker.active_run_id}


# ------------------------------------------------------------------ projetos
@router.get("/projects")
def list_projects(request: Request) -> dict:
    db = _db(request)
    out = []
    for p in db.query("SELECT * FROM projects ORDER BY created_at DESC"):
        item = dict(p)
        item["environments"] = db.one(
            "SELECT COUNT(*) AS c FROM environments WHERE project_id = ?",
            (p["id"],))["c"]
        item["profiles"] = db.one(
            "SELECT COUNT(*) AS c FROM test_profiles WHERE project_id = ?",
            (p["id"],))["c"]
        item["runs"] = db.one(
            "SELECT COUNT(*) AS c FROM runs WHERE project_id = ?",
            (p["id"],))["c"]
        out.append(item)
    return {"projects": out}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectIn, request: Request) -> dict:
    db = _db(request)
    if db.one("SELECT id FROM projects WHERE name = ?", (payload.name,)):
        raise HTTPException(409, "já existe projeto com esse nome")
    pid = new_id("prj")
    db.insert("projects", {"id": pid, "name": payload.name,
                           "description": payload.description,
                           "created_at": utcnow()})
    db.audit("project.create", "project", pid, {"name": payload.name})
    return dict(db.one("SELECT * FROM projects WHERE id = ?", (pid,)))


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    db = _db(request)
    return dict(row_or_404(db.one("SELECT * FROM projects WHERE id = ?",
                                  (project_id)), "projeto"))


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectIn, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM projects WHERE id = ?", (project_id)), "projeto")
    db.update("projects", {"name": payload.name,
                           "description": payload.description},
              "id = ?", (project_id,))
    db.audit("project.update", "project", project_id, {})
    return dict(db.one("SELECT * FROM projects WHERE id = ?", (project_id,)))


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM projects WHERE id = ?", (project_id)), "projeto")
    for env in db.query("SELECT id FROM environments WHERE project_id = ?",
                        (project_id,)):
        _delete_secret(env["id"])
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.audit("project.delete", "project", project_id, {})
    return {"deleted": project_id}


def _delete_secret(env_id: str) -> None:
    path = config.SECRETS_DIR / f"{env_id}.secret"
    if path.exists():
        path.unlink()



# ------------------------------------------------------------------ ambientes
@router.get("/environments")
def list_environments(request: Request, project_id: str | None = None) -> dict:
    db = _db(request)
    if project_id:
        rows = db.query("SELECT * FROM environments WHERE project_id = ? "
                        "ORDER BY created_at", (project_id,))
    else:
        rows = db.query("SELECT * FROM environments ORDER BY created_at")
    return {"environments": [env_out(dict(r)) for r in rows]}


@router.post("/environments", status_code=201)
def create_environment(payload: EnvironmentIn, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM projects WHERE id = ?",
                      (payload.project_id,)), "projeto")
    try:
        scheme, host, port = parse_endpoint(payload.endpoint)
    except TargetPolicyError as exc:
        raise HTTPException(422, f"endpoint recusado: {exc.reason}")
    if db.one("SELECT id FROM environments WHERE project_id = ? AND name = ?",
              (payload.project_id, payload.name)):
        raise HTTPException(409, "já existe ambiente com esse nome")
    env_id = new_id("env")
    db.insert("environments", {
        "id": env_id, "project_id": payload.project_id, "name": payload.name,
        "scheme": scheme, "host": host, "port": port, "kind": payload.kind,
        "secret_header_name": payload.secret_header_name,
        "created_at": utcnow(),
    })
    has_secret = False
    if payload.secret_header_name and payload.secret_header_value:
        _write_secret(env_id, payload.secret_header_value)
        has_secret = True
    db.audit("environment.create", "environment", env_id,
             {"endpoint": f"{scheme}://{host}:{port}", "has_secret": has_secret})
    row = dict(db.one("SELECT * FROM environments WHERE id = ?", (env_id,)))
    row["has_secret"] = has_secret
    return row


@router.delete("/environments/{env_id}")
def delete_environment(env_id: str, request: Request) -> dict:
    db = _db(request)
    row_or_404(db.one("SELECT id FROM environments WHERE id = ?", (env_id)),
               "ambiente")
    _delete_secret(env_id)
    db.execute("DELETE FROM environments WHERE id = ?", (env_id,))
    db.audit("environment.delete", "environment", env_id, {})
    return {"deleted": env_id}


def _write_secret(env_id: str, value: str) -> None:
    config.ensure_dirs()
    path = config.SECRETS_DIR / f"{env_id}.secret"
    path.write_text(get_vault().encrypt(value), encoding="ascii")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    register_secret(value)


# ------------------------------------------------------------------ ferramentas
@router.get("/tools")
def list_tools(request: Request) -> dict:
    db = _db(request)
    return {"tools": [tool_out(dict(r)) for r in
                      db.query("SELECT * FROM tools ORDER BY name")],
            "caveats": INVENTORY_CAVEATS,
            "note": ("Catálogo baseado em leitura estática dos fontes; não "
                     "comprova execução ou funcionamento das ferramentas.")}
