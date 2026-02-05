"""
GraphQL schema for metrics and statistics including epistemic drift analysis
"""
import strawberry
from typing import Optional, List
from sqlalchemy import text
import boto3
from botocore.exceptions import ClientError
import logging

from app.core.database import LocalSessionLocal
from app.core.config import settings
from app.models.document import Document, DocumentChunk, DriftAnalysis
from app.services.drift_analyzer import DriftAnalyzer

logger = logging.getLogger(__name__)
drift_analyzer = DriftAnalyzer()


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
    documents: int
    training_runs: int
    corpus_snapshots: int


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
    tiffs: int
    error: Optional[str] = None


@strawberry.type
class RecentDocument:
    pid: str
    title: str
    created_at: Optional[str]


@strawberry.type
class PidAuthority:
    pid: str
    title: str
    document_count: int
    pdf_count: int  # Total PDFs in archive
    ml_pdf_count: int  # PDFs approved for ML training (use_for_ml=true)
    tiff_count: int
    ml_tiff_count: int  # TIFFs approved for ML training
    total_media_count: int


@strawberry.type
class SystemMetrics:
    local_db: DatabaseStats
    s3_storage: S3Stats
    total_items: int
    pid_count: int
    pid_authorities: List['PidAuthority']


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
                
                result = db.execute(text("SELECT COUNT(*) FROM digital_assets WHERE file_type LIKE 'image/tiff'"))
                tiffs_count = result.scalar()
            except:
                digital_assets_count = 0
                images_count = 0
                pdfs_count = 0
                tiffs_count = 0
            
            # Get new table counts
            try:
                result = db.execute(text("SELECT COUNT(*) FROM documents"))
                documents_count = result.scalar()
            except:
                documents_count = 0
            
            try:
                result = db.execute(text("SELECT COUNT(*) FROM training_runs"))
                training_runs_count = result.scalar()
            except:
                training_runs_count = 0
            
            try:
                result = db.execute(text("SELECT COUNT(*) FROM corpus_snapshots"))
                corpus_snapshots_count = result.scalar()
            except:
                corpus_snapshots_count = 0
            
            # Get PID count (unique PIDs)
            try:
                result = db.execute(text("SELECT COUNT(DISTINCT pid) FROM documents WHERE pid IS NOT NULL"))
                pid_count = result.scalar()
            except:
                pid_count = 0
            
            # Get PID authorities with titles and media counts
            # PERMANENT ML GATE POLICY (Feb 2026):
            # - Only show parent authority records (those with actual media counts > 0)
            # - This filters out individual media item records
            # - Counts are from pdf_count/tiff_count columns (synced via quick_sync_pids.py)
            # - These counts already reflect master-only PDFs with use_for_ml=True
            try:
                result = db.execute(text("""
                    SELECT 
                        pid,
                        MAX(title) as title,
                        COUNT(*) as document_count,
                        MAX(pdf_count) as pdf_count,
                        MAX((doc_metadata->>'ml_pdf_count')::int) as ml_pdf_count,
                        MAX(tiff_count) as tiff_count,
                        MAX((doc_metadata->>'ml_tiff_count')::int) as ml_tiff_count
                    FROM documents 
                    WHERE pid IS NOT NULL
                    AND (pdf_count > 0 OR tiff_count > 0)
                    GROUP BY pid
                    ORDER BY pid
                """))
                pid_authorities = [
                    PidAuthority(
                        pid=row[0],
                        title=row[1] or 'Untitled',
                        document_count=row[2],
                        pdf_count=row[3] or 0,
                        ml_pdf_count=row[4] or 0,
                        tiff_count=row[5] or 0,
                        ml_tiff_count=row[6] or 0,
                        total_media_count=(row[3] or 0) + (row[5] or 0)  # PDFs + TIFFs
                    )
                    for row in result.fetchall()
                ]
            except Exception as e:
                logger.error(f"Error fetching PID authorities: {e}")
                pid_authorities = []
            
            table_counts = TableCounts(
                document_embeddings=counts['document_embeddings'],
                research_sessions=counts['research_sessions'],
                experiments=counts['experiments'],
                digital_assets=digital_assets_count,
                documents=documents_count,
                training_runs=training_runs_count,
                corpus_snapshots=corpus_snapshots_count
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
            pdfs=pdfs_count,
            tiffs=tiffs_count
        )
        
        # Calculate total (database records + digital assets)
        total_items = total_records + digital_assets_count
        
        return SystemMetrics(
            local_db=db_stats,
            s3_storage=s3_stats,
            total_items=total_items,
            pid_count=pid_count,
            pid_authorities=pid_authorities
        )
    
    @strawberry.field
    def recent_documents(
        self,
        days: int = 7
    ) -> List['RecentDocument']:
        """
        Get recently ingested documents with PIDs
        
        Args:
            days: Number of days to look back (default: 7)
        """
        db = LocalSessionLocal()
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            docs = db.query(Document).filter(
                Document.pid.isnot(None),
                Document.created_at >= cutoff_date
            ).order_by(Document.created_at.desc()).all()
            
            return [
                RecentDocument(
                    pid=doc.pid,
                    title=doc.title,
                    created_at=doc.created_at.isoformat() if doc.created_at else None
                )
                for doc in docs
            ]
        finally:
            db.close()
    
    @strawberry.field
    def temporal_documents(
        self,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        only_with_pid: bool = False  # Filter for training corpus only
    ) -> List['TemporalDocument']:
        """
        Query documents by publication year
        
        Args:
            start_year: Filter by minimum publication year
            end_year: Filter by maximum publication year
            only_with_pid: If True, only return PID-linked documents (training corpus)
        """
        db = LocalSessionLocal()
        try:
            query = db.query(Document)
            
            if start_year:
                query = query.filter(Document.publication_year >= start_year)
            if end_year:
                query = query.filter(Document.publication_year <= end_year)
            
            # CRITICAL: Filter for training corpus (PID-linked only)
            if only_with_pid:
                query = query.filter(Document.pid.isnot(None))
            
            docs = query.order_by(Document.publication_year).all()
            
            return [
                TemporalDocument(
                    document_id=doc.document_id,
                    title=doc.title or "",
                    publication_year=doc.publication_year,
                    status=doc.processing_status or "pending",
                    has_diagrams=doc.has_diagrams or 0,
                    pid=doc.pid,  # Expose PID for verification
                    authority_id=doc.authority_id
                )
                for doc in docs
            ]
        except:
            return []
        finally:
            db.close()
    
    @strawberry.field
    def training_corpus_stats(self) -> 'TrainingCorpusStats':
        """
        Get statistics on PID-linked training corpus
        
        Shows data quality: how many documents have PIDs (eligible for training)
        vs orphaned assets (no PID linkage)
        """
        db = LocalSessionLocal()
        try:
            from sqlalchemy import text, func
            
            # Total documents
            total = db.query(func.count(Document.id)).scalar() or 0
            
            # Documents with PID (training eligible)
            with_pid = db.query(func.count(Document.id)).filter(
                Document.pid.isnot(None)
            ).scalar() or 0
            
            # Documents without PID (orphaned)
            without_pid = total - with_pid
            
            # Coverage percentage
            pid_coverage = (with_pid / total * 100) if total > 0 else 0.0
            
            # Breakdown by year
            yearly_stats = db.execute(text("""
                SELECT 
                    publication_year,
                    COUNT(*) as total,
                    COUNT(pid) as with_pid
                FROM documents
                GROUP BY publication_year
                ORDER BY publication_year
            """))
            
            documents_by_year = [
                YearlyDocumentCount(
                    year=row[0],
                    count=row[1],
                    with_pid_count=row[2]
                )
                for row in yearly_stats
            ]
            
            return TrainingCorpusStats(
                total_documents=total,
                total_with_pid=with_pid,
                total_without_pid=without_pid,
                pid_coverage_percent=round(pid_coverage, 2),
                documents_by_year=documents_by_year
            )
        except Exception as e:
            logger.error(f"Error getting training corpus stats: {e}")
            return TrainingCorpusStats(
                total_documents=0,
                total_with_pid=0,
                total_without_pid=0,
                pid_coverage_percent=0.0,
                documents_by_year=[]
            )
        finally:
            db.close()
    
    @strawberry.field
    async def epistemic_drift(
        self,
        start_year: int,
        end_year: int,
        window_size: int = 5
    ) -> 'DriftAnalysisResult':
        """Analyze epistemic drift between time periods"""
        result = await drift_analyzer.analyze_temporal_drift(
            start_year, end_year, window_size
        )
        
        if 'error' in result:
            return DriftAnalysisResult(
                analysis_id="error",
                start_year=start_year,
                end_year=end_year,
                document_count=0,
                drift_score=0.0,
                error=result['error']
            )
        
        return DriftAnalysisResult(
            analysis_id=result['analysis_id'],
            start_year=result['start_year'],
            end_year=result['end_year'],
            document_count=result['document_count'],
            drift_score=result['drift_score'],
            error=None
        )


@strawberry.type
class TemporalDocument:
    document_id: str
    title: str
    publication_year: int
    status: str
    has_diagrams: int
    pid: Optional[str] = None  # Authority linkage
    authority_id: Optional[str] = None


@strawberry.type
class TrainingCorpusStats:
    """Statistics for PID-linked training corpus"""
    total_documents: int
    total_with_pid: int
    total_without_pid: int  # Orphaned assets (not eligible for training)
    pid_coverage_percent: float
    documents_by_year: List['YearlyDocumentCount']


@strawberry.type
class YearlyDocumentCount:
    year: int
    count: int
    with_pid_count: int


@strawberry.type
class DriftAnalysisResult:
    analysis_id: str
    start_year: int
    end_year: int
    document_count: int
    drift_score: float
    error: Optional[str]


schema = strawberry.Schema(query=Query)
