"""Importador do formato DDoSlayer — confirmado no fonte upstream.

Fonte: ddoslayer/DDoSlayer.py, funções generate_attack_summary/export_log_json
(linha ~1354): JSON em logs/{attack_id}.json com attack_id, timestamp,
attack_type, target, port, duration, actual_duration, threads, stealth_mode e
results{packets_sent, packets_failed, total_attempts, success_rate, avg_rate,
peak_rate}.

Regras: procedência externa explícita; packets_sent/success_rate/avg_rate NÃO
são reinterpretados como métricas HTTP — mantêm unidade e definição do DDoSlayer.
"""

from __future__ import annotations

import json

from .. import config
from ..security import sanitize_text
from .junit_xml import ImportRejected

CONFIRMED_TOP = {"attack_id", "timestamp", "attack_type", "target", "port",
                 "duration", "actual_duration", "threads", "stealth_mode", "results"}
CONFIRMED_RESULTS = {"packets_sent", "packets_failed", "total_attempts",
                     "success_rate", "avg_rate", "peak_rate"}

CAVEATS = [
    "packets_sent não equivale a requisições HTTP concluídas com sucesso.",
    "success_rate usa a definição interna do DDoSlayer (pacotes enviados / tentativas), "
    "não uma taxa HTTP comprovada.",
    "Importar este relatório não comprova que o teste foi autorizado, completo "
    "ou corretamente medido.",
]


def parse_ddoslayer(data: bytes, source_name: str = "attack.json") -> dict:
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ImportRejected("JSON acima do limite de upload")
    try:
        obj = json.loads(data.decode("utf-8", errors="strict"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ImportRejected(f"JSON malformado: {exc}") from exc
    if not isinstance(obj, dict):
        raise ImportRejected("formato DDoSlayer esperado objeto JSON no topo")

    known = set(obj.keys()) & CONFIRMED_TOP
    if "attack_id" not in known and "results" not in known:
        raise ImportRejected(
            "não corresponde ao formato DDoSlayer confirmado "
            "(faltam attack_id e results)")

    warnings: list[str] = list(CAVEATS)
    unknown_top = sorted(set(obj.keys()) - CONFIRMED_TOP)
    if unknown_top:
        warnings.append(f"campos fora do esquema confirmado, preservados como evidência: "
                        f"{unknown_top[:10]}")

    results = obj.get("results") if isinstance(obj.get("results"), dict) else {}
    missing = sorted(CONFIRMED_RESULTS - set(results.keys()))
    if missing:
        warnings.append(f"campos ausentes no results (permanecem desconhecidos): {missing}")

    provenance = {
        "source_format": "ddoslayer-json",
        "source_name": sanitize_text(source_name, 200),
        "origin": "arquivo externo importado (procedência declarada pelo usuário)",
        "confirmed_at": "leitura de ddoslayer/DDoSlayer.py em 11/10/2026",
    }

    def num(key):
        v = results.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            warnings.append(f"results.{key} não numérico: {v!r}")
            return None

    pop = "export do DDoSlayer (medição externa, não é medição HTTP do VerificaLab)"
    metrics = []
    for key, unit, defn in [
        ("packets_sent", "pacotes", "contagem reportada pelo DDoSlayer"),
        ("packets_failed", "pacotes", "contagem reportada pelo DDoSlayer"),
        ("total_attempts", "pacotes", "tentativas reportadas"),
        ("success_rate", "%", "definição interna do DDoSlayer"),
        ("avg_rate", "pacotes/s", "média reportada pelo DDoSlayer"),
        ("peak_rate", "pacotes/s", "pico reportado pelo DDoSlayer"),
    ]:
        value = num(key)
        metrics.append({
            "name": f"ddoslayer_{key}",
            "value": value,
            "unit": unit,
            "origin": f"ddoslayer:results.{key} (externo)",
            "samples": int(results.get("total_attempts") or 0) if value is not None else 0,
            "population": pop,
            "discarded": 0,
            "details": {"definition": defn, "caveats": CAVEATS,
                        "provenance": provenance},
        })

    record = {
        "name": sanitize_text(str(obj.get("attack_id") or "attack (sem id)"), 300),
        "classname": sanitize_text(str(obj.get("attack_type") or ""), 300),
        "status": "unknown",
        "message": (
            f"Resumo DDoSlayer importado: alvo {obj.get('target')}, "
            f"duração {obj.get('actual_duration')}s. Sem status de teste "
            f"VerificaLab — procedência externa."
        ),
        "time": None,
        "raw": {k: obj[k] for k in list(obj)[:20]},
    }
    return {
        "format": "ddoslayer-json",
        "records_list": [record],
        "metrics": metrics,
        "warnings": warnings,
        "records": 1,
        "provenance": provenance,
    }
