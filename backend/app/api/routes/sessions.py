from fastapi import APIRouter, Query
from typing import List, Optional
import logging

from app.core.logging import session_logger

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    List recent human-AI collaboration sessions.
    
    Returns logged sessions with full audit trail:
    - User queries
    - Retrieved document chunks
    - Agent responses
    - Timestamps and metadata
    """
    try:
        sessions = session_logger.list_sessions(limit=limit + offset)
        return {
            "total": len(sessions),
            "sessions": sessions[offset:offset + limit]
        }
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {"total": 0, "sessions": []}


@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    """Get detailed information about a specific session"""
    session = session_logger.get_session(session_id)
    
    if not session:
        return {"error": "Session not found"}
    
    return session


@router.get("/{session_id}/evidence-flow")
async def get_evidence_flow(session_id: str):
    """
    Get the evidence flow visualization data for a session.
    
    Returns a graph structure showing:
    - User query node
    - Retrieved document nodes
    - Agent response node
    - Weighted edges based on relevance scores
    """
    session = session_logger.get_session(session_id)
    
    if not session:
        return {"error": "Session not found"}
    
    # Transform session data into D3-compatible graph structure
    nodes = [
        {"id": "query", "label": session["query"][:50] + "...", "group": 1}
    ]
    
    links = []
    
    for idx, chunk in enumerate(session.get("retrieved_chunks", [])):
        chunk_id = f"chunk_{idx}"
        nodes.append({
            "id": chunk_id,
            "label": chunk.get("source", "Unknown"),
            "group": 2
        })
        links.append({
            "source": "query",
            "target": chunk_id,
            "value": chunk.get("relevance_score", 0.5)
        })
    
    nodes.append({
        "id": "response",
        "label": "Agent Response",
        "group": 3
    })
    
    for idx in range(len(session.get("retrieved_chunks", []))):
        links.append({
            "source": f"chunk_{idx}",
            "target": "response",
            "value": session["retrieved_chunks"][idx].get("relevance_score", 0.5)
        })
    
    return {
        "session_id": session_id,
        "nodes": nodes,
        "links": links
    }
