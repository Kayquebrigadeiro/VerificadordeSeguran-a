"""Importadores JSON e JSONL genéricos (formatos efetivamente suportados).

- JSON: objeto com lista em checks/results/tests/cases, ou lista direta.
- JSONL: um objeto JSON por linha; linhas malformadas viram aviso + descarte.
Campos ausentes permanecem desconhecidos; nada é inventado.
"""

from __future__ import annotations

import json

from .. import config
from ..security import sanitize_text
from .junit_xml import ImportRejected

STATUS_MAP = {
    "pass": "pass", "passed": "pass", "ok": "pass", "success": "pass", "true": "pass",
    "fail": "fail", "failed": "fail", "failure": "fail", "false": "fail",
    "error": "error", "errored": "error",
    "skip": "skip", "skipped": "skip", "ignored": "skip",
}


def _normalize_record(raw: dict, warnings: list[str], idx: int) -> dict | None:
    if not isinstance(raw, dict):
        warnings.append(f"registro {idx}: não é objeto; descartado")
        return None
    name = raw.get("name") or raw.get("test") or raw.get("case") or raw.get("title")
    if name is None:
        warnings.append(f"registro {idx}: campo de identificação ausente")
        name = f"(registro {idx})"
    status_raw = raw.get("status") or raw.get("result") or raw.get("outcome")
    if status_raw is None:
        status = "unknown"
        warnings.append(f"registro {idx}: status ausente -> unknown")
    else:
        status = STATUS_MAP.get(str(status_raw).strip().lower(), "unknown")
        if status == "unknown":
            warnings.append(f"registro {idx}: status '{status_raw}' não reconhecido -> unknown")
    message = raw.get("message") or raw.get("reason") or raw.get("description") or ""
    duration = raw.get("duration_ms")
    if duration is None:
        duration = raw.get("duration")
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
        warnings.append(f"registro {idx}: duração inválida -> desconhecida")
    return {
        "name": sanitize_text(str(name), 300),
        "classname": sanitize_text(str(raw.get("suite") or raw.get("class") or ""), 300),
        "status": status,
        "message": sanitize_text(str(message), 1500),
        "time": duration,
        "raw": {k: raw[k] for k in list(raw)[:20]},
    }


def _extract_list(data) -> tuple[list, str]:
    if isinstance(data, list):
        return data, "lista raiz"
    if isinstance(data, dict):
        for key in ("checks", "results", "tests", "cases", "records", "items"):
            if isinstance(data.get(key), list):
                return data[key], f"chave '{key}'"
    raise ImportRejected(
        "JSON não contém lista de registros em checks/results/tests/cases/records/items")


def parse_json(data: bytes, source_name: str = "report.json") -> dict:
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ImportRejected("JSON acima do limite de upload")
    try:
        obj = json.loads(data.decode("utf-8", errors="strict"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ImportRejected(f"JSON malformado: {exc}") from exc
    raw_list, origin = _extract_list(obj)
    if len(raw_list) > config.MAX_JSON_RECORDS:
        raise ImportRejected(f"acima de {config.MAX_JSON_RECORDS} registros")
    warnings: list[str] = [f"estrutura: {origin}"]
    records = []
    for i, raw in enumerate(raw_list):
        rec = _normalize_record(raw, warnings, i)
        if rec:
            records.append(rec)
    if not records:
        warnings.append("nenhum registro válido; campos ausentes permanecem desconhecidos")
    return {"format": "json", "records_list": records, "warnings": warnings,
            "records": len(records)}


def parse_jsonl(data: bytes, source_name: str = "report.jsonl") -> dict:
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ImportRejected("JSONL acima do limite de upload")
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > config.MAX_JSON_RECORDS:
        raise ImportRejected(f"acima de {config.MAX_JSON_RECORDS} linhas")
    warnings: list[str] = []
    records = []
    discarded = 0
    for i, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"linha {i}: JSON inválido — descartada")
            discarded += 1
            continue
        rec = _normalize_record(raw, warnings, i)
        if rec:
            records.append(rec)
        else:
            discarded += 1
    if discarded:
        warnings.append(f"{discarded} linha(s) descartada(s) por malformação")
    return {"format": "jsonl", "records_list": records, "warnings": warnings,
            "records": len(records), "discarded": discarded}
