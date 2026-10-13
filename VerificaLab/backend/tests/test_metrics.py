"""Métricas: percentis nearest-rank, populações e descartes."""

from verificalab.metrics import (count_summary, latency_summary, percentile,
                                 rate_summary, unknown_metric)


def test_percentile_nearest_rank():
    samples = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(samples, 50) == 50
    assert percentile(samples, 90) == 90
    assert percentile(samples, 100) == 100
    assert percentile(samples, 0) == 10
    assert percentile([7], 95) == 7


def test_percentile_empty_is_none():
    assert percentile([], 50) is None


def test_latency_summary_complete_metadata():
    out = latency_summary([5, 15, 25, 35], population="teste", discarded=2)
    assert out["unit"] == "ms"
    assert out["samples"] == 4
    assert out["discarded"] == 2
    assert out["population"] == "teste"
    assert out["details"]["p50_ms"] == 15
    assert out["details"]["p95_ms"] == 35


def test_latency_summary_without_data_is_unknown():
    out = latency_summary([], population="teste")
    assert out["value"] is None
    assert out["samples"] == 0


def test_rate_summary_definition():
    out = rate_summary(10, 5.0, population="concluídas")
    assert out["value"] == 2.0
    assert out["details"]["completed"] == 10
    assert out["details"]["duration_s"] == 5.0


def test_rate_summary_without_duration():
    out = rate_summary(10, 0.0, population="x")
    assert out["value"] is None


def test_count_and_unknown():
    c = count_summary(3, name_unit="falhas", population="p", discarded=1)
    assert c["value"] == 3.0 and c["discarded"] == 1
    u = unknown_metric("sem definição comprovada")
    assert u["value"] is None and u["population"] == "indisponível"
