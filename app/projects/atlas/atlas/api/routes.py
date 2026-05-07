"""FastAPI application and root router."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlas.api.documents import router as doc_router
from atlas.api.graph import router as graph_router
from atlas.api.analysis import router as analysis_router
from atlas.api.pipeline import router as pipeline_router
from atlas.connectors.neo4j_client import ensure_schema, close as close_neo4j


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    ensure_schema()
    yield
    # Shutdown
    close_neo4j()


app = FastAPI(
    title="Atlas — Industry Chain Knowledge Graph Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(doc_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["pipeline"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "atlas"}

