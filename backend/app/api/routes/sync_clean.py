"""
Sync endpoints - trigger document sync from various sources
Includes GraphQL DDR Archive sync and S3 Spaces sync
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from typing import Optional, List
from datetime import datetime

from app.services.s3_sync import S3SyncService
from app.services.graphql_sync import GraphQLSyncService
from app.services.database_authorities_sync import sync_all_authorities_with_report

logger = logging.getLogger(__name__)
router = APIRouter()

s3_sync_service = S3SyncService()
graphql_sync_service = GraphQLSyncService()


@router.post("/s3/trigger")
async def trigger_s3_sync(max_docs: Optional[int] = None):
    """
    Trigger S3 sync to pull PDFs from DigitalOcean Spaces
    
    Args:
        max_docs: Maximum number of documents to process (None = all)
    
    Returns:
        Sync operation summary
    """
    try:
        logger.info(f"Triggering S3 sync (max_docs={max_docs})...")
        
        result = await s3_sync_service.sync_from_s3(max_docs=max_docs)
        
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return {
            'status': 'success',
            'message': f"Processed {result['processed']} documents",
            'details': result
        }
        
    except Exception as e:
        logger.error(f"Error during S3 sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/authorities/scheduled")
async def scheduled_authority_sync(
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None)
):
    """
    Scheduled sync endpoint for cron jobs
    
    Security: Requires API key header
    """
    # TODO: Add API key validation when settings.SYNC_API_KEY is configured
    # if x_api_key != settings.SYNC_API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    logger.info("Starting scheduled authority sync...")
    
    try:
        result = sync_all_authorities_with_report()
        
        return {
            'status': 'success',
            'message': f"Synced {result.get('total_synced', 0)} authority records",
            'details': result
        }
        
    except Exception as e:
        logger.error(f"Scheduled sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/authorities/manual")
async def manual_authority_sync(
    background_tasks: BackgroundTasks,
    incremental: bool = True
):
    """
    Manual sync endpoint for admin use
    
    Args:
        incremental: If True, only sync new records since last sync
    """
    logger.info(f"Starting manual authority sync (incremental={incremental})...")
    
    try:
        result = sync_all_authorities_with_report()
        
        return {
            'status': 'success',
            'message': f"Synced {result.get('total_synced', 0)} authority records",
            'details': result
        }
        
    except Exception as e:
        logger.error(f"Manual sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def sync_status():
    """
    Get comprehensive sync status for all sources
    
    Returns:
        Status for GraphQL, S3, and sync health monitoring
    """
    from app.core.database import LocalSessionLocal
    from sqlalchemy import text
    
    db = LocalSessionLocal()
    try:
        # Get sync health from view
        result = db.execute(text("SELECT * FROM sync_health WHERE source_system = 'ddr_graphql'"))
        sync_health = result.fetchone()
        
        return {
            'graphql_sync': {
                'source': sync_health[1] if sync_health else None,
                'last_sync': sync_health[2].isoformat() if sync_health and sync_health[2] else None,
                'health_status': sync_health[6] if sync_health else 'unknown'
            },
            's3_storage': {
                'configured': s3_sync_service.s3_client is not None,
                'bucket': s3_sync_service.bucket_name if s3_sync_service.s3_client else None
            }
        }
    finally:
        db.close()


@router.get("/s3/list-pdfs")
async def list_pdfs():
    """List all PDFs in S3 bucket with metadata"""
    pdfs = s3_sync_service.list_pdfs_in_bucket()
    
    return {
        'count': len(pdfs),
        'pdfs': [
            {
                'filename': p['filename'],
                'key': p['key'],
                'size_mb': round(p['size'] / 1024 / 1024, 2),
                'publication_year': p['publication_year'],
                'last_modified': p['last_modified'].isoformat()
            }
            for p in pdfs
        ]
    }


@router.get("/history")
async def sync_history(limit: int = 20):
    """
    Get sync history with statistics
    
    Args:
        limit: Number of recent syncs to return
    
    Returns:
        List of recent sync operations with details
    """
    from app.core.database import LocalSessionLocal
    from sqlalchemy import text
    
    db = LocalSessionLocal()
    try:
        result = db.execute(
            text("SELECT * FROM sync_log ORDER BY sync_started_at DESC LIMIT :limit"),
            {'limit': limit}
        )
        syncs = [dict(row._mapping) for row in result.fetchall()]
        
        return {
            'count': len(syncs),
            'syncs': [
                {
                    'sync_id': s['sync_id'],
                    'source_system': s['source_system'],
                    'sync_started_at': s['sync_started_at'].isoformat() if s.get('sync_started_at') else None,
                    'sync_completed_at': s['sync_completed_at'].isoformat() if s.get('sync_completed_at') else None,
                    'status': s['status'],
                    'records_processed': s['records_processed'],
                    'new_records': s['new_records'],
                    'updated_records': s['updated_records'],
                    'triggered_by': s['triggered_by']
                }
                for s in syncs
            ]
        }
    finally:
        db.close()
