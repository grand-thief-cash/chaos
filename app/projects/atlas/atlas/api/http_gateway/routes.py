from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from atlas.api.http_gateway.extraction_routes import router as extraction_router
from atlas.api.http_gateway.governance_routes import router as governance_router
from atlas.api.http_gateway.query_routes import router as query_router
from atlas.api.http_gateway.sample_routes import router as sample_router
from atlas.core.errors import AtlasError

logger = logging.getLogger(__name__)


def create_app(runtime: object | None = None) -> FastAPI:
    app = FastAPI(
        title="Atlas Knowledge Graph Engine",
        version="1.0.0",
        description="Governed research-report knowledge production and query API.",
    )
    if runtime is not None:
        app.state.runtime = runtime

        @app.on_event("startup")
        async def _recover_orphaned_runs() -> None:
            # Atlas cannot resume runs that were mid-flight when it last exited;
            # fail them closed so they don't hang as PROCESSING/RUNNING forever.
            try:
                recovered = await runtime.phoenixa.recover_orphaned_runs()  # type: ignore[attr-defined]
                if sum(recovered.values()) > 0:
                    logger.info("recovered orphaned runs on startup: %s", recovered)
            except Exception:
                logger.exception("orphan recovery failed on startup")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(extraction_router)
    app.include_router(governance_router)
    app.include_router(query_router)
    if runtime is None or runtime.config.engine.knowledge_engine.sampling_enabled:
        app.include_router(sample_router)

    @app.exception_handler(AtlasError)
    async def atlas_error_handler(
        _: Request,
        exc: AtlasError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error_code": exc.code, "detail": str(exc)},
        )

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "service": "atlas",
            "environment": runtime.config.env if runtime is not None else "unconfigured",
            "sampling_enabled": bool(
                runtime is not None
                and runtime.config.engine.knowledge_engine.sampling_enabled
            ),
        }

    return app


app = create_app()
