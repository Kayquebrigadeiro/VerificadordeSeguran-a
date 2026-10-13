"""Configuração e limites do VerificaLab.

Todos os valores podem ser sobrescritos por variáveis de ambiente com o
prefixo VERIFICALAB_. Os limites de carga abaixo são tetos fixos da
especificação e NÃO podem ser elevados pela API.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Diretórios
# ---------------------------------------------------------------------------
# backend/verificalab/config.py -> VerificaLab/
BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
DATA_DIR = Path(os.environ.get("VERIFICALAB_DATA", str(BASE_DIR / "data"))).resolve()
DB_PATH = DATA_DIR / "verificalab.sqlite3"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
EXPORTS_DIR = DATA_DIR / "exports"
SECRETS_DIR = DATA_DIR / "secrets"
KEY_PATH = SECRETS_DIR / "secret.key"
AUTHORIZATION_FILE = SECRETS_DIR / "authorization.json"
SUITE_PROJECTS_DIR = DATA_DIR / "suite_projects"
LOGS_DIR = DATA_DIR / "logs"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


def ensure_dirs() -> None:
    """Cria os diretórios privados da aplicação (permissão 0700)."""
    for d in (DATA_DIR, ARTIFACTS_DIR, EXPORTS_DIR, SECRETS_DIR, SUITE_PROJECTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
        try:
            d.chmod(0o700)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Servidor (somente loopback)
# ---------------------------------------------------------------------------
HOST = os.environ.get("VERIFICALAB_HOST", "127.0.0.1")
PORT = int(os.environ.get("VERIFICALAB_PORT", "8400"))

# Laboratório descartável (alvo de demonstração)
LAB_HOST = "127.0.0.1"
LAB_PORT = int(os.environ.get("VERIFICALAB_LAB_PORT", "8477"))
LAB_PATH = BACKEND_DIR / "verificalab" / "labapp.py"

# Hosts aceitos nas requisições (controle de acesso local)
ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "::1", "[::1]"}
ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
    f"http://127.0.0.1:{os.environ.get('VERIFICALAB_DEV_PORT', '5173')}",
    f"http://localhost:{os.environ.get('VERIFICALAB_DEV_PORT', '5173')}",
}

# ---------------------------------------------------------------------------
# Limites globais de carga (piloto) — tetos fixos, nunca elevados pela API
# ---------------------------------------------------------------------------
LOAD_DEFAULT_RPS = 1.0        # 1 requisição/segundo por padrão
LOAD_MAX_RPS = 5.0            # teto de 5 rps
LOAD_MAX_CONCURRENCY = 2      # concorrência máxima 2
LOAD_MAX_DURATION_S = 30.0    # duração máxima 30 s
LOAD_MAX_ATTEMPTS = 150       # total máximo 150 tentativas
LOAD_ALLOWED_METHODS = ("GET", "HEAD")   # GET/HEAD somente no piloto
LOAD_REQUEST_TIMEOUT_S = 10.0

# Limites de sub-processos (suite runner)
SUITE_MAX_TIMEOUT_S = 300
SUITE_MAX_OUTPUT_BYTES = 1_000_000        # 1 MB de saída incremental
SUITE_KILL_GRACE_S = 2.0                  # prazo documentado: SIGTERM -> SIGKILL
SUITE_ALLOWED_COMMANDS = (                 # comandos pré-configurados (lista, sem shell)
    ("python3", "-m", "pytest"),
    ("python3", "-m", "py.test"),
    ("pytest",),
    ("py.test",),
)

# Limites de importação e upload
MAX_UPLOAD_BYTES = 2 * 1024 * 1024        # 2 MB por upload
MAX_LOG_LINES = 20_000
MAX_LOG_LINE_CHARS = 2_000
MAX_XML_BYTES = 2 * 1024 * 1024
MAX_XML_RECORDS = 10_000
MAX_JSON_RECORDS = 50_000
MAX_XML_DEPTH = 20

# Limites de requisições HTTP de teste
HTTP_MAX_RESPONSE_BYTES = 512 * 1024      # 512 KB por resposta lida
HTTP_DEFAULT_TIMEOUT_S = 10.0

# Retenção: logs e artefatos permanecem até remoção manual (documentado)
RETENTION_NOTE = (
    "Dados persistidos localmente em SQLite (data/verificalab.sqlite3) e "
    "artefatos em data/artifacts. Retenção: até remoção manual pelo usuário; "
    "nenhum dado sai da máquina."
)
