from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from atlas.api.http_gateway.extraction_routes import router as extraction_router
from atlas.api.http_gateway.governance_routes import router as governance_router
from atlas.api.http_gateway.query_routes import router as query_router
from atlas.core.errors import AtlasError


def create_app(runtime: object | None = None) -> FastAPI:
    app = FastAPI(
        title="Atlas Knowledge Graph Engine",
        version="1.0.0",
        description="Governed research-report knowledge production and query API.",
    )
    if runtime is not None:
        app.state.runtime = runtime
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
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "atlas"}

    return app


app = create_app()
