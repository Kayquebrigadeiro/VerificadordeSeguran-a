"""Executor HTTP contra o laboratório real (thread), sem rede externa."""

from __future__ import annotations

import threading

import pytest

from verificalab import config
from verificalab.executors.httpchecks import run_http_checks


class CtxStub:
    def __init__(self, cfg: dict, env: dict) -> None:
        self.cfg = cfg
        self.env = env
        self.cancel_event = threading.Event()
        self.secret_header = None
        self._progress = 0.0
        self.logs: list[str] = []

    def log(self, level, msg):
        self.logs.append(f"{level}:{msg}")

    def set_progress(self, v):
        self._progress = v

    def deadline_reached(self):
        return False


@pytest.fixture(scope="module")
def env_row(lab_server):
    return {"id": "env-test", "scheme": "http", "host": "127.0.0.1",
            "port": config.LAB_PORT, "secret_header_name": None}


def test_contract_pass_and_intentional_fail(env_row):
    ctx = CtxStub({
        "checks": [
            {"name": "ok200", "type": "status", "path": "/ok",
             "expected_status": 200},
            {"name": "json", "type": "json_fields", "path": "/json",
             "expected_status": 200,
             "fields": [{"path": "service", "equals": "verificalab-lab"}]},
            {"name": "espera_201_intencional", "type": "status", "path": "/ok",
             "expected_status": 201},
        ],
        "include_config_checks": False, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    by_name = {c["name"]: c["status"] for c in result["checks"]}
    assert by_name["ok200"] == "pass"
    assert by_name["json"] == "pass"
    assert by_name["espera_201_intencional"] == "fail"  # falha intencional visível


def test_redirect_external_blocked_before_call(env_row):
    ctx = CtxStub({
        "checks": [{"name": "redirect_ext", "type": "status",
                    "path": "/redirect-external", "expected_status": 200}],
        "include_config_checks": False, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    chk = result["checks"][0]
    assert chk["status"] == "fail"
    assert "redirect recusado" in chk["message"]
    assert chk["evidence"]["response"]["blocked_redirect"]


def test_redirect_local_followed(env_row):
    ctx = CtxStub({
        "checks": [{"name": "redirect_local", "type": "status",
                    "path": "/redirect-local", "expected_status": 200}],
        "include_config_checks": False, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    assert result["checks"][0]["status"] == "pass"


def test_slow_within_limit_and_timeout_observable(env_row):
    ctx = CtxStub({
        "checks": [
            {"name": "lenta_ok", "type": "max_time", "path": "/slow?delay=0.4",
             "max_seconds": 3.0, "expected_status": 200},
            {"name": "timeout_observado", "type": "max_time",
             "path": "/slow?delay=3", "max_seconds": 0.5, "expected_status": 200},
        ],
        "include_config_checks": False, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    by_name = {c["name"]: c["status"] for c in result["checks"]}
    assert by_name["lenta_ok"] == "pass"
    assert by_name["timeout_observado"] == "fail"


def test_config_observations_are_informational(env_row):
    ctx = CtxStub({
        "checks": [{"name": "headers", "type": "status", "path": "/headers",
                    "expected_status": 200}],
        "include_config_checks": True, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    assert result["findings"], "esperava achados informativos de configuração"
    assert all(f["severity"] == "info" for f in result["findings"])
    assert any("não uma vulnerabilidade comprovada" in f["description"]
               for f in result["findings"])
    obs = [c for c in result["checks"]
           if c["name"] == "observacao_cabecalhos_configuracao"]
    assert obs and obs[0]["status"] == "unknown"


def test_connection_drop_is_observed_failure(env_row):
    ctx = CtxStub({
        "checks": [{"name": "drop", "type": "status", "path": "/drop",
                    "expected_status": 200}],
        "include_config_checks": False, "timeout_s": 5,
    }, env_row)
    result = run_http_checks(ctx)
    chk = result["checks"][0]
    assert chk["status"] == "fail"          # observação: não respondeu como esperado
    assert chk["observed"] in ("transport_error", "connection_error", "timeout")
