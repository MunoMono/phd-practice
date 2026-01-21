from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from strawberry.fastapi import GraphQLRouter
import logging

from app.api.routes import agent, sessions, experiments, metrics, documents, sync, graphql_sync, provenance, analysis
from app.api.graphql.schema import schema
from app.core.config import settings
from app.services.granite_service import initialize_granite

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
    logger.info("Starting Epistemic Drift Research API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Granite auto-loading disabled to prevent OOM on 8GB RAM
    # Load manually via: POST /api/granite/load-model
    logger.info("Granite LLM service: Manual loading required (use /api/granite/load-model endpoint)")
    
    yield
    logger.info("Shutting down Epistemic Drift Research API")


app = FastAPI(
    title="Epistemic Drift Research API",
    description="FastAPI backend for cybernetic research with Granite LLM",
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
app.include_router(analysis.router, prefix="/api/granite", tags=["granite-analysis"])

# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/api/graphql")


@app.get("/")
async def root():
    return {
        "message": "Epistemic Drift Research API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
