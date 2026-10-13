"""Correlação de logs com execuções — hipóteses com evidência, nunca causas.

Regras:
- Timestamps: ISO8601, syslog, Apache/CLF e epoch. Fuso registrado; relógios
  não comparáveis viram incerteza explícita.
- Coincidência temporal = hipótese com evidência (hyp=1), não causalidade.
- Textos de log são dados: sanitizados, escapados e NUNCA executados.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ..db import Database, utcnow
from ..ids import new_id, sha256_bytes, safe_filename
from ..metrics import count_summary
from ..security import sanitize_text, redact

TS_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ISO8601 com fuso
    (re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}))"),
     "iso8601"),
    # epoch no início (10 dígitos) ou com milissegundos
    (re.compile(r"(?<![\d.])(1[6-9]\d{9}|1[6-9]\d{12})(?![\d.])"), "epoch"),
    # Apache/CLF: 11/Oct/2026:12:34:56 +0000
    (re.compile(r"(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}\s[+-]\d{4})"), "clf"),
    # syslog: Oct 11 12:34:56 (sem fuso/ano)
    (re.compile(r"\b([A-Z][a-z]{2}\s{1,2}\d{1,2}\s\d{2}:\d{2}:\d{2})\b"), "syslog"),
    # data-hora local sem fuso
    (re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"), "naive"),
]

LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b")
REQID_RE = re.compile(r"\b((?:req|request)[-_][A-Za-z0-9]{4,}|trace[-_]?id[\"'=:\s]+[A-Za-z0-9]{6,})",
                      re.IGNORECASE)
HTTP_STATUS_RE = re.compile(r"\b([45]\d{2})\b")

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _parse_ts(text: str) -> tuple[float | None, str | None, str]:
    """-> (epoch_utc, tz_string, incerteza)"""
    for pat, kind in TS_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        raw = m.group(1)
        try:
            if kind == "epoch":
                val = float(raw)
                if val > 1e12:
                    val /= 1000.0
                return val, "epoch(s)", ""
            if kind == "iso8601":
                norm = raw.replace("Z", "+00:00")
                if "+" not in norm[10:] and norm.count(":") == 1:
                    norm = norm + ":00"  # +0300 -> +03:00
                dt = datetime.fromisoformat(norm)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc).timestamp(), None, \
                        "fuso ausente; assumido UTC"
                return dt.timestamp(), str(dt.tzinfo), ""
            if kind == "clf":
                dt = datetime.strptime(raw[:20] + raw[21:], "%d/%b/%Y:%H:%M:%S %z")
                return dt.timestamp(), str(dt.utcoffset()), ""
            if kind == "syslog":
                # sem ano/fuso: ano atual, fuso local — incerteza
                now = datetime.now().astimezone()
                dt = datetime.strptime(raw, "%b %d %H:%M:%S").replace(
                    year=now.year, tzinfo=now.tzinfo)
                return dt.timestamp(), str(now.tzinfo), \
                    "syslog sem ano/fuso; ano atual e fuso local assumidos"
            if kind == "naive":
                now = datetime.now().astimezone()
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=now.tzinfo)
                return dt.timestamp(), str(now.tzinfo), \
                    "data-hora sem fuso; fuso local assumido"
        except (ValueError, OverflowError):
            continue
    return None, None, "sem timestamp reconhecível"


def classify_level(message: str) -> str | None:
    m = LEVEL_RE.search(message[:400])
    return m.group(1).upper() if m else None


def parse_log_file(filename: str, data: bytes) -> dict:
    """Sanitiza e parseia upload de log (limites de config)."""
    from .. import config as cfg

    if len(data) > cfg.MAX_UPLOAD_BYTES:
        raise ValueError(f"arquivo acima de {cfg.MAX_UPLOAD_BYTES} bytes")
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    entries: list[dict] = []
    discarded = 0
    unparsed_ts = 0
    tzs: set[str] = set()
    uncertainties: set[str] = set()
    max_lines = min(len(lines), cfg.MAX_LOG_LINES)
    if len(lines) > cfg.MAX_LOG_LINES:
        discarded += len(lines) - cfg.MAX_LOG_LINES
    for i, line in enumerate(lines[:max_lines], start=1):
        clean = sanitize_text(line)
        if not clean.strip():
            discarded += 1
            continue
        ts_epoch, tz, uncertainty = _parse_ts(clean)
        if ts_epoch is None:
            unparsed_ts += 1
        if tz:
            tzs.add(tz)
        if uncertainty:
            uncertainties.add(uncertainty)
        msg = redact(clean)
        entries.append({
            "line_no": i,
            "ts_raw": clean[:120],
            "ts_epoch": ts_epoch,
            "tz": tz,
            "level": classify_level(msg),
            "message": msg,
        })
    return {
        "entries": entries,
        "filename": safe_filename(filename, "upload.log"),
        "sha256": sha256_bytes(data),
        "discarded": discarded,
        "unparsed_ts": unparsed_ts,
        "timezones": sorted(tzs),
        "uncertainties": sorted(uncertainties),
        "total_lines": len(lines),
    }


def store_logs(db: Database, environment_id: str, parsed: dict) -> int:
    """Persiste entradas sanitizadas do log de um ambiente."""
    # substitui logs anteriores do mesmo arquivo
    db.execute(
        "DELETE FROM log_entries WHERE environment_id = ? AND filename = ?",
        (environment_id, parsed["filename"]))
    n = 0
    for e in parsed["entries"]:
        db.insert("log_entries", {
            "environment_id": environment_id,
            "filename": parsed["filename"],
            "sha256": parsed["sha256"],
            "line_no": e["line_no"],
            "ts_raw": e["ts_raw"], "ts_epoch": e["ts_epoch"], "tz": e["tz"],
            "level": e["level"], "source": parsed["filename"],
            "message": e["message"],
        })
        n += 1
    db.audit("logs.import", "environment", environment_id, {
        "filename": parsed["filename"], "entries": n,
        "discarded": parsed["discarded"], "sha256": parsed["sha256"],
    })
    return n


def _iso_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def correlate_run(db: Database, run_row) -> dict:
    """Correlaciona logs do ambiente com a janela da execução.

    Retorna achados como HIPÓTESES com evidência; nunca causa comprovada.
    """
    env_id = run_row["environment_id"]
    start = _iso_epoch(run_row["started_at"])
    end = _iso_epoch(run_row["finished_at"]) or _iso_epoch(run_row["queued_at"])
    if start is None:
        return {"available": False, "reason": "janela da execução indeterminada"}
    win_start, win_end = start - 60, (end or start) + 60

    rows = db.query(
        "SELECT line_no, ts_epoch, tz, level, message FROM log_entries "
        "WHERE environment_id = ? AND ts_epoch IS NOT NULL "
        "AND ts_epoch BETWEEN ? AND ? ORDER BY ts_epoch LIMIT 5000",
        (env_id, win_start, win_end))
    total_env = db.one("SELECT COUNT(*) AS c FROM log_entries WHERE environment_id = ?",
                       (env_id,))["c"]
    unparsed = db.one(
        "SELECT COUNT(*) AS c FROM log_entries WHERE environment_id = ? "
        "AND ts_epoch IS NULL", (env_id,))["c"]

    errors = [r for r in rows if (r["level"] or "") in
              ("ERROR", "CRITICAL", "FATAL", "WARN", "WARNING")]
    http5 = [r for r in rows if any(m.group(1).startswith("5")
             for m in HTTP_STATUS_RE.finditer(r["message"]))]
    tzs = sorted({r["tz"] for r in rows if r["tz"]})
    local_tz = datetime.now().astimezone().tzname()
    tz_uncertain = (len(tzs) > 1) or any(
        t and local_tz and local_tz not in t and "epoch" not in t for t in tzs)

    corr = {
        "available": True,
        "window_utc": {
            "start": datetime.fromtimestamp(win_start, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(win_end, timezone.utc).isoformat(),
        },
        "entries_in_window": len(rows),
        "entries_total_for_environment": total_env,
        "entries_without_timestamp": unparsed,
        "timezones_observed": tzs,
        "local_tz": local_tz,
        "clock_uncertainty": (
            "Relógios possivelmente não comparáveis: fuso(s) observado(s) difere(m) "
            "do fuso local ou ausentes." if tz_uncertain or unparsed else
            "Sem indício de divergência de relógio nas amostras verificadas."),
    }

    findings = []
    if errors:
        sample = [{"line_no": r["line_no"],
                   "ts": datetime.fromtimestamp(r["ts_epoch"], timezone.utc).isoformat(),
                   "level": r["level"], "message": r["message"][:300]}
                  for r in errors[:10]]
        findings.append({
            "severity": "hypothesis", "hypothesis": 1,
            "title": f"{len(errors)} linha(s) de erro/aviso na janela da execução",
            "description": (
                "Coincidência temporal entre linhas de erro do log e a janela desta "
                "execução. Isso é uma HIPÓTESE com evidência — a causalidade não "
                "foi comprovada. Verifique horário, origem e identificadores antes "
                "de concluir."
            ),
            "evidence": {"sample": sample, "count": len(errors),
                         "window": corr["window_utc"],
                         "clock_uncertainty": corr["clock_uncertainty"]},
        })
    if http5:
        sample = [{"line_no": r["line_no"], "message": r["message"][:300]}
                  for r in http5[:10]]
        findings.append({
            "severity": "hypothesis", "hypothesis": 1,
            "title": f"{len(http5)} menção(ões) a status 5xx na janela",
            "description": (
                "Mensagens com status 5xx coincidem com a janela da execução. "
                "Hipótese com evidência; não prova que a execução causou o erro."
            ),
            "evidence": {"sample": sample, "count": len(http5),
                         "window": corr["window_utc"]},
        })
    if unparsed:
        findings.append({
            "severity": "info", "hypothesis": 0,
            "title": f"{unparsed} linha(s) de log sem timestamp reconhecível",
            "description": "Linhas sem data/hora não entram na correlação temporal; "
                           "permanecem disponíveis como texto.",
            "evidence": {"unparsed": unparsed, "total": total_env},
        })
    corr["findings"] = findings
    return corr

