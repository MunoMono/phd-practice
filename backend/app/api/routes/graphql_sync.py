"""
GraphQL sync endpoints - Import authority records with media from DDR Archive
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.services.graphql_sync import GraphQLSyncService

logger = logging.getLogger(__name__)
router = APIRouter()

sync_service = GraphQLSyncService()


class SyncRequest(BaseModel):
    """GraphQL sync request payload"""
    graphql_response: dict


class SyncStats(BaseModel):
    """Statistics from GraphQL sync operation"""
    total_items: int
    training_eligible: int
    synced: int
    skipped: int
    errors: int
    dry_run: bool


class ValidationReport(BaseModel):
    """Validation report comparing GraphQL to database"""
    graphql_pid_count: int
    database_pid_count: int
    needs_sync: list[str]
    needs_sync_count: int
    orphaned: list[str]
    orphaned_count: int
    already_synced: list[str]
    already_synced_count: int


@router.post("/sync/graphql", response_model=SyncStats)
async def sync_from_graphql(
    request: SyncRequest,
    dry_run: bool = True
):
    """
    Bulk sync training corpus from GraphQL response
    
    CRITICAL: Only PID-linked PDF/TIFF assets are synced
    
    Args:
        request: Request with graphql_response data
        dry_run: If True, don't actually insert to database (default: True for safety)
    
    Returns:
        Sync statistics
    """
    try:
        result = sync_service.bulk_sync_from_graphql_response(
            request.graphql_response,
            dry_run=dry_run
        )
        
        return SyncStats(**result)
        
    except Exception as e:
        logger.error(f"GraphQL sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"GraphQL sync failed: {str(e)}"
        )


@router.post("/sync/validate", response_model=ValidationReport)
async def validate_graphql_sync(graphql_response: dict):
    """
    Validate GraphQL response against current database state
    
    Shows which PIDs need to be synced and which are orphaned
    
    Args:
        graphql_response: GraphQL all_media_items response
    
    Returns:
        Validation report
    """
    try:
        report = sync_service.validate_graphql_against_database(graphql_response)
        return ValidationReport(**report)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@router.get("/sync/pids")
async def get_training_corpus_pids():
    """
    Get all PIDs currently in training corpus
    
    Returns list of PID strings from database
    """
    try:
        pids = sync_service.get_training_corpus_pids()
        return {
            "pids": pids,
            "count": len(pids)
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch PIDs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch PIDs: {str(e)}"
        )
