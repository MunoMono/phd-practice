"""
Provenance API endpoints - XAI and academic attribution
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.services.provenance_service import ProvenanceService

logger = logging.getLogger(__name__)
router = APIRouter()

provenance = ProvenanceService()


class CreateSnapshotRequest(BaseModel):
    name: str
    description: Optional[str] = None


@router.get("/chunk/{chunk_id}/citation")
async def get_chunk_citation(chunk_id: str):
    """
    Get academic citation for a specific chunk
    
    Returns full attribution: PID, title, author, year, page, institution, URL
    """
    try:
        citation = provenance.build_chunk_citation(chunk_id)
        
        if not citation:
            raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found or has no PID")
        
        return citation
        
    except Exception as e:
        logger.error(f"Error building citation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunk/{chunk_id}/provenance")
async def get_chunk_provenance(chunk_id: str):
    """
    Get complete provenance chain for a chunk
    
    Shows: Archive → Document → Chunk → Training Runs → Inferences
    """
    try:
        provenance_chain = provenance.get_chunk_provenance(chunk_id)
        return provenance_chain
        
    except Exception as e:
        logger.error(f"Error getting provenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot/create")
async def create_snapshot(request: CreateSnapshotRequest):
    """
    Create a versioned snapshot of current training corpus
    
    For reproducibility: captures exact state of corpus at a point in time
    """
    try:
        snapshot_id = provenance.create_corpus_snapshot(
            name=request.name,
            description=request.description
        )
        
        return {
            "snapshot_id": snapshot_id,
            "message": f"Corpus snapshot '{request.name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inference/{inference_id}")
async def get_inference_provenance(inference_id: str):
    """
    Get provenance for a specific inference
    
    Shows which training chunks influenced the prediction
    """
    from app.core.database import LocalSessionLocal
    from app.models.document import InferenceLog
    
    db = LocalSessionLocal()
    try:
        inference = db.query(InferenceLog).filter(
            InferenceLog.inference_id == inference_id
        ).first()
        
        if not inference:
            raise HTTPException(status_code=404, detail=f"Inference {inference_id} not found")
        
        return {
            "inference_id": inference.inference_id,
            "query": inference.query,
            "prediction": inference.prediction,
            "model_version": inference.model_version,
            "source_pids": inference.source_pids,
            "source_years": inference.source_years,
            "top_k_chunks": inference.top_k_chunks,
            "created_at": inference.created_at.isoformat()
        }
        
    finally:
        db.close()


@router.get("/training/{run_id}")
async def get_training_run_provenance(run_id: str):
    """
    Get provenance for a training run
    
    Shows which data was used to train which model
    """
    from app.core.database import LocalSessionLocal
    from app.models.document import TrainingRun
    
    db = LocalSessionLocal()
    try:
        run = db.query(TrainingRun).filter(
            TrainingRun.run_id == run_id
        ).first()
        
        if not run:
            raise HTTPException(status_code=404, detail=f"Training run {run_id} not found")
        
        return {
            "run_id": run.run_id,
            "model_name": run.model_name,
            "training_date": run.training_date.isoformat(),
            "total_chunks": run.total_chunks,
            "pid_distribution": run.pid_distribution,
            "temporal_distribution": run.temporal_distribution,
            "corpus_snapshot_id": run.corpus_snapshot_id,
            "hyperparameters": run.hyperparameters,
            "metrics": run.metrics,
            "description": run.description
        }
        
    finally:
        db.close()
