"""Executor de testes HTTP de contrato + verificações de configuração.

Determinístico: compara observação com expectativa. Ausência de header vira
ACHADO INFORMATIVO (conclusão contextualizada), nunca vulnerabilidade automática.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..metrics import latency_summary
from ..models import HttpCheck, HttpProfileConfig
from ..targetpolicy import TargetPolicy
from .common import HttpOutcome, make_client, send_checked

# Cabeçalhos observados nas verificações de configuração (observação, não falha)
CONFIG_HEADERS = [
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "strict-transport-security",
]

PY_TYPES = {"string": str, "number": (int, float), "bool": bool,
            "boolean": bool, "object": dict, "array": list}


def _get_path(obj: Any, dotted: str) -> tuple[bool, Any]:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False, None
    return True, cur


def _eval_check(check: HttpCheck, out: HttpOutcome) -> dict:
    """Avalia um check contra a observação -> resultado padronizado."""
    result: dict[str, Any] = {
        "name": check.name, "category": "contract",
        "expected": "", "observed": "", "message": "",
        "evidence": {}, "duration_ms": out.duration_ms, "status": "fail",
    }
    ev = result["evidence"]
    ev["request"] = {"method": check.method, "path": check.path}
    ev["response"] = {
        "status": out.status, "duration_ms": round(out.duration_ms or 0, 3),
        "redirects": out.redirects, "blocked_redirect": out.blocked_redirect,
        "body_truncated": out.truncated,
        "content_type": out.headers.get("content-type"),
    }

    if out.error:
        # O runner está de pé; a observação é que o alvo não respondeu.
        result["expected"] = f"resposta HTTP {check.expected_status}"
        result["observed"] = out.error
        result["message"] = (
            f"Resposta não obtida ({out.error}); contrato observado como não atendido."
        )
        ev["response"]["error_detail"] = out.error_detail
        return result

    if out.blocked_redirect:
        result["expected"] = "redirect somente para destino cadastrado"
        result["observed"] = "redirect bloqueado"
        result["message"] = out.blocked_redirect
        return result

    status = out.status
    body_text: str | None = None
    if check.type in ("json_fields", "body_contains"):
        body_text = out.content.decode("utf-8", errors="replace")

    if check.type == "status":
        result["expected"] = str(check.expected_status)
        result["observed"] = str(status)
        if status == check.expected_status:
            result["status"] = "pass"
            result["message"] = f"Status {status} conforme esperado."
        else:
            result["message"] = f"Status observado {status}, esperado {check.expected_status}."
        return result

    if check.type == "max_time":
        dur = out.duration_ms or 0
        limit_ms = check.max_seconds * 1000
        result["expected"] = f"<= {check.max_seconds}s"
        result["observed"] = f"{dur / 1000:.3f}s"
        if status == check.expected_status and dur <= limit_ms:
            result["status"] = "pass"
            result["message"] = f"Resposta em {dur:.0f}ms dentro do limite."
        elif status != check.expected_status:
            result["message"] = f"Status {status} difere do esperado {check.expected_status}."
        else:
            result["message"] = f"Tempo {dur:.0f}ms excede limite {limit_ms:.0f}ms."
        return result

    if check.type == "content_type":
        observed_ct = out.headers.get("content-type", "")
        media = observed_ct.split(";")[0].strip().lower()
        expected = (check.expected_content_type or "").split(";")[0].strip().lower()
        result["expected"] = expected
        result["observed"] = media or "(ausente)"
        if media == expected:
            result["status"] = "pass"
            result["message"] = "Content-Type conforme esperado."
        else:
            result["message"] = f"Content-Type {media or '(ausente)'} difere de {expected}."
        if status != check.expected_status:
            result["message"] += f" Status {status} difere de {check.expected_status}."
        return result

    if check.type == "header":
        hv = out.headers.get(check.header.lower())
        result["expected"] = (f"{check.header} presente" if check.header_value is None
                              else f"{check.header} = {check.header_value}")
        result["observed"] = hv if hv is not None else "(ausente)"
        if hv is None:
            result["message"] = f"Cabeçalho {check.header} ausente."
        elif check.header_value is None or hv == check.header_value:
            result["status"] = "pass"
            result["message"] = f"Cabeçalho {check.header} conforme esperado."
        else:
            result["message"] = f"Cabeçalho {check.header} difere do esperado."
        return result

    if check.type == "body_contains":
        result["expected"] = f"contém {check.substring!r}"
        if body_text is not None and check.substring in body_text:
            result["status"] = "pass"
            result["observed"] = "substring presente"
            result["message"] = "Corpo contém o texto esperado."
        else:
            result["observed"] = "substring ausente"
            result["message"] = "Corpo não contém o texto esperado."
        return result


    if check.type == "json_fields":
        try:
            data = json.loads(out.content.decode("utf-8", errors="strict"))
        except Exception as exc:
            result["expected"] = "JSON válido"
            result["observed"] = f"JSON inválido: {type(exc).__name__}"
            result["message"] = "Resposta não é JSON parseável."
            return result
        problems = []
        observed_map: dict = {}
        for fexp in check.fields:
            found, value = _get_path(data, fexp.path)
            if not found:
                problems.append(f"campo '{fexp.path}' ausente")
                observed_map[fexp.path] = None
                continue
            observed_map[fexp.path] = value if not isinstance(value, (dict, list)) else type(value).__name__
            if fexp.type:
                allowed = PY_TYPES.get(fexp.type)
                if allowed and not isinstance(value, allowed):
                    problems.append(
                        f"campo '{fexp.path}' tipo {type(value).__name__}, esperado {fexp.type}")
            if fexp.equals is not None and value != fexp.equals:
                problems.append(f"campo '{fexp.path}' = {value!r}, esperado {fexp.equals!r}")
        result["expected"] = ", ".join(f.path for f in check.fields)
        result["observed"] = json.dumps(observed_map, ensure_ascii=False, default=str)[:500]
        ev["json_fields"] = observed_map
        if status != check.expected_status:
            result["message"] = f"Status {status} difere de {check.expected_status}."
        elif problems:
            result["message"] = "; ".join(problems)
        else:
            result["status"] = "pass"
            result["message"] = f"{len(check.fields)} campo(s) conforme esperado."
        return result

    result["status"] = "error"
    result["message"] = f"Tipo de check não suportado: {check.type}"
    return result


def _config_observations(out: HttpOutcome, *, https: bool) -> tuple[dict, list[dict]]:
    """Análise de cabeçalhos de configuração -> (evidência, achados informativos).

    Ausência de header NÃO é vulnerabilidade: conclusão contextualizada.
    """
    present, missing = [], []
    for h in CONFIG_HEADERS:
        if h in out.headers:
            present.append(h)
        else:
            missing.append(h)
    findings = []
    for h in missing:
        ctx = ""
        if h == "strict-transport-security" and not https:
            ctx = (" HSTS só se aplica a HTTPS; neste endpoint HTTP a ausência "
                   "não indica problema.")
        findings.append({
            "severity": "info", "hypothesis": 0,
            "title": f"Cabeçalho {h} ausente",
            "description": (
                f"Resposta observada sem o cabeçalho {h}. Ausência de cabeçalho "
                f"é uma observação de configuração, não uma vulnerabilidade "
                f"comprovada; o impacto depende do contexto da aplicação.{ctx}"
            ),
            "evidence": {"header": h, "observed_in": "resposta de verificação",
                         "status": out.status,
                         "server": out.headers.get("server")},
        })
    if "set-cookie" in out.headers:
        cookie = out.headers["set-cookie"]
        flags = [f for f in ("httponly", "secure", "samesite") if f in cookie.lower()]
        absent = [f for f in ("httponly", "secure", "samesite") if f not in cookie.lower()]
        if absent:
            findings.append({
                "severity": "info", "hypothesis": 0,
                "title": "Cookie sem sinalizadores: " + ", ".join(absent),
                "description": (
                    "Set-Cookie observado sem " + ", ".join(absent) + ". Trata-se "
                    "de observação de configuração; adequação depende do uso do cookie."
                ),
                "evidence": {"cookie_flags_present": flags,
                             "cookie_flags_absent": absent},
            })
    evidence = {
        "headers_present": present,
        "headers_absent": missing,
        "server": out.headers.get("server"),
        "conclusion": (
            "Abaixo do padrão de cabeçalhos modernos, mas ausência isolada não "
            "comprova vulnerabilidade; ver Achados para conclusão contextualizada."
        ),
    }
    return evidence, findings


def run_http_checks(ctx) -> dict:
    """Executa os checks de contrato (+ observações de configuração) do perfil."""
    cfg = HttpProfileConfig.model_validate(ctx.cfg)
    env = ctx.env
    policy = TargetPolicy(env["scheme"], env["host"], env["port"])
    results: list[dict] = []
    findings: list[dict] = []
    latencies: list[float] = []
    discarded = 0
    cancelled = False
    timed_out = False

    headers: dict[str, str] = {}
    if ctx.secret_header and env.get("secret_header_name"):
        headers[env["secret_header_name"]] = ctx.secret_header

    client = make_client(cfg.timeout_s)
    first_out: HttpOutcome | None = None
    try:
        total = len(cfg.checks) + (1 if cfg.include_config_checks else 0)
        done = 0
        for check in cfg.checks:
            if ctx.cancel_event.is_set():
                cancelled = True
                break
            if ctx.deadline_reached():
                timed_out = True
                break
            try:
                url = policy.build(check.path)
            except Exception as exc:  # config inválida -> runner não conclui
                results.append({
                    "name": check.name, "category": "contract", "status": "error",
                    "expected": f"path válido em {policy.origin}",
                    "observed": check.path, "message": f"Configuração inválida: {exc}",
                    "evidence": {"error": str(exc)}, "duration_ms": None,
                })
                done += 1
                ctx.set_progress(done / total)
                continue
            out = send_checked(client, policy, url, method=check.method, headers=headers)
            if first_out is None:
                first_out = out
            res = _eval_check(check, out)
            results.append(res)
            if out.ok_transport:
                latencies.append(out.duration_ms or 0.0)
            else:
                discarded += 1
            ctx.log("info", f"check '{check.name}': {res['status']} — {res['message']}")
            done += 1
            ctx.set_progress(done / total)

        if cfg.include_config_checks and not cancelled and not timed_out:
            obs_out = first_out
            if obs_out is None or not obs_out.ok_transport:
                try:
                    obs_url = policy.build(cfg.checks[0].path)
                    obs_out = send_checked(client, policy, obs_url, headers=headers)
                except Exception as exc:
                    ctx.log("warn", f"observação de configuração indisponível: {exc}")
                    obs_out = None
            if obs_out is not None and obs_out.ok_transport:
                evidence, fnds = _config_observations(
                    obs_out, https=(policy.scheme == "https"))
                findings.extend(fnds)
                results.append({
                    "name": "observacao_cabecalhos_configuracao",
                    "category": "config", "status": "unknown",
                    "expected": "observação de configuração registrada",
                    "observed": f"{len(evidence['headers_present'])} presentes, "
                                f"{len(evidence['headers_absent'])} ausentes",
                    "message": (
                        "Conclusão contextualizada registrada em Achados: ausência "
                        "de cabeçalho não é vulnerabilidade comprovada."
                    ),
                    "evidence": evidence, "duration_ms": None,
                })
            done += 1
            ctx.set_progress(done / total)
    finally:
        client.close()

    out_dict: dict = {
        "checks": results,
        "findings": findings,
        "metrics": [],
        "artifacts": [],
    }
    latency = latency_summary(
        latencies,
        population="requisições concluídas pelos checks (ida e volta observada "
                   "pelo cliente VerificaLab)",
        discarded=discarded,
    )
    latency["name"] = "latency_checks_ms"
    out_dict["metrics"].append(latency)
    if cancelled:
        out_dict["state"] = "cancelled"
        out_dict["summary"] = "Execução cancelada antes de concluir todos os checks."
    elif timed_out:
        out_dict["state"] = "timed_out"
        out_dict["summary"] = "Limite de duração da execução atingido."
    else:
        out_dict["summary"] = (
            f"{len(results)} verificações executadas contra {policy.origin}."
        )
    return out_dict

