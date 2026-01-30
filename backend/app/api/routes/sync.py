"""
Sync endpoints - trigger document sync from various sources
Includes GraphQL DDR Archive sync and S3 Spaces sync
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, Depends
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.s3_sync import S3SyncService
from app.services.graphql_sync import GraphQLSyncService
from app.services.pid_media_count import PIDMediaCountService
from app.core.database import get_local_db

logger = logging.getLogger(__name__)
router = APIRouter()

s3_sync_service = S3SyncService()
graphql_sync_service = GraphQLSyncService()
pid_media_service = PIDMediaCountService()


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
    Triggered by: Daily cron job at 2 AM
    """
    # TODO: Add API key validation when settings.SYNC_API_KEY is configured
    # if x_api_key != settings.SYNC_API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    logger.info("Starting scheduled authority sync...")
    
    try:
        result = await graphql_sync_service.sync_all_authorities(
            incremental=True,
            triggered_by='cron'
        )
        
        return {
            'status': 'success',
            'message': f"Synced {result.get('new_authorities', 0)} new authorities",
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
    
    Returns:
        Sync operation summary
    """
    logger.info(f"Starting manual authority sync (incremental={incremental})...")
    
    try:
        result = await graphql_sync_service.sync_all_authorities(
            incremental=incremental,
            triggered_by='manual'
        )
        
        return {
            'status': 'success',
            'message': f"Synced {result.get('new_authorities', 0)} authorities",
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
    """
    List all PDFs in S3 bucket with metadata
    
    Returns:
        List of PDFs with filenames, sizes, publication years
    """
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
        syncs = []
        for row in result.fetchall():
            syncs.append({
                'sync_id': row[0],
                'source_system': row[1],
                'sync_started_at': row[2].isoformat() if row[2] else None,
                'sync_completed_at': row[3].isoformat() if row[3] else None,
                'status': row[4],
                'records_processed': row[5],
                'records_added': row[6],
                'records_updated': row[7],
                'records_failed': row[8],
                'triggered_by': row[9],
                'error_log': row[10]
            })
        
        return {
            'count': len(syncs),
            'syncs': syncs
        }
    finally:
        db.close()


@router.post("/media-counts")
async def sync_media_counts():
    """
    Query DDR Archive GraphQL API for media asset counts (PDFs + TIFFs)
    attached to each PID authority. This provides provenance tracking for
    what Docling will ingest.
    
    Returns:
        Summary of media counts updated
    """
    try:
        logger.info("Syncing media counts for all PIDs...")
        
        # Use standalone session - let the service create its own
        stats = pid_media_service.sync_all_pid_media_counts(db=None)
        
        if 'error' in stats:
            raise HTTPException(status_code=500, detail=stats['error'])
        
        return {
            'status': 'success',
            'message': f"Updated media counts for {stats['pids_processed']} PIDs",
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Error syncing media counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/media-counts/{pid}")
async def get_media_count_for_pid(pid: str):
    """
    Get media asset counts for a specific PID
    
    Args:
        pid: The PID to query (e.g., "124881079617")
    
    Returns:
        Dict with pdf_count, tiff_count, total_count
    """
    try:
        counts = pid_media_service.get_media_counts_for_pid(pid)
        
        return {
            'pid': pid,
            'pdf_count': counts['pdf_count'],
            'tiff_count': counts['tiff_count'],
            'total_media_count': counts['total_count']
        }
        
    except Exception as e:
        logger.error(f"Error getting media count for PID {pid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
