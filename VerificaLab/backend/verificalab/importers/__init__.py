"""Registro de importadores — formatos efetivamente suportados.

Formatos homologados: junit-xml, json, jsonl, ddoslayer-json.
MikuMikuBeam: SEM importador — estatísticas existem apenas como stream
WebSocket (client.Emit("stats", ...)); não há arquivo exportável.
"""

from __future__ import annotations

from ..metrics import count_summary
from .ddoslayer import parse_ddoslayer
from .junit_xml import ImportRejected, parse_junit
from .json_report import parse_json, parse_jsonl

__all__ = ["ImportRejected", "parse_import", "FORMATS", "FORMAT_LABELS"]

FORMATS = {
    "junit-xml": parse_junit,
    "json": parse_json,
    "jsonl": parse_jsonl,
    "ddoslayer-json": parse_ddoslayer,
}

FORMAT_LABELS = {
    "junit-xml": "JUnit XML (pytest/CI)",
    "json": "JSON (checks/results/tests/cases)",
    "jsonl": "JSONL (um objeto por linha)",
    "ddoslayer-json": "DDoSlayer logs/*.json (formato confirmado no fonte)",
}


def parse_import(fmt: str, data: bytes, source_name: str) -> dict:
    """Normaliza qualquer importador para: records_list, warnings, metrics."""
    if fmt not in FORMATS:
        raise ImportRejected(
            f"formato não suportado: {fmt} (suportados: {sorted(FORMATS)})")
    res = FORMATS[fmt](data, source_name)
    if fmt == "junit-xml":
        res["records_list"] = res.pop("cases")
        t = res["totals"]
        res["metrics"] = [
            count_summary(t["tests"], name_unit="testes",
                          population="casos lidos do relatório JUnit",
                          details={"suites": len(res["suites"])}),
            count_summary(t["failures"], name_unit="falhas",
                          population="casos com <failure> no JUnit"),
            count_summary(t["errors"], name_unit="erros",
                          population="casos com <error> no JUnit"),
            count_summary(t["skipped"], name_unit="pulados",
                          population="casos com <skipped> no JUnit"),
        ]
        res.setdefault("provenance", {
            "source_format": "junit-xml", "source_name": source_name,
            "origin": "relatório de execução de testes",
        })
    res.setdefault("metrics", [])
    res.setdefault("provenance", {
        "source_format": fmt, "source_name": source_name, "origin": "importação",
    })
    return res
