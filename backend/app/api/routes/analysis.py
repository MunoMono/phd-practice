"""
API route for Granite LLM analysis
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.services.granite_service import get_granite_service
# from app.services.embedding_service import search_similar_chunks  # TODO: implement when embedding service ready

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request model for epistemic drift analysis"""
    query: str = Field(..., description="Research question or analytical query")
    num_context_chunks: int = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")
    max_tokens: Optional[int] = Field(None, ge=50, le=2048, description="Maximum tokens to generate")
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


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_query(request: AnalysisRequest):
    """
    Perform epistemic drift analysis on a research query using Granite LLM.
    
    This endpoint:
    1. Retrieves relevant document chunks using semantic search
    2. Constructs a prompt with the chunks as context
    3. Generates analysis using Granite model
    4. Returns analysis with full provenance (citations to sources)
    
    Args:
        request: Analysis request with query and parameters
        
    Returns:
        Analysis results with citations and metadata
    """
    try:
        granite = get_granite_service()
        
        if not granite.model:
            raise HTTPException(
                status_code=503,
                detail="Granite model not loaded. Please wait for initialization or check logs."
            )
        
        # TODO: Implement actual semantic search when embedding service is ready
        # For now, return mock context chunks
        logger.info(f"Retrieving {request.num_context_chunks} context chunks for query...")
        
        # Mock context chunks (replace with actual retrieval)
        context_chunks = [
            {
                "id": 1,
                "text": "Design methods in the 1960s focused on systematic approaches to problem-solving, emphasizing rationality and scientific rigor.",
                "citation": "Jones, J.C. (1970). Design Methods. John Wiley & Sons, p. 47."
            },
            {
                "id": 2,
                "text": "By the mid-1970s, there was a shift towards participatory design and user-centered approaches, challenging earlier technocratic assumptions.",
                "citation": "Alexander, C. (1977). A Pattern Language. Oxford University Press, p. 203."
            }
        ]
        
        # Generate analysis
        logger.info("Generating Granite analysis...")
        result = granite.generate_analysis(
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


@router.get("/health")
async def health_check():
    """
    Health check endpoint for Granite service.
    
    Returns:
        Service status
    """
    granite = get_granite_service()
    return {
        "status": "healthy" if granite.model else "initializing",
        "model_loaded": granite.model is not None,
        "timestamp": datetime.now().isoformat()
    }
