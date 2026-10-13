"""Runner de suíte de testes — subprocesso real, sem shell, cancelável.

- Argumentos em lista (nenhum shell interpreta entrada do usuário).
- cwd resolvido e restrito às raízes permitidas (validado no cadastro).
- Ambiente mínimo, saída incremental com teto de bytes, prazo total.
- Cancelamento/timeout encerram a ÁRVORE de processos (start_new_session +
  killpg: SIGTERM, espera de SUITE_KILL_GRACE_S, SIGKILL).
- Resultado vem do relatório JUnit gerado pelo próprio runner; sem JUnit
  o resultado é "não confirmável" (error), nunca aprovado.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from .. import config
from ..importers import ImportRejected, parse_import
from ..metrics import count_summary
from ..models import SuiteProfileConfig
from ..security import sanitize_text


def _kill_tree(proc: subprocess.Popen) -> str:
    """Encerra a árvore de processos (grupo de sinais)."""
    action = ""
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return "já finalizado"
    try:
        os.killpg(pgid, signal.SIGTERM)
        action = "SIGTERM"
        proc.wait(timeout=config.SUITE_KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
            action = "SIGKILL"
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            action += " (espera esgotada)"
    except ProcessLookupError:
        pass
    return action


def run_suite(ctx) -> dict:
    cfg = SuiteProfileConfig.model_validate(ctx.cfg)
    cwd = Path(cfg.cwd)
    if not cwd.is_dir():
        return {"state": "error", "summary": f"cwd inexistente: {cwd}",
                "checks": [], "findings": [], "metrics": [], "artifacts": []}

    junit_path = ctx.artifact_dir / "junit.xml"
    cmd = list(cfg.command) + [f"--junitxml={junit_path}"]
    ctx.log("info", f"executando: {cmd[0]} ... (cwd={cwd.name})")

    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONUNBUFFERED": "1",
        "HOME": str(ctx.artifact_dir),
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(ctx.artifact_dir),
    }
    output_chunks: list[bytes] = []
    output_size = 0
    truncated = False
    out_lock = threading.Lock()

    try:
        proc = subprocess.Popen(   # lista, sem invocação de shell
            cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,   # próprio grupo de sinais
        )
    except (OSError, ValueError) as exc:
        return {"state": "error", "summary": f"falha ao iniciar runner: {exc}",
                "checks": [], "findings": [], "metrics": [], "artifacts": []}

    def drain() -> None:
        nonlocal output_size, truncated
        assert proc.stdout is not None
        for chunk in iter(lambda: proc.stdout.read(4096), b""):
            with out_lock:
                if output_size + len(chunk) <= config.SUITE_MAX_OUTPUT_BYTES:
                    output_chunks.append(chunk)
                    output_size += len(chunk)
                else:
                    truncated = True  # continua drenando, só não armazena

    reader = threading.Thread(target=drain, name="suite-out", daemon=True)
    reader.start()

    started = time.monotonic()
    deadline = started + cfg.timeout_s
    kill_reason: str | None = None
    kill_action = ""
    while proc.poll() is None:
        if ctx.cancel_event.is_set():
            kill_reason = "cancelled"
            kill_action = _kill_tree(proc)
            ctx.log("warn", f"cancelamento: árvore de processos encerrada ({kill_action})")
            break
        if time.monotonic() >= deadline:
            kill_reason = "timed_out"
            kill_action = _kill_tree(proc)
            ctx.log("warn", f"timeout: árvore de processos encerrada ({kill_action})")
            break
        time.sleep(0.15)


    exit_code = proc.poll()
    if exit_code is None:
        try:
            exit_code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            exit_code = _kill_tree(proc) or proc.poll()
    reader.join(timeout=5)
    elapsed = time.monotonic() - started
    output = sanitize_text(b"".join(output_chunks).decode("utf-8", errors="replace"),
                           max_len=config.SUITE_MAX_OUTPUT_BYTES)
    if truncated:
        output += "\n…[saída truncada no limite do runner]"

    artifacts = []
    out_path = ctx.artifact_dir / "runner_output.txt"
    out_path.write_text(output, encoding="utf-8")
    artifacts.append({"kind": "runner_output", "filename": "runner_output.txt",
                      "path": str(out_path), "preview": output[-800:]})

    checks: list[dict] = []
    metrics = [count_summary(int(elapsed), name_unit="s",
                             population="duração do subprocesso runner",
                             details={"truncated_output": truncated})]
    warnings: list[str] = []
    state = kill_reason or "unknown"
    summary = ""

    if junit_path.exists():
        try:
            parsed = parse_import("junit-xml", junit_path.read_bytes(), "junit.xml")
            warnings = parsed["warnings"]
            for rec in parsed["records_list"]:
                checks.append({
                    "name": f"{rec['classname']}.{rec['name']}".strip("."),
                    "category": "suite", "status": rec["status"],
                    "expected": "testcase aprovado", "observed": rec["status"],
                    "message": rec["message"] or rec["status"],
                    "evidence": {"detail": (rec.get("detail") or "")[:1500],
                                 "time_s": rec.get("time")},
                    "duration_ms": (rec["time"] or 0) * 1000 if rec.get("time") else None,
                })
            metrics.extend(parsed.get("metrics", []))
            artifacts.append({"kind": "junit", "filename": "junit.xml",
                              "path": str(junit_path),
                              "preview": str(parsed["totals"])})
        except ImportRejected as exc:
            warnings.append(f"JUnit gerado mas rejeitado: {exc.reason}")

    failures = sum(1 for c in checks if c["status"] in ("fail", "error"))
    if kill_reason == "cancelled":
        state = "cancelled"
        summary = (f"Execução cancelada (kill: {kill_action or 'n/a'}); "
                   f"{len(checks)} casos registrados até o cancelamento.")
    elif kill_reason == "timed_out":
        state = "timed_out"
        summary = f"Timeout de {cfg.timeout_s}s atingido (kill: {kill_action})."
    elif not checks:
        state = "error"
        summary = (
            f"Relatório JUnit ausente ou vazio; código de retorno {exit_code}. "
            "Resultado do runner não confirmável — não aprovado."
        )
    elif failures:
        state = "failed"
        summary = f"{failures} de {len(checks)} casos falharam (exit {exit_code})."
    elif exit_code != 0:
        state = "failed"
        summary = (f"Todos os casos leram pass, mas o runner retornou {exit_code}; "
                   "tratado como falha observada.")
    else:
        state = "passed"
        summary = f"{len(checks)} casos aprovados, 0 falhas (exit 0)."

    if warnings:
        ctx.log("info", "avisos de importação: " + " | ".join(warnings[:5]))

    return {
        "state": state, "summary": summary, "checks": checks,
        "findings": [], "metrics": metrics, "artifacts": artifacts,
        "exit_code": int(exit_code) if isinstance(exit_code, int) else None,
        "warnings": warnings,
    }
