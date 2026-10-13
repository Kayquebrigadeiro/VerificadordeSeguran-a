"""Relatórios seguros JSON, Markdown e HTML para execuções orquestradas."""

from __future__ import annotations

import html
import json
from pathlib import Path

from verificalab import config
from verificalab.security import redact_obj

LIMITATIONS = (
    "Somente alvos loopback explícitos são suportados pelos adapters.",
    "Não há amplificação de tráfego nem uso de proxies externos.",
    "Cada ferramenta respeita os limites de duração e threads do catálogo.",
    "Resultados descrevem somente o comportamento observado nesta execução.",
)


def _report_data(summary) -> dict:
    if hasattr(summary, "to_dict"):
        data = summary.to_dict()
    elif isinstance(summary, dict):
        data = dict(summary)
    else:
        raise TypeError("summary deve ser um RunSummary ou dicionário")
    data["limitations"] = list(LIMITATIONS)
    return redact_obj(data)


def _export_path(summary: dict, extension: str) -> Path:
    run_id = summary.get("run_id")
    if not isinstance(run_id, str) or not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in run_id
    ):
        raise ValueError("summary.run_id inválido")
    config.ensure_dirs()
    return config.EXPORTS_DIR / f"{run_id}.{extension}"


def to_json(summary) -> Path:
    data = _report_data(summary)
    path = _export_path(data, "json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def to_markdown(summary) -> Path:
    data = _report_data(summary)
    path = _export_path(data, "md")
    executions = data.get("executions", [])
    rows = [
        "| Ferramenta | Resultado | Código | Duração (s) |",
        "|---|---:|---:|---:|",
    ]
    for execution in executions:
        name = str(execution.get("tool_name") or execution.get("tool_id") or "desconhecida")
        rows.append(
            f"| {name.replace('|', '\\|').replace('\\n', ' ')} "
            f"| {'OK' if execution.get('ok') else 'Falha'} "
            f"| {execution.get('returncode', '—')} "
            f"| {execution.get('total_duration', 0)} |"
        )
    limitations = "\n".join(f"- {item}" for item in data["limitations"])
    content = (
        f"# Relatório VerificaLab — {data.get('run_id', '')}\n\n"
        f"- **Alvo:** {data.get('target', '')}\n"
        f"- **Resultado geral:** {'OK' if data.get('ok') else 'Falha'}\n"
        f"- **Início:** {data.get('started_at', '')}\n"
        f"- **Fim:** {data.get('ended_at', '')}\n"
        f"- **Duração total (s):** {data.get('total_duration', 0)}\n\n"
        "## Ferramentas executadas\n\n"
        + "\n".join(rows)
        + "\n\n## Limitações\n\n"
        + limitations
        + "\n"
    )
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def to_html(summary) -> Path:
    data = _report_data(summary)
    path = _export_path(data, "html")
    escape = html.escape
    executions = data.get("executions", [])
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('tool_name') or item.get('tool_id') or 'desconhecida'))}</td>"
        f"<td>{'OK' if item.get('ok') else 'Falha'}</td>"
        f"<td>{escape(str(item.get('returncode', '—')))}</td>"
        f"<td>{escape(str(item.get('total_duration', 0)))}</td>"
        "</tr>"
        for item in executions
    ) or "<tr><td colspan='4'>Nenhuma ferramenta executada</td></tr>"
    limitations = "".join(f"<li>{escape(item)}</li>" for item in data["limitations"])
    document = f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VerificaLab — relatório {escape(str(data.get('run_id', '')))}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:70rem;margin:2rem auto;padding:0 1rem;color:#172033}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd;padding:.5rem;text-align:left}}
th{{background:#eef1f7}}.status{{font-weight:600}}.limitations{{background:#f5f7fa;padding:1rem}}
</style></head>
<body><h1>Relatório VerificaLab</h1>
<p class="status">Resultado: {'OK' if data.get('ok') else 'Falha'}</p>
<dl><dt>Execução</dt><dd>{escape(str(data.get('run_id', '')))}</dd>
<dt>Alvo</dt><dd>{escape(str(data.get('target', '')))}</dd>
<dt>Início</dt><dd>{escape(str(data.get('started_at', '')))}</dd>
<dt>Fim</dt><dd>{escape(str(data.get('ended_at', '')))}</dd>
<dt>Duração total</dt><dd>{escape(str(data.get('total_duration', 0)))} s</dd></dl>
<h2>Ferramentas executadas</h2>
<table><thead><tr><th>Ferramenta</th><th>Resultado</th><th>Código</th><th>Duração (s)</th>
</tr></thead><tbody>{rows}</tbody></table>
<section class="limitations"><h2>Limitações</h2><ul>{limitations}</ul></section>
</body></html>
"""
    path.write_text(document, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
