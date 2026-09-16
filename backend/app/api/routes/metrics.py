"""
Metrics API endpoints for dashboard statistics
NOTE: This REST endpoint is deprecated. Use the GraphQL endpoint at /graphql instead.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any
import logging

from app.core.database import get_local_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_system_stats(db: Session = Depends(get_local_db)) -> Dict[str, Any]:
    """
    DEPRECATED: Use GraphQL endpoint at /graphql instead
    Legacy REST endpoint for basic statistics
    """
    try:
        stats = {}
        
        # Get local database table counts
        tables = ['document_embeddings', 'research_sessions', 'experiments']
        total_records = 0
        table_counts = {}
        
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
            except:
                count = 0
            table_counts[table] = count
            total_records += count
        
        # Get digital assets
        try:
            result = db.execute(text("SELECT COUNT(*) FROM digital_assets"))
            digital_assets = result.scalar()
        except:
            digital_assets = 0
        
        stats['total_db_records'] = total_records
        stats['table_counts'] = table_counts
        stats['digital_assets'] = digital_assets
        stats['total_items'] = total_records + digital_assets
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {"error": str(e)}


@router.get("/health")
async def health_check(db: Session = Depends(get_local_db)) -> Dict[str, str]:
    """Simple health check endpoint"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
