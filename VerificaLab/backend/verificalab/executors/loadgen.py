"""Gerador HTTP próprio de carga leve para o laboratório local.

Limites do piloto (teto fixo): 5 rps, concorrência 2, 30 s, 150 tentativas,
GET/HEAD apenas, sem proxy, sem raw socket, sem amplificação, sem tráfego
distribuído. O orçamento é reservado ANTES de cada envio e compartilhado
globalmente (budget.GLOBAL_RATE / GLOBAL_CONCURRENCY).

Critério de sucesso: respostas conforme expectativa — NUNCA indisponibilidade
ou "máximo tráfego".
"""

from __future__ import annotations

import threading
import time

from ..budget import BudgetExceeded, Cancelled, RunBudget
from ..metrics import count_summary, latency_summary, rate_summary
from ..models import LoadProfileConfig
from ..targetpolicy import TargetPolicy
from .common import make_client, send_checked


def run_load(ctx) -> dict:
    cfg = LoadProfileConfig.model_validate(ctx.cfg)
    env = ctx.env
    policy = TargetPolicy(env["scheme"], env["host"], env["port"])
    url = policy.build(cfg.path)

    budget = RunBudget(cfg.rps, cfg.duration_s, cfg.max_attempts, ctx.cancel_event)
    headers: dict[str, str] = {}
    if ctx.secret_header and env.get("secret_header_name"):
        headers[env["secret_header_name"]] = ctx.secret_header

    lock = threading.Lock()
    latencies: list[float] = []
    counts = {"ok": 0, "bad_status": 0, "timeout": 0, "connection_error": 0,
              "other_error": 0}
    samples: list[dict] = []
    stop_reason: str | None = None
    cancelled = threading.Event()

    def stop(reason: str, was_cancel: bool = False) -> None:
        nonlocal stop_reason
        with lock:
            if stop_reason is None:
                stop_reason = reason
        if was_cancel:
            cancelled.set()

    def worker_loop() -> None:
        client = make_client(cfg.timeout_s)
        try:
            while True:
                if ctx.cancel_event.is_set():
                    stop("cancelamento solicitado", True)
                    return
                if time.monotonic() >= budget.deadline:
                    stop("duração máxima atingida")
                    return
                try:
                    with budget.slot():          # reserva ANTES do envio
                        out = send_checked(client, policy, url,
                                           method=cfg.method, headers=headers)
                except Cancelled:
                    stop("cancelamento solicitado", True)
                    return
                except BudgetExceeded as exc:
                    stop(exc.reason)
                    return
                with lock:
                    if out.error == "timeout":
                        counts["timeout"] += 1
                    elif out.error == "connection_error":
                        counts["connection_error"] += 1
                    elif out.error:
                        counts["other_error"] += 1
                    elif out.status == cfg.expect_status:
                        counts["ok"] += 1
                        latencies.append(out.duration_ms or 0.0)
                    else:
                        counts["bad_status"] += 1
                        if len(samples) < 10:
                            samples.append({"status": out.status,
                                            "duration_ms": out.duration_ms})
                    attempts = budget.attempts
                ctx.set_progress(min(0.99, attempts / max(1, budget.max_attempts)))

        finally:
            client.close()

    n_threads = max(1, min(cfg.concurrency, 2))
    threads = [threading.Thread(target=worker_loop, name=f"load-{i}", daemon=True)
               for i in range(n_threads)]
    started = time.monotonic()
    for t in threads:
        t.start()
    hard_deadline = started + cfg.duration_s + cfg.timeout_s + 10
    for t in threads:
        remaining = max(0.1, hard_deadline - time.monotonic())
        t.join(timeout=remaining)
    alive = [t for t in threads if t.is_alive()]
    elapsed = time.monotonic() - started

    total_sent = sum(counts.values())
    if cancelled.is_set() or ctx.cancel_event.is_set():
        state = "cancelled"
        summary = (f"Cancelado após {total_sent} tentativas "
                   f"({stop_reason or 'cancel'}).")
    elif alive:
        state = "timed_out"
        summary = "Limite de duração excedido; threads ativas abandonadas."
    elif total_sent == 0:
        state = "error"
        summary = f"Runner não conseguiu enviar requisições ({stop_reason})."
    elif counts["ok"] == total_sent:
        state = "passed"
        summary = (f"{counts['ok']}/{total_sent} respostas conforme expectativa "
                   f"({stop_reason or 'concluído'}).")
    else:
        state = "failed"
        summary = (f"{total_sent - counts['ok']} de {total_sent} tentativas fora "
                   f"da expectativa ({stop_reason or 'concluído'}).")

    failure_total = (counts["bad_status"] + counts["timeout"]
                     + counts["connection_error"] + counts["other_error"])
    latency = latency_summary(
        latencies,
        population=f"requisições concluídas com status {cfg.expect_status} "
                   f"(ida e volta observada pelo cliente)",
        discarded=counts["timeout"] + counts["connection_error"]
                  + counts["other_error"],
    )
    latency["name"] = "latency_load_ms"
    rate = rate_summary(counts["ok"], elapsed,
                        population="respostas conforme expectativa / duração "
                                   "observada")
    rate["name"] = "rate_completed_rps"
    failed = count_summary(failure_total, name_unit="tentativas",
                           population="tentativas fora da expectativa",
                           details={**counts, "stop_reason": stop_reason,
                                    "expected_status": cfg.expect_status})
    failed["name"] = "count_failed_attempts"
    metrics = [latency, rate, failed]
    return {
        "state": state,
        "summary": summary,
        "checks": [],
        "findings": [],
        "metrics": metrics,
        "artifacts": [],
        "evidence_samples": samples,
    }
