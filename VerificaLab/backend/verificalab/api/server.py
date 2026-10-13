"""Fabricação do app FastAPI: segurança, rotas, estáticos e lifespan."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, config, labctl
from ..catalog import seed_tools
from ..db import get_db
from ..security import check_mutation, host_allowed
from ..worker import Worker
from .routes_core import router as core_router
from .routes_data import router as data_router
from .routes_runs import router as runs_router

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'")


def create_app(start_lab: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config.ensure_dirs()
        db = get_db()
        seed_tools(db)
        app.state.db = db
        app.state.worker = Worker(db)
        app.state.worker.start()   # recupera execuções interrompidas
        if start_lab and os.environ.get("VERIFICALAB_AUTOLAB", "1") != "0":
            result = labctl.start()
            print(f"[app] laboratório: {result.get('message')}")
        try:
            yield
        finally:
            app.state.worker.stop()
            labctl.ensure_stopped_at_exit()

    app = FastAPI(
        title="VerificaLab",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.headers.get("host")
        if not host_allowed(host):
            return JSONResponse({"detail": "Header Host não é loopback"}, 403)
        err = check_mutation(
            request.method, host, request.headers.get("origin"),
            lambda k: request.headers.get(k))
        if err:
            return JSONResponse({"detail": err}, 403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(core_router)
    app.include_router(runs_router)
    app.include_router(data_router)

    if config.FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True),
                  name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def root_fallback() -> dict:
            return {
                "message": "Frontend não compilado. Execute: cd frontend && "
                           "npm install && npm run build",
                "api_docs": "/api/docs",
            }

    return app


app = create_app()
