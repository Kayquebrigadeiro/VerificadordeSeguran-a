"""Contratos tipados da API — validação explícita de entrada.

Regras inegociáveis aplicadas aqui (antes de tocar no banco):
- Endpoint: IP literal de loopback, porta explícita, sem credenciais.
- Carga: rps <= 5, concorrência <= 2, duração <= 30 s, tentativas <= 150,
  métodos GET/HEAD. Valores acima são REJEITADOS (422), não silenciosamente.
- Suite: comando em lista, prefixo na lista de comandos pré-configurados,
  cwd dentro das raízes permitidas, sem --junitxml próprio (o runner gera).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from . import config
from .targetpolicy import TargetPolicyError, parse_endpoint

import sys

# ---------------------------------------------------------------------------
# Projetos e ambientes
# ---------------------------------------------------------------------------


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome não pode ser vazio")
        return v


class EnvironmentIn(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=80)
    endpoint: str  # ex.: http://127.0.0.1:8477
    kind: Literal["lab", "local"] = "lab"
    secret_header_name: Optional[str] = Field(default=None, max_length=64)
    secret_header_value: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        try:
            parse_endpoint(v)
        except TargetPolicyError as exc:
            raise ValueError(exc.reason) from exc
        return v.strip()

    @field_validator("secret_header_name")
    @classmethod
    def header_name_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if any(c in v for c in "\r\n: "):
            raise ValueError("nome de cabeçalho inválido")
        return v


# ---------------------------------------------------------------------------
# Checks HTTP (contrato)
# ---------------------------------------------------------------------------

CheckType = Literal["status", "json_fields", "content_type", "max_time",
                    "body_contains", "header"]


class FieldExpectation(BaseModel):
    path: str = Field(min_length=1, max_length=200, description="caminho tipo a.b.c")
    type: Optional[Literal["string", "number", "boolean", "object", "array"]] = None
    equals: Optional[Any] = None


class HttpCheck(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: CheckType
    path: str = Field(default="/", max_length=1000)
    method: Literal["GET", "HEAD", "POST"] = "GET"
    expected_status: int = Field(default=200, ge=100, le=599)
    fields: list[FieldExpectation] = Field(default_factory=list, max_length=50)
    expected_content_type: Optional[str] = Field(default=None, max_length=200)
    max_seconds: Optional[float] = Field(default=None, ge=0.05, le=60)
    substring: Optional[str] = Field(default=None, max_length=1000)
    header: Optional[str] = Field(default=None, max_length=200)
    header_value: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def fields_only_for_json(self) -> "HttpCheck":
        if self.type == "json_fields" and not self.fields:
            raise ValueError("json_fields exige ao menos uma expectativa de campo")
        if self.type == "max_time" and self.max_seconds is None:
            raise ValueError("max_time exige max_seconds")
        if self.type == "content_type" and not self.expected_content_type:
            raise ValueError("content_type exige expected_content_type")
        if self.type == "body_contains" and not self.substring:
            raise ValueError("body_contains exige substring")
        if self.type == "header" and not self.header:
            raise ValueError("header exige header")
        return self


class HttpProfileConfig(BaseModel):
    checks: list[HttpCheck] = Field(min_length=1, max_length=50)
    include_config_checks: bool = True
    timeout_s: float = Field(default=config.HTTP_DEFAULT_TIMEOUT_S, ge=0.5, le=30)

    @field_validator("checks")
    @classmethod
    def unique_names(cls, v: list[HttpCheck]) -> list[HttpCheck]:
        names = [c.name for c in v]
        if len(names) != len(set(names)):
            raise ValueError("nomes de check duplicados")
        return v


# ---------------------------------------------------------------------------
# Carga leve (piloto)
# ---------------------------------------------------------------------------


class LoadProfileConfig(BaseModel):
    path: str = Field(default="/ok", max_length=1000)
    method: Literal["GET", "HEAD"] = "GET"   # GET/HEAD somente no piloto
    rps: float = Field(default=config.LOAD_DEFAULT_RPS, gt=0)
    duration_s: float = Field(default=5.0, gt=0)
    concurrency: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=150, ge=1)
    timeout_s: float = Field(default=config.LOAD_REQUEST_TIMEOUT_S, ge=0.5, le=30)
    expect_status: int = Field(default=200, ge=100, le=599)

    @field_validator("rps")
    @classmethod
    def rps_cap(cls, v: float) -> float:
        if v > config.LOAD_MAX_RPS:
            raise ValueError(f"rps acima do teto do piloto ({config.LOAD_MAX_RPS})")
        return v

    @field_validator("duration_s")
    @classmethod
    def duration_cap(cls, v: float) -> float:
        if v > config.LOAD_MAX_DURATION_S:
            raise ValueError(f"duração acima do teto ({config.LOAD_MAX_DURATION_S}s)")
        return v

    @field_validator("concurrency")
    @classmethod
    def concurrency_cap(cls, v: int) -> int:
        if v > config.LOAD_MAX_CONCURRENCY:
            raise ValueError(f"concorrência acima do teto ({config.LOAD_MAX_CONCURRENCY})")
        return v

    @field_validator("max_attempts")
    @classmethod
    def attempts_cap(cls, v: int) -> int:
        if v > config.LOAD_MAX_ATTEMPTS:
            raise ValueError(f"tentativas acima do teto ({config.LOAD_MAX_ATTEMPTS})")
        return v



# ---------------------------------------------------------------------------
# Suite de testes (runner real pré-configurado)
# ---------------------------------------------------------------------------


def _allowed_suite_roots() -> list[Path]:
    return [config.SUITE_PROJECTS_DIR.resolve(), config.BACKEND_DIR.resolve()]


class SuiteProfileConfig(BaseModel):
    command: list[str] = Field(min_length=2, max_length=32)
    cwd: str = Field(min_length=1, max_length=4000)
    timeout_s: float = Field(default=120.0, gt=0)

    @field_validator("timeout_s")
    @classmethod
    def timeout_cap(cls, v: float) -> float:
        if v > config.SUITE_MAX_TIMEOUT_S:
            raise ValueError(f"timeout acima do teto ({config.SUITE_MAX_TIMEOUT_S}s)")
        return v

    @field_validator("command")
    @classmethod
    def command_allowlist(cls, v: list[str]) -> list[str]:
        v = [str(x) for x in v]
        allowed = False
        for a in config.SUITE_ALLOWED_COMMANDS:
            if len(v) >= len(a) and tuple(v[: len(a)]) == a:
                allowed = True
                break
        if not allowed and not (len(v) >= 2 and v[0] == sys.executable and v[1] == "-m" and v[2] == "pytest"):
            raise ValueError(
                "comando fora da lista pré-configurada (pytest apenas); "
                f"permitidos: {[list(a) for a in config.SUITE_ALLOWED_COMMANDS]}"
            )
        for arg in v:
            if "--junitxml" in arg:
                raise ValueError("--junitxml é gerado pelo runner; não informe")
            if "\x00" in arg:
                raise ValueError("argumento inválido")
        return v

    @field_validator("cwd")
    @classmethod
    def cwd_allowed(cls, v: str) -> str:
        try:
            resolved = Path(v).expanduser().resolve()
        except OSError as exc:
            raise ValueError("cwd inválido") from exc
        roots = _allowed_suite_roots()
        if not any(resolved == r or resolved.is_relative_to(r) for r in roots):
            raise ValueError(
                "cwd fora das raízes permitidas (data/suite_projects ou backend/)"
            )
        return str(resolved)


# ---------------------------------------------------------------------------
# Perfis e execuções
# ---------------------------------------------------------------------------


class ProfileIn(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["http", "load", "suite"]
    config: dict[str, Any]

    @model_validator(mode="after")
    def validate_config_by_kind(self) -> "ProfileIn":
        if self.kind == "http":
            self.config = HttpProfileConfig.model_validate(self.config).model_dump()
        elif self.kind == "load":
            self.config = LoadProfileConfig.model_validate(self.config).model_dump()
        else:
            self.config = SuiteProfileConfig.model_validate(self.config).model_dump()
        return self


class RunIn(BaseModel):
    profile_id: str
    environment_id: str
