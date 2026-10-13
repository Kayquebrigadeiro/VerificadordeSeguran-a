"""Execução sequencial e limitada de planos de ferramentas autorizados."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from verificalab import config
from verificalab.core.authorization import (
    Authorization,
    AuthorizationError,
    require_authorization,
)
from verificalab.db import Database, get_db, utcnow
from verificalab.ids import new_id, sha256_bytes
from verificalab.security import redact, sanitize_text
from verificalab.stress.base import StressRequest
from verificalab.stress.registry import Tool, ToolRegistry
from verificalab.worker import Worker


@dataclass(frozen=True, slots=True)
class PlanEntry:
    tool_id: str
    tool_name: str
    duration_s: int
    threads: int


@dataclass(frozen=True, slots=True)
class Plan:
    target: str
    tools: tuple[PlanEntry, ...]


@dataclass(frozen=True, slots=True)
class ToolRunSummary:
    run_id: str
    tool_id: str
    tool_name: str
    target: str
    started_at: datetime
    ended_at: datetime
    returncode: int
    ok: bool
    artifact_path: str
    error: str | None = None

    @property
    def total_duration(self) -> float:
        return max(0.0, (self.ended_at - self.started_at).total_seconds())

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "target": self.target,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "returncode": self.returncode,
            "ok": self.ok,
            "total_duration": self.total_duration,
            "artifact_path": self.artifact_path,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    target: str
    started_at: datetime
    ended_at: datetime
    executions: tuple[ToolRunSummary, ...]
    report_paths: tuple[tuple[str, str], ...] = ()

    @property
    def total_duration(self) -> float:
        return max(0.0, (self.ended_at - self.started_at).total_seconds())

    @property
    def ok(self) -> bool:
        return bool(self.executions) and all(item.ok for item in self.executions)

    @property
    def tools(self) -> tuple[ToolRunSummary, ...]:
        return self.executions

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "target": self.target,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "total_duration": self.total_duration,
            "ok": self.ok,
            "executions": [execution.to_dict() for execution in self.executions],
            "reports": dict(self.report_paths),
        }


def _parse_target(target: str) -> tuple[str, str, int]:
    value = target.strip()
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("target deve conter somente host e porta, sem credenciais")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise ValueError("porta inválida no target") from exc
    return parsed.scheme.lower(), parsed.hostname.lower(), port


class Orchestrator:
    """Planeja e executa adapters registrados, persistindo evidências locais."""

    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        db: Database | None = None,
        worker: Worker | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry.load()
        self.db = db or get_db()
        self.worker = worker

    def cancel(self, run_id: str) -> tuple[str, str]:
        """Solicita cancelamento pelo Worker que gerencia a execução."""
        if self.worker is None:
            raise RuntimeError(
                "cancel() requer um Worker; instancie Orchestrator(worker=worker) "
                "com o Worker que gerencia a execução."
            )
        return self.worker.request_cancel(run_id)

    def plan(
        self,
        target: str,
        tools: list[str],
        *,
        duration_s: int | None = None,
        threads: int | None = None,
    ) -> Plan:
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target deve ser uma string não vazia")
        _parse_target(target)
        if not isinstance(tools, list) or not tools:
            raise ValueError("tools deve ser uma lista não vazia")
        if any(not isinstance(tool_id, str) or not tool_id.strip() for tool_id in tools):
            raise ValueError("cada ferramenta deve ter um identificador não vazio")
        if len(set(tools)) != len(tools):
            raise ValueError("tools não pode conter identificadores duplicados")

        entries = []
        for tool_id in tools:
            tool = self.registry.get(tool_id)
            if tool is None:
                raise ValueError(f"ferramenta não registrada: {tool_id}")
            entries.append(self._plan_entry(
                tool,
                duration_s=duration_s,
                threads=threads,
            ))
        return Plan(target=target.strip(), tools=tuple(entries))

    @staticmethod
    def _plan_entry(
        tool: Tool,
        *,
        duration_s: int | None = None,
        threads: int | None = None,
    ) -> PlanEntry:
        duration = duration_s if duration_s is not None else tool.default_limits.duration_s
        thread_count = threads if threads is not None else tool.default_limits.threads
        limits = tool.max_limits
        max_duration = limits.duration_s if limits else tool.default_limits.duration_s
        max_threads = limits.threads if limits else tool.default_limits.threads
        if type(duration) is not int or not 1 <= duration <= max_duration:
            raise ValueError(f"duration_s deve estar entre 1 e {max_duration}")
        if type(thread_count) is not int or not 1 <= thread_count <= max_threads:
            raise ValueError(f"threads deve estar entre 1 e {max_threads}")
        return PlanEntry(
            tool_id=tool.id,
            tool_name=tool.name,
            duration_s=duration,
            threads=thread_count,
        )

    def _authorize(self, plan: Plan, auth: Authorization | None) -> Authorization:
        trusted = require_authorization(plan.target)
        if auth is not None:
            if not isinstance(auth, Authorization):
                raise AuthorizationError("auth deve ser uma autorização válida")
            if auth != trusted or auth.target.strip() != plan.target:
                raise AuthorizationError("auth não corresponde à autorização do alvo")
        return trusted

    def _adapter_for(self, tool_id: str):
        return self.registry.adapter_for(tool_id)

    def _create_db_context(
        self, orchestration_id: str, target: str, tool: PlanEntry
    ) -> tuple[str, str, str, str]:
        scheme, host, port = _parse_target(target)
        project_id = new_id("prj")
        environment_id = new_id("env")
        profile_id = new_id("pro")
        run_id = new_id("run")
        now = utcnow()
        self.db.insert("projects", {
            "id": project_id,
            "name": f"Orchestrator {orchestration_id} {tool.tool_id}",
            "description": "Execução controlada pelo orchestrator.",
            "created_at": now,
        })
        self.db.insert("environments", {
            "id": environment_id,
            "project_id": project_id,
            "name": "Alvo autorizado",
            "scheme": scheme,
            "host": host,
            "port": port,
            "kind": "local",
            "created_at": now,
        })
        self.db.insert("test_profiles", {
            "id": profile_id,
            "project_id": project_id,
            "name": tool.tool_id,
            "kind": "load",
            "config_json": json.dumps({
                "target": target,
                "tool_id": tool.tool_id,
                "duration_s": tool.duration_s,
                "threads": tool.threads,
            }, ensure_ascii=False),
            "created_at": now,
        })
        return project_id, environment_id, profile_id, run_id

    @staticmethod
    def _output_text(text: object) -> str:
        return redact(sanitize_text(str(text or ""), config.SUITE_MAX_OUTPUT_BYTES))

    def _persist_execution(
        self,
        *,
        orchestration_id: str,
        plan: Plan,
        entry: PlanEntry,
        result,
        run_id: str,
        project_id: str,
        environment_id: str,
        profile_id: str,
        started_at: datetime,
        ended_at: datetime,
        error: str | None,
    ) -> ToolRunSummary:
        returncode = getattr(result, "returncode", -1) if result is not None else -1
        if type(returncode) is not int:
            returncode = -1
        output = self._output_text(getattr(result, "stdout", ""))
        stderr = self._output_text(getattr(result, "stderr", ""))
        if error:
            stderr = "\n".join(part for part in (stderr, self._output_text(error)) if part)
        timeout = bool(getattr(result, "timeout", False))
        cancelled = bool(getattr(result, "cancelled", False))
        ok = returncode == 0 and not timeout and not cancelled and error is None
        state = "passed" if ok else "failed"

        artifact_dir = config.ARTIFACTS_DIR / orchestration_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            artifact_dir.chmod(0o700)
        except OSError:
            pass
        artifact_path = artifact_dir / f"{entry.tool_id}.log"
        contents = f"stdout:\n{output}\nstderr:\n{stderr}\n"
        artifact_bytes = contents.encode("utf-8")
        artifact_path.write_bytes(artifact_bytes)
        try:
            artifact_path.chmod(0o600)
        except OSError:
            pass

        self.db.insert("runs", {
            "id": run_id,
            "project_id": project_id,
            "environment_id": environment_id,
            "profile_id": profile_id,
            "kind": "stress",
            "state": state,
            "queued_at": started_at.isoformat(),
            "started_at": started_at.isoformat(),
            "finished_at": ended_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "exit_code": returncode,
            "returncode": returncode,
            "ok": int(ok),
            "tool_id": entry.tool_id,
            "target": plan.target,
            "orchestrator_id": orchestration_id,
            "config_json": json.dumps({
                "tool_id": entry.tool_id,
                "target": plan.target,
                "duration_s": entry.duration_s,
                "threads": entry.threads,
            }, ensure_ascii=False),
            "summary": self._output_text(error or ("execução aprovada" if ok else "execução falhou")),
        })
        self.db.insert("check_results", {
            "id": new_id("chk"),
            "run_id": run_id,
            "seq": 1,
            "name": f"{entry.tool_id} execution",
            "category": "stress",
            "status": "pass" if ok else "fail",
            "expected": "returncode 0",
            "observed": str(returncode),
            "message": self._output_text(error or ("execução aprovada" if ok else "execução falhou")),
            "evidence_json": json.dumps({
                "timeout": timeout,
                "cancelled": cancelled,
                "artifact": str(artifact_path),
            }, ensure_ascii=False),
            "duration_ms": max(0.0, (ended_at - started_at).total_seconds() * 1000),
        })
        self.db.insert("artifacts", {
            "id": new_id("art"),
            "run_id": run_id,
            "kind": "stress_output",
            "filename": artifact_path.name,
            "rel_path": artifact_path.relative_to(config.DATA_DIR).as_posix(),
            "sha256": sha256_bytes(artifact_bytes),
            "size": len(artifact_bytes),
            "preview": self._output_text(contents[-800:]),
            "created_at": utcnow(),
        })
        return ToolRunSummary(
            run_id=run_id,
            tool_id=entry.tool_id,
            tool_name=entry.tool_name,
            target=plan.target,
            started_at=started_at,
            ended_at=ended_at,
            returncode=returncode,
            ok=ok,
            artifact_path=str(artifact_path),
            error=self._output_text(error) if error else None,
        )

    def run(self, plan: Plan, auth: Authorization | None = None) -> RunSummary:
        if not isinstance(plan, Plan) or not plan.tools:
            raise ValueError("plan inválido ou sem ferramentas")
        # A autorização é validada antes de criar artefatos, registros ou subprocessos.
        self._authorize(plan, auth)
        for entry in plan.tools:
            registered = self.registry.get(entry.tool_id)
            if registered is None:
                raise ValueError(f"ferramenta não registrada: {entry.tool_id}")
            if not isinstance(entry, PlanEntry) or entry != self._plan_entry(
                registered,
                duration_s=entry.duration_s,
                threads=entry.threads,
            ):
                raise ValueError(f"entrada do plano foi alterada: {entry.tool_id}")

        orchestration_id = new_id("stress")
        started_at = datetime.now(timezone.utc)
        executions = []
        for entry in plan.tools:
            project_id, environment_id, profile_id, run_id = self._create_db_context(
                orchestration_id, plan.target, entry
            )
            tool_started = datetime.now(timezone.utc)
            result = None
            error = None
            try:
                result = self._adapter_for(entry.tool_id).run(StressRequest(
                    target=plan.target,
                    duration_s=entry.duration_s,
                    threads=entry.threads,
                ))
            except AuthorizationError:
                raise
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            tool_ended = datetime.now(timezone.utc)
            executions.append(self._persist_execution(
                orchestration_id=orchestration_id,
                plan=plan,
                entry=entry,
                result=result,
                run_id=run_id,
                project_id=project_id,
                environment_id=environment_id,
                profile_id=profile_id,
                started_at=tool_started,
                ended_at=tool_ended,
                error=error,
            ))

        summary = RunSummary(
            run_id=orchestration_id,
            target=plan.target,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            executions=tuple(executions),
        )
        from verificalab.core import report

        report_paths = (
            ("json", str(report.to_json(summary))),
            ("markdown", str(report.to_markdown(summary))),
            ("html", str(report.to_html(summary))),
        )
        return RunSummary(
            run_id=summary.run_id,
            target=summary.target,
            started_at=summary.started_at,
            ended_at=summary.ended_at,
            executions=summary.executions,
            report_paths=report_paths,
        )
