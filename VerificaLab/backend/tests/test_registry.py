"""Testes do catálogo YAML de ferramentas."""

from __future__ import annotations

from copy import deepcopy

import pytest
import yaml

from verificalab.stress.registry import (
    DefaultLimits,
    ToolRegistry,
    ToolRegistryError,
)


@pytest.fixture
def registry_root(tmp_path):
    (tmp_path / "sample").mkdir()
    (tmp_path / "sample" / "tool.py").write_text("# tool\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def tool_data():
    return {
        "id": "sample",
        "name": "Sample Tool",
        "path": "sample/tool.py",
        "language": "python",
        "layer": "L7",
        "requires_root": False,
        "description": "Local test tool.",
        "when_to_use": "Use only in an authorized local lab.",
        "example": "python3 sample/tool.py --help",
        "risks": ["May generate traffic."],
        "default_limits": {
            "duration_s": 5,
            "threads": 1,
            "rate_limit": "low",
        },
    }


def load_data(tmp_path, root, data):
    config = tmp_path / "tools.yaml"
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    return ToolRegistry.from_yaml(config, root=root)


def test_default_catalog_contains_all_eight_tools():
    registry = ToolRegistry.load()

    assert len(registry.all()) == 8
    assert {tool.id for tool in registry.all()} == {
        "slowloris",
        "pyddos",
        "ddoslayer",
        "impulse",
        "overload",
        "mhddos",
        "ufonet",
        "mikumikubeam",
    }


def test_default_catalog_has_safe_typed_limits():
    registry = ToolRegistry.from_yaml()

    assert all(isinstance(tool.default_limits, DefaultLimits) for tool in registry.all())
    assert all(tool.default_limits.duration_s <= 30 for tool in registry.all())
    assert all(tool.default_limits.threads <= 2 for tool in registry.all())
    assert all(tool.description.strip() and tool.when_to_use.strip() for tool in registry.all())
    assert all(tool.example.strip() and tool.risks for tool in registry.all())


def test_default_catalog_matches_expected_layers_root_and_languages():
    registry = ToolRegistry.load()

    assert {
        tool.id: (tool.layer, tool.requires_root, tool.language)
        for tool in registry.all()
    } == {
        "slowloris": ("L7", False, "python"),
        "pyddos": ("L4+L7", False, "python"),
        "ddoslayer": ("L4+L7", True, "python"),
        "impulse": ("L4+L7", True, "python"),
        "overload": ("L4+L2", True, "python"),
        "mhddos": ("L4+L7", True, "python"),
        "ufonet": ("L3", False, "python"),
        "mikumikubeam": ("L7", False, "go"),
    }


def test_registry_get_returns_the_requested_tool():
    registry = ToolRegistry.load()

    assert registry.get("slowloris").language == "python"
    assert registry.get("not-present") is None


def test_all_can_filter_by_layer():
    registry = ToolRegistry.load()

    assert {tool.id for tool in registry.all(layer="L3")} == {"ufonet"}
    assert {tool.id for tool in registry.all(layer="L7")} == {"slowloris", "mikumikubeam"}


def test_installed_returns_only_existing_catalog_paths():
    registry = ToolRegistry.load()

    assert {tool.id for tool in registry.installed()} == {
        "slowloris",
        "pyddos",
        "ddoslayer",
        "impulse",
        "overload",
        "mhddos",
        "ufonet",
        "mikumikubeam",
    }


def test_custom_catalog_loads_typed_tool(tmp_path, registry_root, tool_data):
    registry = load_data(tmp_path, registry_root, [tool_data])

    assert registry.get("sample").default_limits == DefaultLimits(5, 1, "low")
    assert registry.get("sample").risks == ("May generate traffic.",)


def test_yaml_root_must_be_a_list(tmp_path, registry_root):
    config = tmp_path / "tools.yaml"
    config.write_text("{}", encoding="utf-8")

    with pytest.raises(ToolRegistryError, match="deve ser uma lista"):
        ToolRegistry.from_yaml(config, root=registry_root)


def test_empty_catalog_is_rejected(tmp_path, registry_root):
    with pytest.raises(ToolRegistryError, match="ao menos uma"):
        load_data(tmp_path, registry_root, [])


def test_invalid_yaml_is_reported(tmp_path, registry_root):
    config = tmp_path / "tools.yaml"
    config.write_text("- id: [\n", encoding="utf-8")

    with pytest.raises(ToolRegistryError, match="YAML inválido"):
        ToolRegistry.from_yaml(config, root=registry_root)


def test_missing_required_field_is_rejected(tmp_path, registry_root, tool_data):
    del tool_data["example"]

    with pytest.raises(ToolRegistryError, match="campos obrigatórios ausentes"):
        load_data(tmp_path, registry_root, [tool_data])


def test_unknown_tool_field_is_rejected(tmp_path, registry_root, tool_data):
    tool_data["unexpected"] = True

    with pytest.raises(ToolRegistryError, match="campos desconhecidos"):
        load_data(tmp_path, registry_root, [tool_data])


def test_duplicate_ids_are_rejected(tmp_path, registry_root, tool_data):
    with pytest.raises(ToolRegistryError, match="identificador duplicado"):
        load_data(tmp_path, registry_root, [tool_data, deepcopy(tool_data)])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("language", "rust", "language"),
        ("layer", "L2", "layer"),
        ("requires_root", "false", "requires_root"),
        ("default_limits", {"duration_s": 31, "threads": 1, "rate_limit": "low"}, "duration_s"),
        ("default_limits", {"duration_s": 5, "threads": 3, "rate_limit": "low"}, "threads"),
        ("default_limits", {"duration_s": True, "threads": 1, "rate_limit": "low"}, "duration_s"),
        ("default_limits", {"duration_s": 5, "threads": 1, "rate_limit": "high"}, "rate_limit"),
    ],
)
def test_invalid_field_values_are_rejected(
    tmp_path, registry_root, tool_data, field, value, message
):
    tool_data[field] = value

    with pytest.raises(ToolRegistryError, match=message):
        load_data(tmp_path, registry_root, [tool_data])


def test_empty_risks_are_rejected(tmp_path, registry_root, tool_data):
    tool_data["risks"] = []

    with pytest.raises(ToolRegistryError, match="risks"):
        load_data(tmp_path, registry_root, [tool_data])


@pytest.mark.parametrize(
    "tool_path", ["../outside.py", "/etc/passwd", "missing.py", "bad\0path"]
)
def test_unsafe_or_missing_tool_path_marks_tool_uninstalled(
    tmp_path, registry_root, tool_data, tool_path
):
    tool_data["path"] = tool_path

    registry = load_data(tmp_path, registry_root, [tool_data])

    assert registry.get("sample") is not None
    assert registry.get("sample").installed is False
