"""Carregamento validado do catálogo declarativo de ferramentas de stress."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Iterable, Iterator, Literal, Mapping

import yaml

if TYPE_CHECKING:
    from verificalab.stress.base import StressAdapter

Language = Literal["python", "go"]
Layer = Literal["L3", "L4", "L7", "L4+L2", "L4+L7"]
RateLimit = Literal["low", "medium"]

_TOOL_FIELDS = {
    "id",
    "name",
    "path",
    "language",
    "layer",
    "requires_root",
    "description",
    "when_to_use",
    "example",
    "risks",
    "default_limits",
    "max_limits",
}
_REQUIRED_TOOL_FIELDS = _TOOL_FIELDS - {"max_limits"}
_LIMIT_FIELDS = {"duration_s", "threads", "rate_limit"}
_MAX_LIMIT_FIELDS = {"duration_s", "threads"}
_SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ADAPTER_TYPES = {
    "slowloris": ("verificalab.stress.adapters.slowloris", "SlowlorisAdapter"),
    "ddoslayer": ("verificalab.stress.adapters.ddoslayer", "DDoSlayerAdapter"),
    "mhddos": ("verificalab.stress.adapters.mhddos", "MHDDOSAdapter"),
    "impulse": ("verificalab.stress.adapters.impulse", "ImpulseAdapter"),
    "overload": ("verificalab.stress.adapters.overload", "OverloadAdapter"),
    "pyddos": ("verificalab.stress.adapters.pyddos", "PyDDoSAdapter"),
    "ufonet": ("verificalab.stress.adapters.ufonet", "UFONetAdapter"),
    "mikumikubeam": (
        "verificalab.stress.adapters.mikumikubeam",
        "MikuMikuBeamAdapter",
    ),
}


class ToolRegistryError(ValueError):
    """O catálogo YAML existe, mas não satisfaz o esquema esperado."""


@dataclass(frozen=True, slots=True)
class DefaultLimits:
    duration_s: int
    threads: int
    rate_limit: RateLimit


@dataclass(frozen=True, slots=True)
class MaxLimits:
    duration_s: int
    threads: int


@dataclass(frozen=True, slots=True)
class Tool:
    id: str
    name: str
    path: str
    language: Language
    layer: Layer
    requires_root: bool
    description: str
    when_to_use: str
    example: str
    risks: tuple[str, ...]
    default_limits: DefaultLimits
    max_limits: MaxLimits | None
    installed: bool


def _require_text(value: object, field: str, tool_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolRegistryError(f"{tool_id}: '{field}' deve ser texto não vazio")
    return value.strip()


def _parse_tool(data: object, root: Path) -> Tool:
    if not isinstance(data, dict):
        raise ToolRegistryError("cada ferramenta deve ser um objeto YAML")

    tool_id = _require_text(data.get("id"), "id", "<desconhecida>")
    unknown = set(data) - _TOOL_FIELDS
    missing = _REQUIRED_TOOL_FIELDS - set(data)
    if unknown:
        raise ToolRegistryError(f"{tool_id}: campos desconhecidos: {sorted(unknown)}")
    if missing:
        raise ToolRegistryError(f"{tool_id}: campos obrigatórios ausentes: {sorted(missing)}")
    if not _SLUG_PATTERN.fullmatch(tool_id):
        raise ToolRegistryError(f"{tool_id}: 'id' deve ser um slug em minúsculas")

    name = _require_text(data["name"], "name", tool_id)
    tool_path = _require_text(data["path"], "path", tool_id)
    path_parts = Path(tool_path)
    installed = False
    if not path_parts.is_absolute() and ".." not in path_parts.parts and "\\" not in tool_path:
        try:
            resolved_path = (root / path_parts).resolve()
            resolved_path.relative_to(root)
            installed = resolved_path.exists()
        except (OSError, RuntimeError, ValueError):
            pass

    language = data["language"]
    if language not in ("python", "go"):
        raise ToolRegistryError(f"{tool_id}: 'language' deve ser 'python' ou 'go'")
    layer = data["layer"]
    if layer not in ("L3", "L4", "L7", "L4+L2", "L4+L7"):
        raise ToolRegistryError(f"{tool_id}: 'layer' inválida: {layer!r}")
    requires_root = data["requires_root"]
    if not isinstance(requires_root, bool):
        raise ToolRegistryError(f"{tool_id}: 'requires_root' deve ser booleano")

    description = _require_text(data["description"], "description", tool_id)
    when_to_use = _require_text(data["when_to_use"], "when_to_use", tool_id)
    example = _require_text(data["example"], "example", tool_id)
    risks_value = data["risks"]
    if (
        not isinstance(risks_value, list)
        or not risks_value
        or any(not isinstance(risk, str) or not risk.strip() for risk in risks_value)
    ):
        raise ToolRegistryError(f"{tool_id}: 'risks' deve ser uma lista de textos não vazios")

    limits = data["default_limits"]
    if not isinstance(limits, dict):
        raise ToolRegistryError(f"{tool_id}: 'default_limits' deve ser um objeto")
    missing_limits = _LIMIT_FIELDS - set(limits)
    unknown_limits = set(limits) - _LIMIT_FIELDS
    if missing_limits or unknown_limits:
        raise ToolRegistryError(
            f"{tool_id}: campos de default_limits inválidos "
            f"(ausentes: {sorted(missing_limits)}, desconhecidos: {sorted(unknown_limits)})"
        )
    duration_s = limits["duration_s"]
    threads = limits["threads"]
    if type(duration_s) is not int or not 1 <= duration_s <= 30:
        raise ToolRegistryError(f"{tool_id}: 'duration_s' deve estar entre 1 e 30")
    if type(threads) is not int or not 1 <= threads <= 2:
        raise ToolRegistryError(f"{tool_id}: 'threads' deve estar entre 1 e 2")
    rate_limit = limits["rate_limit"]
    if rate_limit not in ("low", "medium"):
        raise ToolRegistryError(f"{tool_id}: 'rate_limit' deve ser 'low' ou 'medium'")

    max_limits = None
    if "max_limits" in data:
        max_value = data["max_limits"]
        if not isinstance(max_value, dict):
            raise ToolRegistryError(f"{tool_id}: 'max_limits' deve ser um objeto")
        missing_max = _MAX_LIMIT_FIELDS - set(max_value)
        unknown_max = set(max_value) - _MAX_LIMIT_FIELDS
        if missing_max or unknown_max:
            raise ToolRegistryError(
                f"{tool_id}: campos de max_limits inválidos "
                f"(ausentes: {sorted(missing_max)}, desconhecidos: {sorted(unknown_max)})"
            )
        max_duration = max_value["duration_s"]
        max_threads = max_value["threads"]
        if (
            type(max_duration) is not int
            or not duration_s <= max_duration <= 30
        ):
            raise ToolRegistryError(
                f"{tool_id}: max_limits.duration_s deve estar entre "
                f"{duration_s} e 30"
            )
        if type(max_threads) is not int or not threads <= max_threads <= 50:
            raise ToolRegistryError(
                f"{tool_id}: max_limits.threads deve estar entre {threads} e 50"
            )
        max_limits = MaxLimits(max_duration, max_threads)

    return Tool(
        id=tool_id,
        name=name,
        path=tool_path,
        language=language,
        layer=layer,
        requires_root=requires_root,
        description=description,
        when_to_use=when_to_use,
        example=example,
        risks=tuple(risk.strip() for risk in risks_value),
        default_limits=DefaultLimits(
            duration_s=duration_s,
            threads=threads,
            rate_limit=rate_limit,
        ),
        max_limits=max_limits,
        installed=installed,
    )


class ToolRegistry:
    """Catálogo imutável indexado por identificador de ferramenta."""

    def __init__(self, tools: Iterable[Tool]) -> None:
        by_id: dict[str, Tool] = {}
        for tool in tools:
            if tool.id in by_id:
                raise ToolRegistryError(f"identificador duplicado: {tool.id}")
            by_id[tool.id] = tool
        if not by_id:
            raise ToolRegistryError("o catálogo deve conter ao menos uma ferramenta")
        self._tools: Mapping[str, Tool] = MappingProxyType(by_id)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path | None = None,
        *,
        root: str | Path | None = None,
    ) -> ToolRegistry:
        """Carrega YAML validado; caminhos de ferramentas são relativos a `root`."""
        module_path = Path(__file__).resolve()
        yaml_path = Path(path) if path is not None else (
            module_path.parents[2] / "config" / "tools.yaml"
        )
        tool_root = Path(root) if root is not None else module_path.parents[4]
        tool_root = tool_root.resolve()
        try:
            with yaml_path.open("r", encoding="utf-8") as stream:
                data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ToolRegistryError(f"YAML inválido em {yaml_path}: {exc}") from exc

        if not isinstance(data, list):
            raise ToolRegistryError("a raiz de tools.yaml deve ser uma lista")
        return cls(_parse_tool(item, tool_root) for item in data)

    @classmethod
    def load(cls, path: str | Path | None = None, *, root: str | Path | None = None) -> ToolRegistry:
        """Alias explícito para carregar o catálogo padrão ou um YAML fornecido."""
        return cls.from_yaml(path, root=root)

    def all(self, layer: Layer | None = None) -> tuple[Tool, ...]:
        tools = self._tools.values()
        if layer is not None:
            tools = (tool for tool in tools if tool.layer == layer)
        return tuple(tools)

    def get(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def adapter_for(self, tool_id: str) -> StressAdapter:
        """Instancia o adapter associado à ferramenta registrada."""
        if tool_id not in self._tools:
            raise KeyError(tool_id)
        module_name, type_name = _ADAPTER_TYPES[tool_id]
        adapter_type = getattr(import_module(module_name), type_name)
        return adapter_type()

    def installed(self) -> tuple[Tool, ...]:
        return tuple(tool for tool in self._tools.values() if tool.installed)

    @property
    def tools(self) -> tuple[Tool, ...]:
        return self.all()

    def __getitem__(self, tool_id: str) -> Tool:
        return self._tools[tool_id]

    def __iter__(self) -> Iterator[Tool]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._tools)
