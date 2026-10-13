"""Orçamento global: reserva antes do envio, tetos e cancelamento."""

import threading
import time

import pytest

from verificalab.budget import BudgetExceeded, Cancelled, RunBudget


def test_attempt_cap_respected():
    ev = threading.Event()
    budget = RunBudget(rps=100, duration_s=10, max_attempts=3, cancel_event=ev)
    # rps é limitado ao teto global (5); usa-se reserva direta sem taxa esperando
    got = 0
    try:
        for _ in range(10):
            budget.reserve()
            got += 1
    except BudgetExceeded:
        pass
    assert got <= 3
    with pytest.raises(BudgetExceeded):
        budget.reserve()


def test_rps_is_capped_at_global_limit():
    ev = threading.Event()
    budget = RunBudget(rps=999, duration_s=1, max_attempts=150, cancel_event=ev)
    assert budget.rps <= 5.0


def test_duration_and_attempts_capped_at_pilot_limits():
    ev = threading.Event()
    budget = RunBudget(rps=1, duration_s=9999, max_attempts=10_000, cancel_event=ev)
    assert budget.duration_s <= 30
    assert budget.max_attempts <= 150


def test_cancel_raises_before_send():
    ev = threading.Event()
    ev.set()
    budget = RunBudget(rps=5, duration_s=10, max_attempts=10, cancel_event=ev)
    with pytest.raises(Cancelled):
        budget.reserve()


def test_deadline_exceeded_raises():
    ev = threading.Event()
    budget = RunBudget(rps=5, duration_s=0.05, max_attempts=150, cancel_event=ev)
    time.sleep(0.06)
    with pytest.raises(BudgetExceeded):
        budget.reserve()
