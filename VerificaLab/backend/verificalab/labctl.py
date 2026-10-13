"""Controle do laboratório: iniciar/parar/verificar o subprocesso do alvo.

O lab é iniciado pela plataforma como subprocesso em grupo de sinais
próprio (start_new_session), somente em loopback, e encerrado junto com
a árvore quando a plataforma para.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import config

_proc: subprocess.Popen | None = None
_log_handle = None


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def status() -> dict:
    running = _port_open(config.LAB_HOST, config.LAB_PORT)
    return {
        "running": running,
        "pid": _proc.pid if (_proc and _proc.poll() is None) else None,
        "endpoint": f"http://{config.LAB_HOST}:{config.LAB_PORT}",
        "managed_by": "verificalab" if (_proc and _proc.poll() is None)
                      else ("externo/desconhecido" if running else None),
    }


def start() -> dict:
    global _proc, _log_handle
    if _port_open(config.LAB_HOST, config.LAB_PORT):
        return {**status(), "message": "lab já ativo nesta porta"}
    if _proc and _proc.poll() is not None:
        _proc = None
    config.ensure_dirs()
    log_path = config.LOGS_DIR / "lab.log"
    _log_handle = open(log_path, "ab", buffering=0)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONUNBUFFERED": "1"}
    _proc = subprocess.Popen(
        [sys.executable, str(config.LAB_PATH),
         "--port", str(config.LAB_PORT)],
        cwd=str(config.BACKEND_DIR), env=env,
        stdout=_log_handle, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    for _ in range(50):
        if _port_open(config.LAB_HOST, config.LAB_PORT):
            break
        if _proc.poll() is not None:
            break
        time.sleep(0.1)
    return {**status(), "message": "lab iniciado" if status()["running"]
            else "falha ao iniciar lab (ver data/logs/lab.log)"}


def stop() -> dict:
    global _proc, _log_handle
    killed = False
    if _proc and _proc.poll() is None:
        try:
            pgid = os.getpgid(_proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            _proc.wait(timeout=3)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(_proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        killed = True
        _proc = None
    elif _port_open(config.LAB_HOST, config.LAB_PORT):
        # porta aberta sem processo nosso: não matamos processos alheios
        return {**status(),
                "message": "porta ativa mas não gerenciada pelo VerificaLab; "
                           "não encerrada (sem autorização)"}
    if _log_handle:
        try:
            _log_handle.close()
        except OSError:
            pass
        _log_handle = None
    time.sleep(0.2)
    return {**status(), "message": "lab encerrado" if killed else "lab já parado"}


def ensure_stopped_at_exit() -> None:
    global _proc
    if _proc and _proc.poll() is None:
        try:
            os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        _proc = None
