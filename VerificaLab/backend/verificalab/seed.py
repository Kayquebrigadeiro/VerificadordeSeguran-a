"""Semeia o projeto de demonstração: ambiente lab + perfis + suíte demo.

Uso: python3 -m verificalab demo
Idempotente: se o projeto já existir, reaproveita.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .db import Database, utcnow
from .ids import new_id
from .models import ProfileIn
from .targetpolicy import parse_endpoint

DEMO_SUITE_FILES = {
    "test_demo.py": '''"""Suite demo do VerificaLab — casos determinísticos.

test_fail_intencional e test_skip_intencional são DELIBERADOS para
demonstrar que falhas reais aparecem como falha (não mascaradas).
"""
import pytest


def test_pass_simples():
    assert 1 + 1 == 2


def test_pass_lista():
    dados = {"a": 1, "b": 2}
    assert sorted(dados) == ["a", "b"]


def test_fail_intencional():
    """Falha proposital: contrato exige 201, real é 200."""
    status_observado = 200
    assert status_observado == 201, (
        f"esperava 201, observei {status_observado} (falha intencional)")


def test_skip_intencional():
    pytest.skip("caso pendente de implementação")
''',
    "test_slow.py": '''"""Caso longo com filho real — prova cancelamento com killpg.

O subprocesso sleep 300 nasce no MESMO grupo de sinais do pytest; ao
cancelar, o VerificaLab encerra a árvore inteira.
"""
import subprocess
import time


def test_filho_real_longo():
    proc = subprocess.Popen(["sleep", "300"])
    try:
        time.sleep(60)
    finally:
        if proc.poll() is None:
            proc.kill()
''',
}
def ensure_demo_suite() -> Path:
    """Garante os arquivos da suíte demo em data/suite_projects/demo."""
    demo_dir = config.SUITE_PROJECTS_DIR / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    try:
        demo_dir.chmod(0o700)
    except OSError:
        pass
    for name, content in DEMO_SUITE_FILES.items():
        path = demo_dir / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    (demo_dir / "pytest.ini").write_text(
        "[pytest]\naddopts = -p no:cacheprovider\n", encoding="utf-8")
    return demo_dir


HTTP_CONTRACT_CONFIG = {
    "checks": [
        {"name": "status_normal_200", "type": "status", "path": "/ok",
         "method": "GET", "expected_status": 200},
        {"name": "contrato_json_campos", "type": "json_fields", "path": "/json",
         "expected_status": 200,
         "fields": [
             {"path": "service", "type": "string", "equals": "verificalab-lab"},
             {"path": "status", "type": "string", "equals": "running"},
             {"path": "checks.database", "equals": "ok"},
         ]},
        {"name": "content_type_texto", "type": "content_type", "path": "/text",
         "expected_content_type": "text/plain", "expected_status": 200},
        {"name": "resposta_rapida", "type": "max_time", "path": "/ok",
         "max_seconds": 2.0, "expected_status": 200},
        {"name": "erro_controlado_observado", "type": "status", "path": "/error",
         "expected_status": 500},
        {"name": "negacao_403_observada", "type": "status", "path": "/forbidden",
         "expected_status": 403},
        {"name": "redirect_local_seguido", "type": "status",
         "path": "/redirect-local", "expected_status": 200},
        {"name": "resposta_lenta_no_limite", "type": "max_time",
         "path": "/slow?delay=0.3", "max_seconds": 2.0, "expected_status": 200},
        {"name": "FALHA_INTENCIONAL_espera_201", "type": "status", "path": "/ok",
         "expected_status": 201},
        {"name": "FALHA_INTENCIONAL_redirect_externo", "type": "status",
         "path": "/redirect-external", "expected_status": 200},
    ],
    "include_config_checks": True,
    "timeout_s": 8.0,
}

def seed_demo(db: Database) -> str:
    ensure_demo_suite()
    existing = db.one("SELECT id FROM projects WHERE name = ?",
                      ("Laboratório VerificaLab",))
    if existing:
        return (f"demo já existe (projeto {existing['id']}); suíte demo em "
                f"{config.SUITE_PROJECTS_DIR / 'demo'}")

    scheme, host, port = parse_endpoint(f"http://{config.LAB_HOST}:{config.LAB_PORT}")
    prj = new_id("prj")
    db.insert("projects", {"id": prj, "name": "Laboratório VerificaLab",
                           "description": "Projeto de demonstração com o lab "
                                          "descartável em loopback.",
                           "created_at": utcnow()})
    env = new_id("env")
    db.insert("environments", {
        "id": env, "project_id": prj, "name": "lab-local",
        "scheme": scheme, "host": host, "port": port, "kind": "lab",
        "secret_header_name": None, "created_at": utcnow()})

    demo_dir = str((config.SUITE_PROJECTS_DIR / "demo").resolve())
    profiles = [
        ("Contrato do laboratório", "http", HTTP_CONTRACT_CONFIG),
        ("Observação de configuração HTTP", "http", {
            "checks": [{"name": "headers_rota_sem_seguranca", "type": "status",
                        "path": "/headers", "expected_status": 200}],
            "include_config_checks": True, "timeout_s": 8.0}),
        ("Carga leve (2 rps, 6 s)", "load", {
            "path": "/ok", "method": "GET", "rps": 2.0, "duration_s": 6.0,
            "concurrency": 2, "max_attempts": 20, "timeout_s": 5.0,
            "expect_status": 200}),
        ("Suite rápida (pytest demo)", "suite", {
            "command": ["python3", "-m", "pytest", "-q", "test_demo.py"],
            "cwd": demo_dir, "timeout_s": 60}),
        ("Suite longa (para cancelamento)", "suite", {
            "command": ["python3", "-m", "pytest", "-q", "test_slow.py"],
            "cwd": demo_dir, "timeout_s": 120}),
    ]
    made = []
    for name, kind, cfg in profiles:
        payload = ProfileIn(project_id=prj, name=name, kind=kind, config=cfg)
        pid = new_id("prf")
        db.insert("test_profiles", {
            "id": pid, "project_id": prj, "name": name, "kind": kind,
            "config_json": json.dumps(payload.config, ensure_ascii=False),
            "created_at": utcnow()})
        made.append(f"{kind}:{name}")
    db.audit("demo.seed", "project", prj, {"profiles": made})
    return (f"demo criado: projeto {prj}, ambiente {env} "
            f"({scheme}://{host}:{port}), perfis: {', '.join(made)}")
