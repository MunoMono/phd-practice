from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from strawberry.fastapi import GraphQLRouter
import asyncio
import logging
import os

from app.api.routes import agent, sessions, experiments, metrics, documents, sync, graphql_sync, provenance, analysis, viz, search, missingness, claims, query_runs, cross_read, authorities, retrieval
from app.api.graphql.schema import schema
from app.core.config import settings
from app.services.inference_service import initialize_inference_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting Testamentary Traces Research API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    inference_init_task = None

    auto_load = os.getenv("TURIN_AUTO_LOAD", "true").strip().lower() in {"1", "true", "yes", "on"}
    if auto_load:
        inference_init_task = asyncio.create_task(initialize_inference_service())
        logger.info("Active Turin runtime auto-load started in background")
    else:
        logger.info("Active Turin runtime auto-load disabled by TURIN_AUTO_LOAD")

    yield
    if inference_init_task and not inference_init_task.done():
        inference_init_task.cancel()
    logger.info("Shutting down Testamentary Traces Research API")


app = FastAPI(
    title="Testamentary Traces Research API",
    description="FastAPI backend for the Turin local research instrument",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(graphql_sync.router, prefix="/api/v1", tags=["graphql-sync"])
app.include_router(provenance.router, prefix="/api/provenance", tags=["provenance"])
app.include_router(analysis.router, prefix="/api/runtime", tags=["runtime-analysis"])
app.include_router(analysis.exploratory_router, prefix="/api/analysis", tags=["exploratory-analysis"])
app.include_router(viz.router, prefix="/api/viz", tags=["visualizations"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(missingness.router, prefix="/api/missingness", tags=["missingness"])
app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(query_runs.router, prefix="/api/query-runs", tags=["query-runs"])
app.include_router(cross_read.router, prefix="/api/cross-read", tags=["cross-read"])
app.include_router(authorities.router, prefix="/api/authorities", tags=["authorities"])
app.include_router(retrieval.router, prefix="/api/retrieval", tags=["retrieval"])

# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/api/graphql")


@app.get("/")
async def root():
    return {
        "message": "Testamentary Traces Research API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
