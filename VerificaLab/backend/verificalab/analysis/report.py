"""Exportação de relatório (JSON/HTML) e comparação entre execuções.

- Todo conteúdo passa por redact_obj + html.escape antes de sair.
- Sem tokens/segredos em relatório; dados ausentes como "desconhecido".
"""

from __future__ import annotations

import html
import json

from .. import config
from ..db import Database, utcnow
from ..security import redact_obj

LIMITATIONS = [
    "Verificações determinísticas e evidências; nenhuma IA ou treinamento.",
    "Ausência de cabeçalho ou falha de contrato não comprova causa raiz.",
    "Correlação temporal com logs gera hipóteses, não causalidade comprovada.",
    "Métricas de latência são observações do cliente VerificaLab, não do servidor.",
    "Importações externas não comprovam autorização ou completude do teste.",
]


def build_report(db: Database, run_id: str) -> dict | None:
    run = db.one("SELECT * FROM runs WHERE id = ?", (run_id,))
    if not run:
        return None
    project = db.one("SELECT * FROM projects WHERE id = ?", (run["project_id"],))
    env = db.one("SELECT * FROM environments WHERE id = ?", (run["environment_id"],))
    profile = db.one("SELECT * FROM test_profiles WHERE id = ?", (run["profile_id"],))

    checks = db.query("SELECT * FROM check_results WHERE run_id = ? ORDER BY seq",
                      (run_id,))
    ms = db.query("SELECT * FROM metrics WHERE run_id = ?", (run_id,))
    fs = db.query("SELECT * FROM findings WHERE run_id = ? ORDER BY created_at",
                  (run_id,))
    arts = db.query("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
    events = db.query(
        "SELECT ts, level, message FROM run_events WHERE run_id = ? "
        "ORDER BY id LIMIT 500", (run_id,))
    imps = db.query(
        "SELECT id, format, source_name, sha256, records, created_at "
        "FROM imports WHERE run_id = ? ORDER BY created_at", (run_id,))

    report = {
        "report_version": "1",
        "generated_at": utcnow(),
        "platform": {"name": "VerificaLab", "version": "0.1.0",
                     "retention": config.RETENTION_NOTE},
        "run": {**dict(run),
                "config_json": json.loads(run["config_json"])},
        "project": dict(project) if project else None,
        "environment": {
            "id": env["id"], "name": env["name"], "kind": env["kind"],
            "endpoint": f"{env['scheme']}://{env['host']}:{env['port']}",
            "secret_header_name": env["secret_header_name"],
            "secret_header_value": "***",  # nunca exportado
        } if env else None,
        "profile": {"id": profile["id"], "name": profile["name"],
                    "kind": profile["kind"],
                    "config": json.loads(profile["config_json"])} if profile else None,
        "checks": [dict(c) | {"evidence_json": json.loads(c["evidence_json"])}
                   for c in checks],
        "metrics": [dict(m) | {"details": json.loads(m["details_json"])}
                    for m in ms],
        "findings": [dict(f) | {"evidence": json.loads(f["evidence_json"])}
                     for f in fs],
        "artifacts": [{"id": a["id"], "kind": a["kind"], "filename": a["filename"],
                       "sha256": a["sha256"], "size": a["size"],
                       "created_at": a["created_at"]} for a in arts],
        "imports": [dict(i) for i in imps],
        "events": [dict(e) for e in events],
        "limitations": LIMITATIONS,
    }
    return redact_obj(report)


def render_html(report: dict) -> str:
    """HTML autocontido e 100% escapado (sem scripts, CSP restritiva)."""
    e = html.escape

    def j(v) -> str:
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        return e(str(v))

    run = report["run"]
    rows_checks = "".join(
        f"<tr><td>{e(c['name'])}</td><td class='s-{e(c['status'])}'>"
        f"{e(c['status'])}</td><td>{e(c.get('expected') or '')}</td>"
        f"<td>{e(c.get('observed') or '')}</td><td>{e(c.get('message') or '')}</td></tr>"
        for c in report["checks"]) or "<tr><td colspan='5'>sem verificações</td></tr>"
    rows_metrics = "".join(
        f"<tr><td>{e(m['name'])}</td><td>{j(m.get('value'))}</td>"
        f"<td>{e(m.get('unit') or '-')}</td><td>{e(str(m.get('samples')))}</td>"
        f"<td>{e(m.get('population') or '')}</td><td>{e(str(m.get('discarded')))}</td>"
        f"<td>{e(m.get('origin') or '')}</td></tr>"
        for m in report["metrics"]) or "<tr><td colspan='7'>sem métricas</td></tr>"
    rows_findings = "".join(
        f"<tr><td>{e(f['severity'])}"
        f"{' (hipótese)' if f.get('hypothesis') else ''}</td>"
        f"<td>{e(f['title'])}</td><td>{e(f['description'])}</td></tr>"
        for f in report["findings"]) or "<tr><td colspan='3'>sem achados</td></tr>"
    rows_arts = "".join(
        f"<tr><td>{e(a['kind'])}</td><td>{e(a['filename'])}</td>"
        f"<td><code>{e(a['sha256'])}</code></td><td>{a['size']}</td></tr>"
        for a in report["artifacts"]) or "<tr><td colspan='4'>sem artefatos</td></tr>"
    lims = "".join(f"<li>{e(x)}</li>" for x in report["limitations"])
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; style-src 'unsafe-inline'">
<title>VerificaLab — relatório {e(str(run['id']))}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:70rem;color:#14213d}}
h1,h2{{margin-top:1.4rem}} table{{border-collapse:collapse;width:100%;font-size:.85rem}}
td,th{{border:1px solid #ccd;padding:.35rem .5rem;text-align:left;vertical-align:top}}
th{{background:#eef1f7}} .s-pass{{color:#1a7f37;font-weight:600}}
.s-fail{{color:#b42318;font-weight:600}} .s-error{{color:#b54708;font-weight:600}}
.s-unknown,.s-skip{{color:#57606a}} code{{background:#f2f4f7;padding:.1rem .3rem}}
.meta td:first-child{{background:#f7f8fa;width:14rem}}
.warn{{background:#fff8c5;padding:.6rem;border:1px solid #e5c454}}
</style></head><body>
<h1>Relatório VerificaLab</h1>
<p class="warn">Evidência determinística — sem IA. Falhas exibidas são reais e não
foram mascaradas. Correlações são hipóteses.</p>
<h2>Execução</h2>
<table class="meta">
<tr><td>ID</td><td><code>{e(str(run['id']))}</code></td></tr>
<tr><td>Estado</td><td class="s-{e(str(run['state']))}">{e(str(run['state']))}</td></tr>
<tr><td>Tipo</td><td>{e(str(run['kind']))}</td></tr>
<tr><td>Resumo</td><td>{e(str(run.get('summary') or ''))}</td></tr>
<tr><td>Início</td><td>{e(str(run.get('started_at') or 'desconhecido'))}</td></tr>
<tr><td>Fim</td><td>{e(str(run.get('finished_at') or 'desconhecido'))}</td></tr>
<tr><td>Alvo</td><td>{j(report['environment']['endpoint'] if report['environment'] else None)}</td></tr>
<tr><td>Perfil</td><td>{e(report['profile']['name'] if report['profile'] else 'desconhecido')}</td></tr>
<tr><td>Gerado em</td><td>{e(report['generated_at'])}</td></tr>
</table>
<h2>Verificações ({len(report['checks'])})</h2>
<table><tr><th>Nome</th><th>Status</th><th>Esperado</th><th>Observado</th>
<th>Mensagem</th></tr>{rows_checks}</table>
<h2>Métricas ({len(report['metrics'])})</h2>
<table><tr><th>Nome</th><th>Valor</th><th>Unidade</th><th>Amostras</th>
<th>População</th><th>Descartes</th><th>Origem</th></tr>{rows_metrics}</table>
<h2>Achados ({len(report['findings'])})</h2>
<table><tr><th>Severidade</th><th>Título</th><th>Descrição</th></tr>{rows_findings}</table>
<h2>Artefatos ({len(report['artifacts'])})</h2>
<table><tr><th>Tipo</th><th>Arquivo</th><th>SHA-256</th><th>Bytes</th></tr>
{rows_arts}</table>
<h2>Limitações</h2><ul>{lims}</ul>
<p>{e(report['platform']['retention'])}</p>
</body></html>"""


def compare_runs(db: Database, a_id: str, b_id: str) -> dict | None:
    """Compara duas execuções: estados, verificações e métricas."""
    a = db.one("SELECT * FROM runs WHERE id = ?", (a_id,))
    b = db.one("SELECT * FROM runs WHERE id = ?", (b_id,))
    if not a or not b:
        return None

    def status_map(run_id: str) -> dict:
        return {r["name"]: r["status"]
                for r in db.query("SELECT name, status FROM check_results "
                                  "WHERE run_id = ?", (run_id,))}

    def counts(statuses: dict) -> dict:
        out = {"pass": 0, "fail": 0, "error": 0, "skip": 0, "unknown": 0}
        for s in statuses.values():
            out[s] = out.get(s, 0) + 1
        return out

    sa, sb = status_map(a_id), status_map(b_id)
    checks = {}
    for n in sorted(set(sa) | set(sb)):
        va, vb = sa.get(n), sb.get(n)
        if va is None:
            change = "apenas_em_b"
        elif vb is None:
            change = "apenas_em_a"
        elif va == vb:
            change = "sem_alteracao"
        elif vb in ("fail", "error") and va == "pass":
            change = "piorou"
        elif va in ("fail", "error") and vb == "pass":
            change = "melhorou"
        else:
            change = "alterado"
        checks[n] = {"a": va or "ausente", "b": vb or "ausente", "change": change}

    def metric_map(run_id: str) -> dict:
        return {(m["name"], m["unit"] or ""): m
                for m in db.query("SELECT * FROM metrics WHERE run_id = ?", (run_id,))}

    ma, mb = metric_map(a_id), metric_map(b_id)
    metrics = []
    for key in sorted(set(ma) | set(mb)):
        x, y = ma.get(key), mb.get(key)
        xv = x["value"] if x else None
        yv = y["value"] if y else None
        delta = pct = None
        if xv is not None and yv is not None:
            delta = round(yv - xv, 4)
            pct = round((yv - xv) / xv * 100, 2) if xv else None
        metrics.append({
            "name": key[0], "unit": key[1] or None,
            "a": xv, "b": yv,
            "a_samples": x["samples"] if x else None,
            "b_samples": y["samples"] if y else None,
            "delta": delta, "delta_pct": pct,
            "origin": (x or y)["origin"],
            "comparable": xv is not None and yv is not None,
            "note": None if (xv is not None and yv is not None)
                    else "valor indisponível em uma das execuções",
        })

    return {
        "a": {"id": a["id"], "state": a["state"], "kind": a["kind"],
              "started_at": a["started_at"], "finished_at": a["finished_at"],
              "summary": a["summary"]},
        "b": {"id": b["id"], "state": b["state"], "kind": b["kind"],
              "started_at": b["started_at"], "finished_at": b["finished_at"],
              "summary": b["summary"]},
        "state_change": f"{a['state']} -> {b['state']}",
        "counts": {"a": counts(sa), "b": counts(sb)},
        "checks": checks,
        "regressed": [n for n, c in checks.items() if c["change"] == "piorou"],
        "improved": [n for n, c in checks.items() if c["change"] == "melhorou"],
        "metrics": metrics,
        "limitations": [
            "Diferenças de métricas consideram populações e amostras distintas "
            "(ver a/b samples); comparabilidade é limitada.",
            "Alteração de estado não explica causa; consulte evidências.",
        ],
    }
