"""Métricas determinísticas — taxa e percentis a partir de observações.

Regras:
- Percentis usam nearest-rank sobre a população informada.
- Toda métrica registra: unidade, origem, quantidade de amostras,
  população utilizada e descartes. Sem dados => None (indisponível).
- Métricas de processo do cliente NUNCA são apresentadas como métricas
  do servidor testado sem essa qualificação explícita.
"""

from __future__ import annotations

import math
from typing import Sequence


def percentile(samples: Sequence[float], p: float) -> float | None:
    """Percentil nearest-rank (p em 0..100). None se não houver amostras."""
    if not samples:
        return None
    ordered = sorted(samples)
    if p <= 0:
        return float(ordered[0])
    if p >= 100:
        return float(ordered[-1])
    rank = math.ceil(p / 100.0 * len(ordered))
    rank = max(1, min(rank, len(ordered)))
    return float(ordered[rank - 1])


def latency_summary(samples_ms: Sequence[float], *, population: str,
                    discarded: int = 0) -> dict:
    """Resumo de latências em milissegundos com metadados completos."""
    valid = [float(s) for s in samples_ms if s is not None and not math.isnan(s)]
    if not valid:
        return {
            "value": None, "unit": "ms", "samples": 0,
            "population": population, "discarded": discarded,
            "details": {"note": "sem amostras concluídas"},
        }
    return {
        "value": percentile(valid, 50),
        "unit": "ms",
        "samples": len(valid),
        "population": population,
        "discarded": discarded,
        "details": {
            "min_ms": round(min(valid), 3),
            "max_ms": round(max(valid), 3),
            "mean_ms": round(sum(valid) / len(valid), 3),
            "p50_ms": round(percentile(valid, 50), 3),
            "p90_ms": round(percentile(valid, 90), 3),
            "p95_ms": round(percentile(valid, 95), 3),
            "p99_ms": round(percentile(valid, 99), 3),
            "method": "nearest-rank sobre amostras concluídas",
        },
    }


def rate_summary(completed: int, duration_s: float, *, population: str,
                 unit: str = "req/s") -> dict:
    """Taxa concluída por duração observada; sem duração => indeterminado."""
    if duration_s <= 0 or completed < 0:
        return {"value": None, "unit": unit, "samples": completed,
                "population": population, "discarded": 0,
                "details": {"note": "duração observada indisponível"}}
    return {
        "value": round(completed / duration_s, 3),
        "unit": unit,
        "samples": completed,
        "population": population,
        "discarded": 0,
        "details": {
            "completed": completed,
            "duration_s": round(duration_s, 3),
            "definition": "requisições concluídas com sucesso / duração observada",
        },
    }


def count_summary(value: int, *, name_unit: str, population: str,
                  discarded: int = 0, details: dict | None = None) -> dict:
    return {
        "value": float(value), "unit": name_unit, "samples": int(value),
        "population": population, "discarded": discarded,
        "details": details or {},
    }


def unknown_metric(reason: str) -> dict:
    """Indisponível — usado quando não há dados ou definição comprovada."""
    return {
        "value": None, "unit": None, "samples": 0,
        "population": "indisponível", "discarded": 0,
        "details": {"note": reason},
    }
