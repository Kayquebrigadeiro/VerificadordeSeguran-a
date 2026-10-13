"""Importadores: JUnit (XXE/limites), JSON/JSONL e DDoSlayer (formato confirmado)."""

import json

import pytest

from verificalab.importers import ImportRejected, parse_import

JUnit_OK = b"""<?xml version="1.0"?>
<testsuite name="suite" tests="3" failures="1" errors="0" skipped="1" time="1.5">
  <testcase classname="test_a" name="ok_case" time="0.1"/>
  <testcase classname="test_a" name="bad_case" time="0.2">
    <failure message="esperava 201, observei 200">trace aqui</failure>
  </testcase>
  <testcase classname="test_a" name="skip_case" time="0">
    <skipped message="pendente"/>
  </testcase>
</testsuite>"""

JUnit_XXE = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<testsuite name="s" tests="1">&xxe;</testsuite>"""

JUnit_MALFORMED = b"<?xml version='1.0'?><testsuite><unclosed"


def test_junit_ok():
    res = parse_import("junit-xml", JUnit_OK, "junit.xml")
    assert res["records"] == 3
    statuses = {r["name"]: r["status"] for r in res["records_list"]}
    assert statuses == {"ok_case": "pass", "bad_case": "fail", "skip_case": "skip"}
    assert any("esperava 201" in r["message"] for r in res["records_list"])


def test_junit_xxe_rejected():
    with pytest.raises(ImportRejected) as exc:
        parse_import("junit-xml", JUnit_XXE, "evil.xml")
    assert "XXE" in exc.value.reason


def test_junit_malformed_rejected():
    with pytest.raises(ImportRejected):
        parse_import("junit-xml", JUnit_MALFORMED, "bad.xml")


def test_junit_declared_count_mismatch_warns():
    data = b'<testsuite name="s" tests="99"><testcase name="a"/></testsuite>'
    res = parse_import("junit-xml", data, "j.xml")
    assert any("difere" in w for w in res["warnings"])


def test_json_generic_list():
    data = json.dumps([
        {"name": "c1", "status": "passed", "message": "ok"},
        {"name": "c2", "status": "banana"},
        {"status": "fail"},
    ]).encode()
    res = parse_import("json", data, "r.json")
    assert res["records"] == 3
    statuses = [r["status"] for r in res["records_list"]]
    assert statuses == ["pass", "unknown", "fail"]
    assert any("não reconhecido" in w for w in res["warnings"])


def test_json_without_list_rejected():
    with pytest.raises(ImportRejected):
        parse_import("json", b'{"foo": 1}', "r.json")


def test_jsonl_malformed_lines_become_warnings():
    data = b'{"name": "a", "status": "ok"}\nlixao nao json\n{"name": "b", "status": "fail"}\n'
    res = parse_import("jsonl", data, "r.jsonl")
    assert res["records"] == 2
    assert any("JSON inválido" in w for w in res["warnings"])


DDOSLAYER_OK = json.dumps({
    "attack_id": "attack_20261011_120000",
    "timestamp": "2026-10-11 12:00:00",
    "attack_type": "http",
    "target": "127.0.0.1", "port": 80, "duration": 10, "actual_duration": 9.9,
    "threads": 2, "stealth_mode": False,
    "results": {"packets_sent": 100, "packets_failed": 5, "total_attempts": 105,
                "success_rate": 95.24, "avg_rate": 10, "peak_rate": 12},
}).encode()


def test_ddoslayer_format_confirmed_imported():
    res = parse_import("ddoslayer-json", DDOSLAYER_OK, "attack.json")
    assert res["records"] == 1
    names = {m["name"] for m in res["metrics"]}
    assert "ddoslayer_packets_sent" in names
    pkt = next(m for m in res["metrics"] if m["name"] == "ddoslayer_packets_sent")
    assert pkt["unit"] == "pacotes"
    assert "não equivale" in " ".join(pkt["details"]["caveats"])
    assert any("não comprova" in w for w in res["warnings"])


def test_ddoslayer_wrong_shape_rejected():
    with pytest.raises(ImportRejected):
        parse_import("ddoslayer-json", b'{"qualquer": 1}', "x.json")


def test_unknown_format_rejected():
    with pytest.raises(ImportRejected):
        parse_import("xml-generic", b"<x/>", "x.xml")
