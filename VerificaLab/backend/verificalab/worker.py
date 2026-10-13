"""Worker separado do ciclo HTTP — executa uma execução ativa por vez.

- Reclama execuções `queued` (mais antiga primeiro) e as executa.
- Cancelamento: fila → cancelada direta; ativa → flag + evento; executores
  interrompem novos envios e encerram sub-processos (suite) no prazo.
- Recuperação após reinício: execuções `running` viram `interrupted`
  (nunca aprovadas). `queued` permanece na fila.
- Persistência completa: checks, métricas, achados, artefatos, eventos.
"""

from __future__ import annotations

import json
import threading
import time
import traceback

from .db import Database, utcnow
from .ids import safe_filename, sha256_file
from .security import redact, register_secret, sanitize_text

FINAL_STATES = {"passed", "failed", "cancelled", "timed_out", "interrupted", "error"}


class RunContext:
    """API que os executores usam para interagir com a execução atual."""

    def __init__(self, worker: "Worker", run_id: str, cfg: dict, env,
                 artifact_dir, deadline_s: float, secret_header: str | None) -> None:
        self._worker = worker
        self.db: Database = worker.db
        self.run_id = run_id
        self.cfg = cfg
        self.env = env
        self.artifact_dir = artifact_dir
        self.cancel_event = worker._events.get(run_id) or threading.Event()
        self.secret_header = secret_header
        self._deadline = time.monotonic() + deadline_s

    def log(self, level: str, message: str) -> None:
        self.db.insert("run_events", {
            "run_id": self.run_id, "ts": utcnow(), "level": level,
            "message": sanitize_text(redact(message), max_len=1000),
        })

    def set_progress(self, value: float) -> None:
        self.db.update("runs", {"progress": max(0.0, min(0.99, float(value)))},
                       "id = ?", (self.run_id,))

    def deadline_reached(self) -> bool:
        return getattr(self, "_deadline", 0) <= time.monotonic()


def aggregate_http_state(results: list[dict]) -> str:
    """failed = teste observado falhou; error = runner não concluiu."""
    statuses = [r.get("status") for r in results]
    if not statuses:
        return "error"
    if any(s == "fail" for s in statuses):
        return "failed"
    if any(s == "error" for s in statuses):
        return "error"
    return "passed"


class Worker:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self.active_run_id: str | None = None

    # ------------------------------------------------------------------ ciclo
    def start(self) -> None:
        self.recover_interrupted()
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="verificalab-worker",
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def recover_interrupted(self) -> None:
        """Reinício: running -> interrupted (nunca aprovada)."""
        rows = self.db.query("SELECT id FROM runs WHERE state = 'running'")
        for row in rows:
            self.db.update("runs", {
                "state": "interrupted",
                "finished_at": utcnow(),
                "interrupted_reason": "reinício da aplicação",
                "summary": "Execução interrompida por reinício; não é aprovação.",
            }, "id = ? AND state = 'running'", (row["id"],))
            self.db.audit("run.interrupted", "run", row["id"])
        if rows:
            print(f"[worker] {len(rows)} execução(ões) marcada(s) como interrompidas")

    def request_cancel(self, run_id: str) -> tuple[str, str]:
        """Retorna (status, mensagem)."""
        row = self.db.one("SELECT state FROM runs WHERE id = ?", (run_id,))
        if not row:
            return "not_found", "execução inexistente"
        state = row["state"]
        if state in FINAL_STATES:
            return "already_final", f"execução já finalizada ({state})"
        if state == "queued":
            changed = self.db.execute(
                "UPDATE runs SET state='cancelled', finished_at=?, summary=? "
                "WHERE id=? AND state='queued'",
                (utcnow(), "Cancelada na fila antes de iniciar.", run_id)).rowcount
            if changed:
                self.db.audit("run.cancel", "run", run_id, {"where": "queued"})
                return "cancelled", "cancelada na fila"
            return "race", "estado mudou; tente novamente"
        self.db.update("runs", {"cancel_requested": 1},
                       "id = ? AND state = 'running'", (run_id,))
        with self._lock:
            ev = self._events.get(run_id)
        if ev:
            ev.set()
        self.db.audit("run.cancel", "run", run_id, {"where": "running"})
        return "cancelling", "cancelamento solicitado; aguardando interrupção"

    # ------------------------------------------------------------------ loop
    def _loop(self) -> None:
        while not self._stop.is_set():
            row = self.db.one(
                "SELECT id FROM runs WHERE state = 'queued' "
                "ORDER BY queued_at ASC LIMIT 1")
            if not row:
                time.sleep(0.4)
                continue
            run_id = row["id"]
            changed = self.db.execute(
                "UPDATE runs SET state='running', started_at=?, progress=0.01 "
                "WHERE id=? AND state='queued'", (utcnow(), run_id)).rowcount
            if not changed:
                continue
            self._execute(run_id)
        if self.active_run_id:
            self.db.update("runs", {
                "state": "interrupted", "finished_at": utcnow(),
                "interrupted_reason": "encerramento do worker",
                "summary": "Execução interrompida pelo encerramento do worker.",
            }, "id = ? AND state = 'running'", (self.active_run_id,))




    # ------------------------------------------------------------------ execução
    def _execute(self, run_id: str) -> None:
        from . import config
        from .executors.httpchecks import run_http_checks
        from .executors.loadgen import run_load
        from .executors.suite import run_suite

        run = self.db.one("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not run:
            return
        env_row = self.db.one("SELECT * FROM environments WHERE id = ?",
                              (run["environment_id"],))
        env = dict(env_row) if env_row else {}
        snapshot = json.loads(run["config_json"])
        kind = snapshot["profile_kind"]
        profile_cfg = snapshot["profile_config"]

        artifact_dir = config.ARTIFACTS_DIR / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            artifact_dir.chmod(0o700)
        except OSError:
            pass

        # segredo do ambiente: cifrado em arquivo 0600, nunca no banco em claro
        secret: str | None = None
        secret_file = config.SECRETS_DIR / f"{run['environment_id']}.secret"
        if env.get("secret_header_name") and secret_file.exists():
            try:
                from .security import get_vault
                secret = get_vault().decrypt(
                    secret_file.read_text(encoding="ascii").strip())
                register_secret(secret)
            except Exception:
                secret = None

        # evento de cancelamento (fecha a corrida com a API)
        ev = threading.Event()
        with self._lock:
            self._events[run_id] = ev
            self.active_run_id = run_id
        pending = self.db.one("SELECT cancel_requested FROM runs WHERE id = ?",
                              (run_id,))
        if pending and pending["cancel_requested"]:
            ev.set()

        if kind == "http":
            deadline_s = 60 + 15 * max(1, len(profile_cfg.get("checks", [])))
        elif kind == "load":
            deadline_s = (profile_cfg.get("duration_s", 30)
                          + profile_cfg.get("timeout_s", 10) + 15)
        else:
            deadline_s = profile_cfg.get("timeout_s", 120) + 15

        ctx = RunContext(self, run_id, profile_cfg, env, artifact_dir,
                         deadline_s, secret)
        ctx.log("info", f"execução iniciada (tipo={kind})")
        self.db.audit("run.start", "run", run_id, {"kind": kind})

        try:
            if kind == "http":
                result = run_http_checks(ctx)
            elif kind == "load":
                result = run_load(ctx)
            elif kind == "suite":
                result = run_suite(ctx)
            else:
                result = {"state": "error", "summary": f"tipo desconhecido: {kind}",
                          "checks": [], "findings": [], "metrics": [],
                          "artifacts": []}
        except Exception as exc:  # runner não conseguiu concluir
            result = {
                "state": "error",
                "summary": "Falha interna do runner; execução não concluída.",
                "checks": [], "findings": [], "metrics": [], "artifacts": [],
                "error": sanitize_text(
                    "".join(traceback.format_exception(exc))[-3000:]),
            }

        state = result.get("state")
        if kind == "http" and state not in ("cancelled", "timed_out", "error"):
            state = aggregate_http_state(result.get("checks", []))
        if state not in FINAL_STATES:
            state = "error"

        cancel_flag = self.db.one("SELECT cancel_requested FROM runs WHERE id = ?",
                                  (run_id,))
        if cancel_flag and cancel_flag["cancel_requested"] and ev.is_set():
            if state != "cancelled":
                result["summary"] = (
                    "Cancelamento solicitado durante a execução; resultado não "
                    "constitui aprovação. " + (result.get("summary") or ""))
            state = "cancelled"

        self._persist(run_id, env, result, state)
        with self._lock:
            self._events.pop(run_id, None)
            self.active_run_id = None
        ctx.log("info", f"execução finalizada: {state}")


    # ------------------------------------------------------------------ persistência
    def _persist(self, run_id: str, env, result: dict, state: str) -> None:
        from . import config as _config
        from .ids import new_id
        from .security import redact_obj

        for seq, chk in enumerate(result.get("checks", [])):
            self.db.insert("check_results", {
                "id": new_id("chk"), "run_id": run_id, "seq": seq,
                "name": sanitize_text(str(chk.get("name", "")), 300),
                "category": str(chk.get("category", "contract")),
                "status": chk.get("status", "unknown"),
                "expected": sanitize_text(str(chk.get("expected", "")), 1000),
                "observed": sanitize_text(str(chk.get("observed", "")), 1000),
                "message": sanitize_text(redact(str(chk.get("message", ""))), 2000),
                "evidence_json": json.dumps(
                    redact_obj(chk.get("evidence", {})), ensure_ascii=False),
                "duration_ms": chk.get("duration_ms"),
            })
        for m in result.get("metrics", []):
            self.db.insert("metrics", {
                "id": new_id("met"), "run_id": run_id,
                "name": str(m.get("name", "")),
                "value": m.get("value"), "value_text": m.get("value_text"),
                "unit": m.get("unit"), "origin": str(m.get("origin", "")),
                "samples": m.get("samples"), "population": m.get("population"),
                "discarded": int(m.get("discarded") or 0),
                "details_json": json.dumps(m.get("details", {}), ensure_ascii=False),
            })
        for f in result.get("findings", []):
            self.db.insert("findings", {
                "id": new_id("fnd"), "run_id": run_id,
                "environment_id": env["id"],
                "severity": f.get("severity", "info"),
                "title": sanitize_text(str(f.get("title", "")), 300),
                "description": sanitize_text(
                    redact(str(f.get("description", ""))), 4000),
                "hypothesis": 1 if f.get("hypothesis") else 0,
                "evidence_json": json.dumps(
                    redact_obj(f.get("evidence", {})), ensure_ascii=False),
                "created_at": utcnow(),
            })

        for art in result.get("artifacts", []):
            path = art.get("path")
            if not path:
                continue
            try:
                p = _config.Path(path)
                rel = p.relative_to(_config.ARTIFACTS_DIR)
                size = p.stat().st_size
                digest = sha256_file(p)
            except (ValueError, OSError):
                continue
            self.db.insert("artifacts", {
                "id": new_id("art"), "run_id": run_id,
                "kind": str(art.get("kind", "file")),
                "filename": safe_filename(art.get("filename", p.name), p.name),
                "rel_path": str(rel), "sha256": digest, "size": size,
                "preview": sanitize_text(redact(str(art.get("preview", ""))), 2000),
                "created_at": utcnow(),
            })
        summary = sanitize_text(redact(str(result.get("summary", ""))), 2000)
        self.db.update("runs", {
            "state": state, "finished_at": utcnow(), "summary": summary,
            "error_detail": sanitize_text(
                str(result.get("error", "") or ""), 3000) or None,
            "exit_code": result.get("exit_code"),
            "progress": 1.0,
        }, "id = ?", (run_id,))
        self.db.audit("run.finish", "run", run_id,
                      {"state": state, "summary": summary[:200]})
