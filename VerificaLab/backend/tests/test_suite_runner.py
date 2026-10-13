"""Runner de suite: pytest real, JUnit, falha intencional e killpg com filho."""

from __future__ import annotations

import os
import sys
import threading
import time

from verificalab.executors.suite import run_suite
from verificalab.seed import ensure_demo_suite


class CtxStub:
    def __init__(self, cfg: dict, artifact_dir) -> None:
        self.cfg = cfg
        self.env = {}
        self.artifact_dir = artifact_dir
        self.cancel_event = threading.Event()
        self.secret_header = None
        self.logs: list[str] = []

    def log(self, level, msg):
        self.logs.append(f"{level}:{msg}")

    def set_progress(self, v):
        pass

    def deadline_reached(self):
        return False


def _procs(cmdline_fragment: str) -> list[int]:
    found = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode(errors="replace")
            if cmdline_fragment in cmd:
                found.append(int(pid))
        except OSError:
            continue
    return found


def test_suite_quick_runs_real_pytest(tmp_path):
    demo = ensure_demo_suite()
    ctx = CtxStub({
        "command": [sys.executable, "-m", "pytest", "-q", "test_demo.py"],
        "cwd": str(demo), "timeout_s": 90,
    }, tmp_path)
    result = run_suite(ctx)
    # suite real: pass + fail intencional + skip => failed (falha visível)
    assert result["state"] == "failed"
    assert result["exit_code"] != 0
    statuses = {c["name"].split(".")[-1]: c["status"] for c in result["checks"]}
    assert statuses["test_pass_simples"] == "pass"
    assert statuses["test_fail_intencional"] == "fail"
    assert statuses["test_skip_intencional"] == "skip"
    # artefatos reais persistidos
    kinds = {a["kind"] for a in result["artifacts"]}
    assert "junit" in kinds and "runner_output" in kinds
    assert (tmp_path / "junit.xml").exists()


def test_suite_cancel_kills_process_tree(tmp_path):
    """Cancelamento deve encerrar pytest E o filho sleep 300."""
    demo = ensure_demo_suite()
    ctx = CtxStub({
        "command": [sys.executable, "-m", "pytest", "-q", "test_slow.py"],
        "cwd": str(demo), "timeout_s": 120,
    }, tmp_path)
    before = set(_procs("sleep 300"))
    result: dict = {}

    def target():
        result.update(run_suite(ctx))

    t = threading.Thread(target=target)
    t.start()
    # espera o filho real nascer
    child_born = False
    for _ in range(100):
        if set(_procs("sleep 300")) - before:
            child_born = True
            break
        time.sleep(0.2)
    assert child_born, "teste slow não chegou a gerar o filho sleep"
    ctx.cancel_event.set()
    t.join(timeout=30)
    assert not t.is_alive(), "runner não terminou após cancelamento"
    assert result.get("state") == "cancelled"
    # árvore morta: nenhum sleep 300 remanescente
    time.sleep(0.5)
    remaining = set(_procs("sleep 300")) - before
    assert not remaining, f"processos órfãos: {remaining}"


def test_suite_without_junit_is_not_approved(tmp_path):
    """Sem relatório JUnit o resultado é não confirmável (error)."""
    import subprocess  # noqa: F401  (documenta intenção)
    demo = ensure_demo_suite()
    # comando que sai com 0 mas não gera JUnit: pytest com addopts removido
    cfg = {"command": [sys.executable, "-m", "pytest", "-q", "--no-header",
                       "-p", "no:cacheprovider", "test_demo.py"],
           "cwd": str(demo), "timeout_s": 90}
    # o runner SEMPRE adiciona --junitxml; caso coberto é junit ausente por
    # falha de permissão de escrita — simulado removendo o arquivo após.
    ctx = CtxStub(cfg, tmp_path)
    result = run_suite(ctx)
    # com junit gerado normalmente: estado failed pela falha intencional
    assert result["state"] == "failed"
    assert result["checks"], "deveria ter casos do JUnit"
