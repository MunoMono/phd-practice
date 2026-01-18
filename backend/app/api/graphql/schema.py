"""
GraphQL schema for metrics and statistics
"""
import strawberry
from typing import Optional
from sqlalchemy import text
import boto3
from botocore.exceptions import ClientError
import logging

from app.core.database import LocalSessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_s3_stats() -> 'S3Stats':
    """Query Digital Ocean Spaces for asset counts"""
    try:
        if not settings.S3_ENDPOINT or not settings.S3_ACCESS_KEY:
            return S3Stats(
                total_assets=0,
                total_size_bytes=0,
                total_size_mb=0.0,
                configured=False
            )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name='nyc3'
        )
        
        # Count objects in bucket
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=settings.S3_BUCKET)
        
        total_assets = 0
        total_size = 0
        
        for page in pages:
            if 'Contents' in page:
                total_assets += len(page['Contents'])
                total_size += sum(obj['Size'] for obj in page['Contents'])
        
        return S3Stats(
            total_assets=total_assets,
            total_size_bytes=total_size,
            total_size_mb=round(total_size / (1024 * 1024), 2),
            configured=True
        )
        
    except ClientError as e:
        logger.error(f"S3 error: {e}")
        return S3Stats(
            total_assets=0,
            total_size_bytes=0,
            total_size_mb=0.0,
            configured=True,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected S3 error: {e}")
        return S3Stats(
            total_assets=0,
            total_size_bytes=0,
            total_size_mb=0.0,
            configured=False,
            error=str(e)
        )


@strawberry.type
class TableCounts:
    document_embeddings: int
    research_sessions: int
    experiments: int
    digital_assets: int


@strawberry.type
class DatabaseStats:
    total: int
    table_counts: TableCounts


@strawberry.type
class S3Stats:
    total_assets: int
    total_size_bytes: int
    total_size_mb: float
    configured: bool
    images: int
    pdfs: int
    error: Optional[str] = None


@strawberry.type
class SystemMetrics:
    local_db: DatabaseStats
    s3_storage: S3Stats
    total_items: int


@strawberry.type
class Query:
    @strawberry.field
    def system_metrics(self) -> SystemMetrics:
        """Get complete system metrics including database and S3 storage"""
        
        # Get database counts
        db = LocalSessionLocal()
        try:
            # Core database tables (not counting digital_assets which are file references)
            tables = ['document_embeddings', 'research_sessions', 'experiments']
            counts = {}
            total_records = 0
            
            for table in tables:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                except:
                    count = 0
                counts[table] = count
                total_records += count
            
            # Get digital assets count separately
            try:
                result = db.execute(text("SELECT COUNT(*) FROM digital_assets"))
                digital_assets_count = result.scalar()
                
                # Get breakdown by type
                result = db.execute(text("SELECT COUNT(*) FROM digital_assets WHERE file_type LIKE 'image/%'"))
                images_count = result.scalar()
                
                result = db.execute(text("SELECT COUNT(*) FROM digital_assets WHERE file_type = 'application/pdf'"))
                pdfs_count = result.scalar()
            except:
                digital_assets_count = 0
                images_count = 0
                pdfs_count = 0
            
            table_counts = TableCounts(
                document_embeddings=counts['document_embeddings'],
                research_sessions=counts['research_sessions'],
                experiments=counts['experiments'],
                digital_assets=digital_assets_count
            )
            
            db_stats = DatabaseStats(
                total=total_records,
                table_counts=table_counts
            )
        finally:
            db.close()
        
        # Get S3 stats (currently not configured, so using database digital_assets count)
        s3_stats = S3Stats(
            total_assets=digital_assets_count,
            total_size_bytes=0,
            total_size_mb=0.0,
            configured=False,
            images=images_count,
            pdfs=pdfs_count
        )
        
        # Calculate total (database records + digital assets)
        total_items = total_records + digital_assets_count
        
        return SystemMetrics(
            local_db=db_stats,
            s3_storage=s3_stats,
            total_items=total_items
        )


schema = strawberry.Schema(query=Query)
