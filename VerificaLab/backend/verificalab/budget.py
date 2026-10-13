"""Orçamento global de requisições — reservado ANTES do envio.

Tetos do piloto (config): 5 rps, concorrência 2, 30 s, 150 tentativas.
O rate limiter e o semáforo de concorrência são globais (compartilhados
entre quaisquer workers/executores do processo); duração e tentativas são
por execução. Cancelamento interrompe novas reservas imediatamente.
"""

from __future__ import annotations

import threading
import time
from . import config


class BudgetExceeded(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Cancelled(Exception):
    pass


class _GlobalRateLimiter:
    """Intervalo mínimo entre envios, configurável pela execução ativa."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interval = 1.0 / config.LOAD_DEFAULT_RPS
        self._next_slot = 0.0

    def configure(self, rps: float) -> None:
        rps = max(0.1, min(float(rps), config.LOAD_MAX_RPS))
        with self._lock:
            self._interval = 1.0 / rps

    def acquire(self, cancel_event: threading.Event | None = None) -> None:
        """Bloqueia até o próximo slot; acorda cedo se cancelado."""
        while True:
            with self._lock:
                now = time.monotonic()
                wait = self._next_slot - now
                if wait <= 0:
                    self._next_slot = now + self._interval
                    return
                wake = min(wait, 0.1)
            if cancel_event is not None and cancel_event.wait(wake):
                raise Cancelled("cancelamento solicitado")
            else:
                time.sleep(wake)


GLOBAL_RATE = _GlobalRateLimiter()
GLOBAL_CONCURRENCY = threading.BoundedSemaphore(config.LOAD_MAX_CONCURRENCY)


class RunBudget:
    """Orçamento de uma execução: duração, tentativas, taxa e concorrência.

    Uso: `with budget.slot(): ...envia...` — a reserva acontece antes do envio.
    """

    def __init__(self, rps: float, duration_s: float, max_attempts: int,
                 cancel_event: threading.Event) -> None:
        self.rps = max(0.1, min(float(rps), config.LOAD_MAX_RPS))
        self.duration_s = min(float(duration_s), config.LOAD_MAX_DURATION_S)
        self.max_attempts = min(int(max_attempts), config.LOAD_MAX_ATTEMPTS)
        self.cancel_event = cancel_event
        self.attempts = 0
        self._lock = threading.Lock()
        self.deadline = time.monotonic() + self.duration_s
        GLOBAL_RATE.configure(self.rps)

    def reserve(self) -> None:
        """Reserva 1 tentativa + slot de taxa. Pode bloquear; lança Cancelled/BudgetExceeded."""
        if self.cancel_event.is_set():
            raise Cancelled("cancelamento solicitado")
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("duração máxima atingida")
        with self._lock:
            if self.attempts >= self.max_attempts:
                raise BudgetExceeded("total máximo de tentativas atingido")
            self.attempts += 1
        try:
            GLOBAL_RATE.acquire(self.cancel_event)
        except Cancelled:
            with self._lock:
                self.attempts -= 1
            raise
        if self.cancel_event.is_set():
            with self._lock:
                self.attempts -= 1
            raise Cancelled("cancelamento solicitado")

    class _Slot:
        def __init__(self, budget: "RunBudget") -> None:
            self.budget = budget

        def __enter__(self):
            self.budget.reserve()
            if not GLOBAL_CONCURRENCY.acquire(timeout=30):
                with self.budget._lock:
                    self.budget.attempts -= 1
                raise BudgetExceeded("concorrência global esgotada")
            if self.budget.cancel_event.is_set():
                GLOBAL_CONCURRENCY.release()
                with self.budget._lock:
                    self.budget.attempts -= 1
                raise Cancelled("cancelamento solicitado")
            return self

        def __exit__(self, *exc):
            GLOBAL_CONCURRENCY.release()
            return False

    def slot(self) -> "RunBudget._Slot":
        return RunBudget._Slot(self)

    @property
    def remaining_attempts(self) -> int:
        with self._lock:
            return max(0, self.max_attempts - self.attempts)
