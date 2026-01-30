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
        }
    finally:
        db.close() 2 * * * curl -X POST \\
        -H "X-API-Key: ${SYNC_API_KEY}" \\
        http://localhost:8000/api/v1/sync/authorities/scheduled
    ```
    
    Returns:
        Sync operation started confirmation
    """
    # TODO: Validate API key for production
    # if x_api_key != settings.SYNC_API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    sync_id = graphql_sync_service.start_sync_log(
        sync_type='scheduled',
        triggered_by='cron'
    )
    
    # Run sync in background
    background_tasks.add_task(
        run_graphql_sync,
        sync_id=sync_id,
        incremental=True
    )
    
    return {
        'status': 'sync_started',
        'sync_id': sync_id,
        'type': 'scheduled',
        'message': 'Incremental sync started in background'
    }


@router.post("/authorities/manual")
async def manual_authority_sync(
    background_tasks: BackgroundTasks,
    pids: Optional[List[str]] = None,
    force_refresh: bool = False
):
    """
    Manual authority sync - trigger from UI or API
    
    Allows PhD researchers to sync specific authorities or force refresh all.
    
    Args:
        pids: Specific PIDs to sync (None = all)
        force_refresh: Re-fetch even if unchanged
    
    Returns:
        Sync operation started confirmation
    """
    sync_type = 'full' if force_refresh else 'incremental'
    
    sync_id = graphql_sync_service.start_sync_log(
        sync_type=sync_type,
        triggered_by='manual_api'
    )
    
    # Run sync in background
    background_tasks.add_task(
        run_graphql_sync,
        sync_id=sync_id,
        specific_pids=pids,
        incremental=not force_refresh
    )
    
    return {
        'status': 'sync_started',
        'sync_id': sync_id,
        'type': sync_type,
        'pids': pids,
        'message': f'Sync started for {len(pids) if pids else "all"} authorities'
    }


async def run_graphql_sync(
    sync_id: str,
    specific_pids: Optional[List[str]] = None,
    incremental: bool = True
):
    """
    Background task to run GraphQL sync
    
    Args:
        sync_id: Tracking ID for this sync
        specific_pids: Only sync these PIDs
        incremental: Only fetch changed records
    """
    try:
        records_new = 0
        records_updated = 0
        records_failed = 0
        
        # TODO: Implement actual GraphQL fetch and sync logic
        # For now, this is a placeholder
        logger.info(f"Running sync {sync_id}: incremental={incremental}, pids={specific_pids}")
        
        # Mark as complete
        graphql_sync_service.complete_sync_log(
            sync_id=sync_id,
            records_new=records_new,
            records_updated=records_updated,
            records_failed=records_failed,
            status='completed'
        )
        
    except Exception as e:
        logger.error(f"Sync {sync_id} failed: {e}")
        graphql_sync_service.complete_sync_log(
            sync_id=sync_id,
            status='failed',
            error_log=str(e)
        )


@router.get("/status")
async def sync_status():
    """Get S3 sync service status"""
    pdfs = sync_service.list_pdfs_in_bucket()
    
    return {
        'configured': sync_service.s3_client is not None,
        'bucket': sync_service.s3_client and sync_service.s3_client._endpoint.host,
        'pdfs_in_bucket': len(pdfs),
        'pdfs_with_year': len([p for p in pdfs if p['publication_year']]),
        'year_range': {
            'min': min([p['publication_year'] for p in pdfs if p['publication_year']], default=None),
            'max': max([p['publication_year'] for p in pdfs if p['publication_year']], default=None)
        }
    }


@router.get("/list-pdfs")
async def list_pdfs():
    """List all PDFs in S3 bucket with metadata"""
    pdfs = sync_service.list_pdfs_in_bucket()
    
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
