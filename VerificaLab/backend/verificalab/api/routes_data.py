"""Rotas: uploads de logs, importações, artefatos, comparação, achados."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from .. import config
from ..analysis.correlate import parse_log_file, store_logs
from ..analysis.report import compare_runs
from ..db import utcnow
from ..ids import new_id, safe_filename, sha256_bytes
from ..importers import FORMAT_LABELS, ImportRejected, parse_import
from ..security import redact, redact_obj, sanitize_text
from .helpers import row_or_404

router = APIRouter(prefix="/api")


def _db(request: Request):
    return request.app.state.db


async def _read_body(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"corpo acima do limite ({limit} bytes)")
        chunks.append(chunk)
    return b"".join(chunks)


# ------------------------------------------------------------------ logs
@router.post("/environments/{env_id}/logs")
async def upload_logs(env_id: str, request: Request,
                      filename: str = Query(default="upload.log", max_length=200)):
    db = _db(request)
    row_or_404(db.one("SELECT id FROM environments WHERE id = ?", (env_id)),
               "ambiente")
    data = await _read_body(request, config.MAX_UPLOAD_BYTES)
    if not data:
        raise HTTPException(422, "corpo vazio")
    try:
        parsed = parse_log_file(filename, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    n = store_logs(db, env_id, parsed)
    return {
        "filename": parsed["filename"], "entries": n,
        "total_lines": parsed["total_lines"], "discarded": parsed["discarded"],
        "without_timestamp": parsed["unparsed_ts"],
        "timezones": parsed["timezones"], "uncertainties": parsed["uncertainties"],
        "sha256": parsed["sha256"],
    }


@router.get("/environments/{env_id}/logs")
def get_logs(env_id: str, request: Request,
             limit: int = Query(default=200, ge=1, le=2000),
             offset: int = Query(default=0, ge=0),
             level: str | None = None):
    db = _db(request)
    row_or_404(db.one("SELECT id FROM environments WHERE id = ?", (env_id)),
               "ambiente")
    sql = "SELECT * FROM log_entries WHERE environment_id = ?"
    params: list = [env_id]
    if level:
        sql += " AND level = ?"
        params.append(level.upper())
    total = db.one(f"SELECT COUNT(*) AS c FROM ({sql})", params)["c"]
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return {"total": total, "entries": [dict(r) for r in db.query(sql, params)]}



# ------------------------------------------------------------------ importações
@router.get("/import/formats")
def import_formats() -> dict:
    return {"formats": FORMAT_LABELS,
            "note": ("MikuMikuBeam não possui importador: estatísticas existem "
                     "apenas como stream WebSocket (sem arquivo exportável).")}


@router.post("/imports", status_code=201)
async def create_import(request: Request,
                        format: str = Query(...),
                        run_id: str | None = Query(default=None),
                        filename: str = Query(default="report.json", max_length=200)):
    db = _db(request)
    if run_id:
        row_or_404(db.one("SELECT id FROM runs WHERE id = ?", (run_id)), "execução")
    data = await _read_body(request, config.MAX_UPLOAD_BYTES)
    if not data:
        raise HTTPException(422, "corpo vazio")
    try:
        parsed = parse_import(format, data, safe_filename(filename))
    except ImportRejected as exc:
        raise HTTPException(422, f"importação recusada: {exc.reason}")

    imp_id = new_id("imp")
    # registros normalizados viram artefato (caminho gerado pelo backend)
    rel_dir = run_id if run_id else "_imports"
    art_dir = config.ARTIFACTS_DIR / rel_dir
    art_dir.mkdir(parents=True, exist_ok=True)
    records_path = art_dir / f"import_{imp_id}.json"
    payload = redact_obj({
        "import_id": imp_id, "format": format,
        "source_name": safe_filename(filename),
        "provenance": parsed.get("provenance", {}),
        "warnings": parsed["warnings"],
        "records": parsed.get("records_list", []),
    })
    records_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    db.insert("imports", {
        "id": imp_id, "run_id": run_id, "format": format,
        "source_name": sanitize_text(safe_filename(filename), 200),
        "sha256": sha256_bytes(data), "size": len(data),
        "records": parsed.get("records", 0),
        "warnings_json": json.dumps(parsed["warnings"], ensure_ascii=False),
        "created_at": utcnow(),
    })
    if run_id:
        from ..ids import sha256_file
        db.insert("artifacts", {
            "id": new_id("art"), "run_id": run_id, "kind": "import",
            "filename": records_path.name,
            "rel_path": str(records_path.relative_to(config.ARTIFACTS_DIR)),
            "sha256": sha256_file(records_path),
            "size": records_path.stat().st_size,
            "preview": sanitize_text(redact(
                json.dumps(parsed.get("records_list", [])[:3],
                           ensure_ascii=False)), 1500),
            "created_at": utcnow(),
        })
        for m in parsed.get("metrics", []):
            db.insert("metrics", {
                "id": new_id("met"), "run_id": run_id,
                "name": f"import.{m.get('name', '')}",
                "value": m.get("value"), "unit": m.get("unit"),
                "origin": m.get("origin", "importação externa"),
                "samples": m.get("samples"), "population": m.get("population"),
                "discarded": int(m.get("discarded") or 0),
                "details_json": json.dumps(m.get("details", {}),
                                           ensure_ascii=False),
            })
    db.audit("import.create", "import", imp_id,
             {"format": format, "records": parsed.get("records", 0),
              "run_id": run_id, "source": safe_filename(filename)})
    return {"id": imp_id, "format": format, "records": parsed.get("records", 0),
            "warnings": parsed["warnings"],
            "provenance": parsed.get("provenance", {}),
            "attached_to_run": run_id}

@router.get("/imports")
def list_imports(request: Request, run_id: str | None = None,
                 limit: int = Query(default=100, ge=1, le=500)) -> dict:
    db = _db(request)
    if run_id:
        rows = db.query("SELECT * FROM imports WHERE run_id = ? "
                        "ORDER BY created_at DESC LIMIT ?", (run_id, limit))
    else:
        rows = db.query("SELECT * FROM imports ORDER BY created_at DESC LIMIT ?",
                        (limit,))
    return {"imports": [dict(r) | {"warnings": json.loads(r["warnings_json"]),
                                   "warnings_json": None} for r in rows]}


@router.get("/imports/{import_id}")
def get_import(import_id: str, request: Request) -> dict:
    db = _db(request)
    row = row_or_404(db.one("SELECT * FROM imports WHERE id = ?", (import_id)),
                     "importação")
    out = dict(row)
    out["warnings"] = json.loads(out.pop("warnings_json"))
    out["records_detail"] = None
    # caminho determinístico gerado no upload (run_id ou _imports)
    rel_dir = row["run_id"] if row["run_id"] else "_imports"
    path = (config.ARTIFACTS_DIR / rel_dir /
            f"import_{import_id}.json").resolve()
    try:
        path.relative_to(config.ARTIFACTS_DIR.resolve())
        if path.is_file():
            out["records_detail"] = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        pass
    return out


# ------------------------------------------------------------------ artefatos
@router.get("/artifacts/{art_id}/download")
def download_artifact(art_id: str, request: Request):
    db = _db(request)
    art = row_or_404(db.one("SELECT * FROM artifacts WHERE id = ?", (art_id)),
                     "artefato")
    path = (config.ARTIFACTS_DIR / art["rel_path"]).resolve()
    try:
        path.relative_to(config.ARTIFACTS_DIR.resolve())  # trava de caminho
    except ValueError:
        raise HTTPException(400, "caminho de artefato inválido")
    if not path.is_file():
        raise HTTPException(404, "arquivo de artefato ausente")
    return FileResponse(path, filename=safe_filename(art["filename"], "artefato"),
                        media_type="application/octet-stream",
                        headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ comparação
@router.get("/compare")
def compare(request: Request, a: str = Query(...), b: str = Query(...)):
    db = _db(request)
    result = compare_runs(db, a, b)
    if result is None:
        raise HTTPException(404, "uma das execuções não existe")
    return result


# ------------------------------------------------------------------ achados
@router.get("/findings")
def list_findings(request: Request, run_id: str | None = None,
                  environment_id: str | None = None,
                  limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    db = _db(request)
    sql = "SELECT * FROM findings WHERE 1=1"
    params: list = []
    if run_id:
        sql += " AND run_id = ?"
        params.append(run_id)
    if environment_id:
        sql += " AND environment_id = ?"
        params.append(environment_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return {"findings": [dict(f) | {"evidence": json.loads(f["evidence_json"]),
                                    "evidence_json": None}
                         for f in db.query(sql, params)]}
