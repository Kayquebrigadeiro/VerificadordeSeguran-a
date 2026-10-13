"""Catálogo estático das oito ferramentas do inventário.

Evidência: leitura dos fontes no repositório (11/10/2026). Catalogar não
significa executar, copiar ou integrar métodos ofensivos. Nenhuma capacidade
de flood/amplificação é acionada pelo VerificaLab.
"""

from __future__ import annotations

TOOLS: list[dict] = [
    {
        "slug": "mikumikubeam",
        "name": "MikuMikuBeam",
        "upstream_path": "mikumikubeam",
        "language": "Go",
        "license": "MIT (arquivo LICENSE presente)",
        "capabilities": ["HTTP flood", "TCP flood", "Slowloris", "burst",
                         "interface web (mmb-server)"],
        "import_formats": [],
        "notes": (
            "Catalogada. Estatísticas emitidas apenas por stream "
            "(WebSocket client.Emit(stats) com timestamp, pps, totalPackets, "
            "log) — sem arquivo exportável; importador NÃO implementado "
            "(lacuna documentada). Cancelamento por context anotado como "
            "referência. Métodos de flood não integrados."
        ),
    },
    {
        "slug": "ddoslayer",
        "name": "DDoSlayer",
        "upstream_path": "ddoslayer",
        "language": "Python",
        "license": "GPL-3.0 (arquivo LICENSE presente)",
        "capabilities": ["HTTP", "Slowloris", "SYN", "UDP", "recomendador de ataques"],
        "import_formats": ["ddoslayer-json"],
        "notes": (
            "Catalogada. Exportação JSON confirmada no fonte "
            "(export_log_json -> logs/{attack_id}.json com attack_id, "
            "timestamp, target, results.packets_sent, success_rate, avg_rate). "
            "packets_sent/success_rate NÃO são reinterpretadas como métricas "
            "HTTP. Recomendador de ataques não reutilizado."
        ),
    },
    {
        "slug": "slowloris",
        "name": "Slowloris",
        "upstream_path": "slowloris",
        "language": "Python",
        "license": "MIT (arquivo LICENSE presente)",
        "capabilities": ["conexões HTTP incompletas (slowloris)"],
        "import_formats": [],
        "notes": "Catalogada. Nenhum executor de conexões incompletas na primeira versão.",
    },
    {
        "slug": "mhddos",
        "name": "MHDDoS",
        "upstream_path": "mhddos",
        "language": "Python",
        "license": "MIT (arquivo LICENSE presente)",
        "capabilities": ["57 métodos L4/L7", "proxies", "amplificação"],
        "import_formats": [],
        "notes": "Catalogada. Sem execução automática, sem download de proxies, sem amplificação.",
    },
    {
        "slug": "impulse",
        "name": "Impulse",
        "upstream_path": "impulse",
        "language": "Python",
        "license": "GPL-3.0 (arquivo LICENSE presente)",
        "capabilities": ["UDP", "SYN", "ICMP", "NTP", "HTTP", "SMS/EMAIL"],
        "import_formats": [],
        "notes": "Catalogada. Sem importação dos módulos SMS/EMAIL e sem execução de métodos.",
    },
    {
        "slug": "pyddos",
        "name": "PyDDoS",
        "upstream_path": "pyddos",
        "language": "Python",
        "license": "não identificada (sem arquivo LICENSE)",
        "capabilities": ["SYN", "HTTP", "Slowloris"],
        "import_formats": [],
        "notes": (
            "Catalogada. Instalação automática privilegiada e interatividade "
            "registradas como obstáculos. Sem arquivo de licença."
        ),
    },
    {
        "slug": "overload",
        "name": "Overload",
        "upstream_path": "overload",
        "language": "Python",
        "license": "MIT (arquivo LICENSE presente)",
        "capabilities": ["HTTP", "Slowloris", "SYN", "ARP", "disconnect"],
        "import_formats": [],
        "notes": "Catalogada. Manutenção e sobreposição registradas. Sem módulos L2.",
    },
    {
        "slug": "ufonet",
        "name": "UFONet",
        "upstream_path": "ufonet",
        "language": "Python",
        "license": "não identificada na raiz (docs/LICENSE presente, não revisado)",
        "capabilities": ["open redirect", "amplificação L3", "darknet", "botnet"],
        "import_formats": [],
        "notes": "Catalogada. Sem mecanismo distribuído nem recursos de terceiros.",
    },
]

# Correções do relatório original (evidência lida no repositório)
INVENTORY_CAVEATS = [
    "`__pycache__` indica possível importação/compilação, não execução bem-sucedida.",
    "Binário existente não comprova que funciona.",
    "Scan de portas é uma verificação ativa.",
    "Faixas privadas ou loopback amplas não constituem autorização automática.",
    "Contagem de pacotes enviados não equivale a requisições HTTP concluídas com sucesso.",
]


def seed_tools(db) -> None:
    """Insere o catálogo na primeira execução (idempotente por slug)."""
    import json as _json

    from .db import utcnow
    from .ids import new_id

    for tool in TOOLS:
        if db.one("SELECT id FROM tools WHERE slug = ?", (tool["slug"],)):
            continue
        db.insert("tools", {
            "id": new_id("tool"),
            "slug": tool["slug"],
            "name": tool["name"],
            "upstream_path": tool["upstream_path"],
            "language": tool["language"],
            "license": tool["license"],
            "status": "cataloged",
            "capabilities_json": _json.dumps(tool["capabilities"], ensure_ascii=False),
            "import_formats_json": _json.dumps(tool["import_formats"], ensure_ascii=False),
            "notes": tool["notes"],
            "cataloged_at": utcnow(),
        })
