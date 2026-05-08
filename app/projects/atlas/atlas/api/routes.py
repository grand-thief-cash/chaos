"""FastAPI application and root router."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas.api.documents import router as doc_router
from atlas.api.graph import router as graph_router
from atlas.api.analysis import router as analysis_router
from atlas.api.pipeline import router as pipeline_router
from atlas.api.web_clip import router as web_clip_router
from atlas.api.extraction import router as extraction_router
from atlas.connectors.neo4j_client import ensure_schema as ensure_neo4j_schema, close as close_neo4j
from atlas.connectors import phoenixa_client


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup — ensure Neo4j schema via PhoenixA
    await ensure_neo4j_schema()
    yield
    # Shutdown
    await close_neo4j()
    await phoenixa_client.close()


app = FastAPI(
    title="Atlas — Industry Chain Knowledge Graph Engine",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for cthulhu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(doc_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(web_clip_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(extraction_router, prefix="/api/v1/extractions", tags=["extractions"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "atlas"}

