"""Contratos comuns dos adapters de stress."""

from __future__ import annotations

from importlib import import_module
import os
import sys
from pathlib import Path

import pytest

from verificalab.core.authorization import AuthorizationError
from verificalab.stress.base import (
    AdapterExecutionError,
    StressAdapter,
    StressRequest,
)
from verificalab.stress.registry import ToolRegistry
from tests.fixtures.local_http import local_http

TOOL_IDS = (
    "ddoslayer",
    "mhddos",
    "impulse",
    "overload",
    "pyddos",
    "ufonet",
    "mikumikubeam",
    "slowloris",
)
FAIL_CLOSED_IDS = {"ddoslayer", "overload", "ufonet"}


def adapter_for(tool_id: str) -> StressAdapter:
    return ToolRegistry.load().adapter_for(tool_id)


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_adapter_for_returns_expected_adapter(tool_id):
    adapter = adapter_for(tool_id)

    assert isinstance(adapter, StressAdapter)
    assert adapter.tool_id == tool_id


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_clamp_respects_catalog_limits(tool_id):
    adapter = adapter_for(tool_id)
    tool = ToolRegistry.load()[tool_id]
    limits = tool.max_limits or tool.default_limits

    limited = adapter.clamp(
        StressRequest("127.0.0.1:8477", duration_s=999, threads=999)
    )

    assert limited.duration_s == limits.duration_s
    assert limited.threads == limits.threads


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_clamp_never_increases_requested_values(tool_id):
    adapter = adapter_for(tool_id)

    limited = adapter.clamp(
        StressRequest("127.0.0.1:8477", duration_s=1, threads=1)
    )

    assert limited.duration_s == 1
    assert limited.threads == 1


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_build_cmd_requires_loopback_and_only_supported_cli(tool_id):
    adapter = adapter_for(tool_id)
    request = StressRequest("127.0.0.1:8477", duration_s=1, threads=1)

    if tool_id in FAIL_CLOSED_IDS:
        with pytest.raises(AdapterExecutionError):
            adapter.build_cmd(request)
    else:
        command = adapter.build_cmd(request)
        target = "http://127.0.0.1:8477/"
        if tool_id == "mhddos":
            assert command[2:] == ["GET", target, "0", "1", "0", "1", "1"]
        elif tool_id == "impulse":
            assert command == [
                sys.executable,
                str(adapter._tool_path()),
                "--target",
                target,
                "--method",
                "HTTP",
                "--time",
                "1",
                "--threads",
                "1",
            ]
        elif tool_id == "mikumikubeam":
            assert command == [
                "env",
                "HOME=/dev/null",
                f"GOMODCACHE={os.environ.get('GOMODCACHE', Path.home() / 'go/pkg/mod')}",
                f"GOCACHE={os.environ.get('GOCACHE', Path.home() / '.cache/go-build')}",
                "GOTOOLCHAIN=local",
                "GOPROXY=off",
                "go",
                "-C",
                str(adapter._tool_path().parent.parent),
                "run",
                "./cmd/mmb-cli",
                "attack",
                "--duration",
                "1",
                "--delay",
                "1000",
                "--packet-size",
                "512",
                "--threads",
                "1",
                "--no-proxy",
                "http_flood",
                target,
            ]
        elif tool_id == "slowloris":
            assert command == [
                sys.executable,
                str(adapter._tool_path()),
                "127.0.0.1",
                "--port",
                "8477",
                "--sockets",
                "1",
            ]


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_build_cmd_rejects_unreviewed_extra_args(tool_id):
    adapter = adapter_for(tool_id)

    with pytest.raises(ValueError, match="extra_args"):
        adapter.build_cmd(
            StressRequest(
                "127.0.0.1:8477",
                duration_s=1,
                threads=1,
                extra_args=("--proxy", "attacker-controlled"),
            )
        )


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_build_cmd_rejects_external_targets(tool_id):
    adapter = adapter_for(tool_id)

    with pytest.raises(ValueError, match="loopback"):
        adapter.build_cmd(StressRequest("example.com", duration_s=1, threads=1))


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_run_checks_authorization_before_other_gates(tool_id, monkeypatch):
    adapter = adapter_for(tool_id)

    def reject_authorization(target):
        assert target == "example.com"
        raise AuthorizationError("sem autorização")

    monkeypatch.setattr(
        "verificalab.stress.base.authorization.require_authorization",
        reject_authorization,
    )
    with pytest.raises(AuthorizationError, match="sem autorização"):
        adapter.run(StressRequest("example.com", duration_s=1, threads=1))


@pytest.mark.parametrize("tool_id", TOOL_IDS, ids=TOOL_IDS)
def test_requires_root_tools_refuse_without_privileges(tool_id, monkeypatch):
    tool = ToolRegistry.load()[tool_id]
    if not tool.requires_root:
        pytest.skip("ferramenta não requer root")

    adapter = adapter_for(tool_id)
    monkeypatch.setattr(
        "verificalab.stress.base.StressAdapter._has_root",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "verificalab.stress.base.StressAdapter._execute",
        staticmethod(lambda command, req: pytest.fail("não deveria executar")),
    )
    monkeypatch.setattr(
        "verificalab.stress.base.authorization.require_authorization",
        lambda target: None,
    )

    with pytest.raises(PermissionError, match="root"):
        adapter.run(StressRequest("127.0.0.1:8477", duration_s=1, threads=1))


def test_adapter_for_slowloris_returns_existing_adapter():
    adapter = ToolRegistry.load().adapter_for("slowloris")

    assert type(adapter).__name__ == "SlowlorisAdapter"


def test_adapter_for_unknown_tool_raises_key_error():
    with pytest.raises(KeyError):
        ToolRegistry.load().adapter_for("inexistente")


def test_mikumikubeam_executes_against_local_lab(local_http):
    adapter = adapter_for("mikumikubeam")
    result = adapter.run(
        StressRequest(local_http.target, duration_s=1, threads=1)
    )

    assert result.returncode == 0
    assert not result.timeout
    assert "[lab] " in local_http.new_log_lines()


def test_all_catalog_adapters_instantiate():
    registry = ToolRegistry.load()

    assert len(registry.all()) == 8
    for tool in registry.all():
        adapter = registry.adapter_for(tool.id)
        module_name, class_name = {
            "slowloris": ("slowloris", "SlowlorisAdapter"),
            "ddoslayer": ("ddoslayer", "DDoSlayerAdapter"),
            "mhddos": ("mhddos", "MHDDOSAdapter"),
            "impulse": ("impulse", "ImpulseAdapter"),
            "overload": ("overload", "OverloadAdapter"),
            "pyddos": ("pyddos", "PyDDoSAdapter"),
            "ufonet": ("ufonet", "UFONetAdapter"),
            "mikumikubeam": ("mikumikubeam", "MikuMikuBeamAdapter"),
        }[tool.id]
        expected_type = getattr(
            import_module(f"verificalab.stress.adapters.{module_name}"), class_name
        )
        assert isinstance(adapter, expected_type)
