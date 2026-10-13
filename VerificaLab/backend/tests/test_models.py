"""Validação dos contratos: limites de carga, suite e checks HTTP."""

import pytest
from pydantic import ValidationError

from verificalab.models import (HttpProfileConfig, LoadProfileConfig,
                                ProfileIn, SuiteProfileConfig)


def test_load_rps_above_cap_rejected():
    with pytest.raises(ValidationError) as exc:
        LoadProfileConfig(rps=50)
    assert "teto" in str(exc.value)


def test_load_duration_above_cap_rejected():
    with pytest.raises(ValidationError):
        LoadProfileConfig(duration_s=120)


def test_load_concurrency_above_cap_rejected():
    with pytest.raises(ValidationError):
        LoadProfileConfig(concurrency=8)


def test_load_attempts_above_cap_rejected():
    with pytest.raises(ValidationError):
        LoadProfileConfig(max_attempts=10_000)


def test_load_post_method_rejected():
    with pytest.raises(ValidationError):
        LoadProfileConfig(method="POST")


def test_load_defaults_within_limits():
    cfg = LoadProfileConfig()
    assert cfg.rps <= 5 and cfg.concurrency <= 2
    assert cfg.duration_s <= 30 and cfg.max_attempts <= 150
    assert cfg.method in ("GET", "HEAD")


def test_suite_command_outside_allowlist_rejected():
    with pytest.raises(ValidationError) as exc:
        SuiteProfileConfig(command=["bash", "-c", "rm -rf /"], cwd="/tmp")
    assert "pré-configurada" in str(exc.value) or "lista" in str(exc.value)


def test_suite_junitxml_argument_rejected():
    with pytest.raises(ValidationError):
        SuiteProfileConfig(command=["python3", "-m", "pytest",
                                    "--junitxml=/tmp/x.xml"], cwd="/tmp")


def test_suite_cwd_outside_allowed_roots_rejected():
    with pytest.raises(ValidationError) as exc:
        SuiteProfileConfig(command=["python3", "-m", "pytest"], cwd="/etc")
    assert "raízes" in str(exc.value)


def test_http_check_requires_fields_for_json():
    with pytest.raises(ValidationError):
        HttpProfileConfig(checks=[{"name": "a", "type": "json_fields",
                                   "path": "/json"}])


def test_http_check_max_time_requires_seconds():
    with pytest.raises(ValidationError):
        HttpProfileConfig(checks=[{"name": "a", "type": "max_time", "path": "/"}])


def test_profile_in_validates_config_by_kind():
    p = ProfileIn(project_id="prj", name="carga", kind="load",
                  config={"rps": 2, "duration_s": 5})
    assert p.config["concurrency"] == 1
    with pytest.raises(ValidationError):
        ProfileIn(project_id="prj", name="carga2", kind="load",
                  config={"rps": 99})
