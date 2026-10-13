"""Importador JUnit XML — protegido contra XXE e excesso de registros.

Barreiras: limite de bytes, rejeição de DOCTYPE/ENTITY antes do parse,
limite de profundidade, limite de casos. Mensagens são sanitizadas e
truncadas; nenhum texto de relatório é executado.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .. import config
from ..security import sanitize_text


class ImportRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _reject_dtd(data: bytes) -> None:
    head = data[:8192].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise ImportRejected("XML com DOCTYPE/ENTITY rejeitado (proteção XXE)")


def _depth(elem: ET.Element, max_depth: int, level: int = 1) -> None:
    if level > max_depth:
        raise ImportRejected(f"XML profundo demais (limite {max_depth})")
    for child in elem:
        _depth(child, max_depth, level + 1)


def _tag(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1]


def _case_status(tc: ET.Element) -> tuple[str, str]:
    for child in tc:
        t = _tag(child)
        if t == "failure":
            return "fail", child.get("message") or "failure"
        if t == "error":
            return "error", child.get("message") or "error"
        if t == "skipped":
            return "skip", child.get("message") or "skipped"
    return "pass", ""


def parse_junit(data: bytes, source_name: str = "junit.xml") -> dict:
    if len(data) > config.MAX_XML_BYTES:
        raise ImportRejected(f"XML acima do limite ({config.MAX_XML_BYTES} bytes)")
    if not data.strip():
        raise ImportRejected("XML vazio")
    _reject_dtd(data)
    try:
        root = ET.fromstring(data.decode("utf-8", errors="replace"))
    except ET.ParseError as exc:
        raise ImportRejected(f"XML malformado: {exc}") from exc
    _depth(root, config.MAX_XML_DEPTH)

    warnings: list[str] = []
    cases: list[dict] = []
    suites: list[dict] = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}

    def handle_suite(suite: ET.Element) -> None:
        st = {
            "name": suite.get("name") or "(sem nome)",
            "tests": _int(suite.get("tests")),
            "failures": _int(suite.get("failures")),
            "errors": _int(suite.get("errors")),
            "skipped": _int(suite.get("skipped")),
            "time": _float(suite.get("time")),
        }
        suites.append(st)
        totals["tests"] += st["tests"]
        totals["failures"] += st["failures"]
        totals["errors"] += st["errors"]
        totals["skipped"] += st["skipped"]
        totals["time"] += st["time"]
        for child in suite:
            if _tag(child) == "testcase":
                if len(cases) >= config.MAX_XML_RECORDS:
                    warnings.append(
                        f"Limite de {config.MAX_XML_RECORDS} casos atingido; resto descartado.")
                    return
                status, msg = _case_status(child)
                detail = ""
                for gc in child:
                    if _tag(gc) in ("failure", "error") and (gc.text or ""):
                        detail = sanitize_text(gc.text, max_len=1500)
                        break
                cases.append({
                    "name": sanitize_text(child.get("name") or "(sem nome)", 300),
                    "classname": sanitize_text(child.get("classname") or "", 300),
                    "time": _float(child.get("time")),
                    "status": status,
                    "message": sanitize_text(msg, 800),
                    "detail": detail,
                })
            elif _tag(child) in ("testsuite", "testsuites"):
                handle_suite(child)

    if _tag(root) in ("testsuite", "testsuites"):
        handle_suite(root)
    else:
        raise ImportRejected(f"raiz <{_tag(root)}> não é testsuite/testsuites")

    if not cases:
        warnings.append("Nenhum <testcase> encontrado; campos ausentes permanecem desconhecidos.")
    declared = totals["tests"]
    if declared and declared != len(cases):
        warnings.append(
            f"Total declarado ({declared}) difere dos casos lidos ({len(cases)}); "
            "prevalece o que foi lido.")
        totals["tests"] = len(cases)
    return {
        "format": "junit-xml",
        "cases": cases,
        "suites": suites,
        "totals": totals,
        "warnings": warnings,
        "records": len(cases),
    }


def _int(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
