"""CLI do VerificaLab: serve, migrate, lab, demo, tui."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verificalab",
        description="VerificaLab — testes locais controlados e investigação "
                    "por evidências (sem IA).")
    sub = parser.add_subparsers(dest="cmd")

    p_serve = sub.add_parser("serve", help="inicia a plataforma (somente loopback)")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--no-lab", action="store_true",
                         help="não inicia o laboratório junto")

    sub.add_parser("migrate", help="aplica migrações e semeia catálogo")

    p_lab = sub.add_parser("lab", help="controla o laboratório")
    p_lab.add_argument("action", choices=["start", "stop", "status"])

    sub.add_parser("demo", help="cria projeto/perfis de demonstração")

    sub.add_parser("tui", help="abre o painel interativo de ferramentas")

    args = parser.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn

        from . import config
        from .api.server import create_app

        port = args.port or config.PORT
        app = create_app(start_lab=not args.no_lab)
        print(f"[verificalab] http://{config.HOST}:{port} (loopback apenas)")
        uvicorn.run(app, host=config.HOST, port=port, log_level="warning")
        return 0

    if args.cmd == "migrate":
        from .catalog import seed_tools
        from .db import get_db

        db = get_db()
        seed_tools(db)
        print(f"migrações aplicadas; schema v{db.schema_version}; "
              f"catálogo: {db.one('SELECT COUNT(*) AS c FROM tools')['c']} ferramentas")
        return 0

    if args.cmd == "lab":
        from . import labctl

        fn = {"start": labctl.start, "stop": labctl.stop,
              "status": labctl.status}[args.action]
        print(fn())
        return 0

    if args.cmd == "demo":
        from .catalog import seed_tools
        from .db import get_db
        from .seed import seed_demo

        db = get_db()
        seed_tools(db)
        summary = seed_demo(db)
        print(summary)
        return 0

    if args.cmd == "tui":
        from .tui.app import VerificaLabApp

        VerificaLabApp().run()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
