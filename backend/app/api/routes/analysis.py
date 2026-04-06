"""
API route for Granite LLM analysis
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from sqlalchemy import text

from app.services.granite_service import get_granite_service
from app.core.database import LocalSessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request model for epistemic drift analysis"""
    query: str = Field(..., description="Research question or analytical query")
    num_context_chunks: int = Field(12, ge=1, le=20, description="Number of context chunks to retrieve")
    max_tokens: Optional[int] = Field(None, ge=50, le=512, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")


class AnalysisResponse(BaseModel):
    """Response model for analysis results"""
    analysis: str
    query: str
    num_context_chunks: int
    inference_time_seconds: float
    model: str
    timestamp: str
    context_chunks: List[Dict[str, Any]]


class ModelInfoResponse(BaseModel):
    """Response model for model information"""
    model_name: str
    device: str
    loaded: bool
    max_tokens: int
    temperature: float
    quantized: str


class ModelLoadResponse(BaseModel):
    loaded: bool
    model_name: str
    device: str
    message: str


RELATED_TERMS = [
    "design",
    "research",
    "methodology",
    "systems",
    "collaboration",
]


def build_expanded_query(query: str) -> str:
    lower_query = query.lower()
    additions = [term for term in RELATED_TERMS if term not in lower_query]
    if not additions:
        return query
    return f"{query} OR {' OR '.join(additions)}"


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_query(request: AnalysisRequest):
    """
    Perform epistemic drift analysis on a research query using Granite LLM.
    
    This endpoint:
    1. Retrieves relevant chunks using PostgreSQL full-text search
    2. Constructs a prompt with citations
    3. Generates analysis using Granite model
    4. Returns analysis with provenance metadata
    
    Args:
        request: Analysis request with query and parameters
        
    Returns:
        Analysis results with citations and metadata
    """
    try:
        granite = get_granite_service()

        status_info = granite.get_load_status()
        if status_info.get("model_status") != "ready":
            raise HTTPException(
                status_code=503,
                detail=f"Granite runtime not ready (status={status_info.get('model_status')}). Call /api/granite/load-model first.",
            )
        
        expanded_query = build_expanded_query(request.query)
        logger.info(
            "Retrieving up to %s FTS context chunks (expanded query terms applied=%s)...",
            request.num_context_chunks,
            expanded_query != request.query,
        )
        context_chunks: List[Dict[str, Any]] = []
        db = LocalSessionLocal()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                        chunk_id,
                        document_id,
                        chunk_text,
                        source_page,
                        ts_rank(search_tsv, websearch_to_tsquery('english', :query)) AS rank
                    FROM document_chunks
                    WHERE search_tsv @@ websearch_to_tsquery('english', :query)
                    ORDER BY rank DESC
                    LIMIT :limit
                    """
                ),
                {"query": expanded_query, "limit": request.num_context_chunks},
            ).fetchall()

            context_chunks = [
                {
                    "id": row.chunk_id,
                    "text": row.chunk_text,
                    "citation": f"{row.document_id}, p.{row.source_page if row.source_page is not None else '?'}",
                }
                for row in rows
            ]
        finally:
            db.close()

        if not context_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant context chunks found for the query. Try broader terms.",
            )
        
        # Generate analysis
        logger.info("Generating Granite analysis...")
        result = await granite.generate_analysis(
            query=request.query,
            context_chunks=context_chunks,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        # Add context chunks to response
        result["context_chunks"] = context_chunks
        
        logger.info(f"✓ Analysis complete: {len(result['analysis'])} characters")
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info():
    """
    Get information about the loaded Granite model.
    
    Returns:
        Model metadata including name, device, and configuration
    """
    granite = get_granite_service()
    return granite.get_model_info()


@router.post("/load-model", response_model=dict)
async def load_model():
    """
    Run synchronous model loading for explicit debugging.

    This call is intentionally synchronous so logs show the exact failure/hang point.
    """
    granite = get_granite_service()

    if granite.model is not None and granite.tokenizer is not None:
        return {
            "loaded": True,
            "model_name": granite.model_name,
            "device": granite.device,
            "message": "Model already loaded",
        }

    try:
        success = granite.load_model()
        if not success:
            return {
                "loaded": False,
                "model_name": granite.model_name,
                "device": granite.device,
                "message": f"Model load failed: {granite.get_load_status().get('last_error')}",
            }

        return {
            "loaded": True,
            "model_name": granite.model_name,
            "device": granite.device,
            "message": "Model loaded successfully",
        }
    except Exception:
        logger.exception("Unhandled exception while loading model synchronously")
        raise HTTPException(status_code=500, detail="Unhandled error in /load-model")


@router.get("/load-status")
async def get_load_status():
    """
    Get current model load status without blocking.
    
    Use this endpoint to poll for model loading progress.
    
    Returns:
        model_status: "not_loaded", "loading", "ready", "error"
        model_ready: bool (true if model_status == "ready")
        last_error: error message if status is "error"
        memory_usage_mb: current process memory usage
    """
    granite = get_granite_service()
    return granite.get_load_status()


@router.post("/unload-model")
async def unload_model():
    """
    Unload Granite model to free memory (optional emergency use only).
    
    This is a destructive operation. After calling, you must call /load-model again.
    
    Returns:
        status: "unloaded"
        memory_usage_mb: current process memory usage after unload
    """
    granite = get_granite_service()
    granite.unload_model()
    logger.info("Granite runtime status reset to not_loaded")
    
    return {
        "status": "unloaded",
        "memory_usage_mb": granite.get_load_status()["memory_usage_mb"]
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint for Granite service.
    
    Returns:
        status: "healthy" (if model ready) or "initializing" (if loading/not loaded)
        model_loaded: bool
        model_status: current loading status
        memory_usage_mb: process memory usage
        last_error: error message if any
        timestamp: ISO timestamp
    """
    granite = get_granite_service()
    status_info = granite.get_load_status()
    
    # Service is healthy if model is ready, otherwise still initializing
    is_healthy = status_info["model_ready"]
    
    return {
        "status": "healthy" if is_healthy else "initializing",
        "model_loaded": is_healthy,
        "model_status": status_info["model_status"],
        "current_memory_usage": status_info["memory_usage_mb"],
        "memory_usage_mb": status_info["memory_usage_mb"],
        "last_error": status_info["last_error"],
        "timestamp": datetime.now().isoformat()
    }
