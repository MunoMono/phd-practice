"""
S3 Spaces sync service - pulls PDFs from DigitalOcean Spaces
Automatically processes documents for epistemic drift analysis
"""
import logging
import re
import tempfile
import os
import shutil
from typing import List, Dict, Optional
import boto3
from botocore.exceptions import ClientError
import uuid
from datetime import datetime
from sqlalchemy import text

from app.core.config import settings
from app.core.database import LocalSessionLocal
from app.models.document import Document, DocumentChunk
from app.services.docling_processor import DoclingProcessor
from app.services.authority_service import AuthorityService

logger = logging.getLogger(__name__)


class S3SyncService:
    """Sync documents from DigitalOcean Spaces to local database"""
    
    def __init__(self):
        self.s3_client = None
        self.docling = DoclingProcessor()
        self.authorities = AuthorityService()  # For PID validation and metadata enrichment
        self.min_free_gb = float(os.getenv("INGEST_MIN_FREE_GB", "10"))
        self._init_s3_client()
        self._valid_pids_cache = None  # Cache of PIDs from Postgres authorities

    def _get_free_disk_gb(self, path: str = "/") -> float:
        """Return free disk space in GB for resource safety checks."""
        usage = shutil.disk_usage(path)
        return usage.free / (1024 ** 3)

    def _upsert_ingestion_state(
        self,
        db,
        source_key: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Store resumable ingestion state per source asset."""
        db.execute(
            text(
                """
                INSERT INTO ingestion_state (source_key, status, last_error, updated_at, retries)
                VALUES (
                    :source_key,
                    :status,
                    :error,
                    NOW(),
                    CASE WHEN :status = 'failed' THEN 1 ELSE 0 END
                )
                ON CONFLICT (source_key)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    last_error = EXCLUDED.last_error,
                    updated_at = NOW(),
                    retries = CASE
                        WHEN EXCLUDED.status = 'failed' THEN ingestion_state.retries + 1
                        ELSE ingestion_state.retries
                    END
                """
            ),
            {"source_key": source_key, "status": status, "error": error},
        )
    
    def _init_s3_client(self):
        """Initialize S3 client for DigitalOcean Spaces"""
        if not settings.S3_ENDPOINT or not settings.S3_ACCESS_KEY:
            logger.warning("S3 credentials not configured - sync disabled")
            return
        
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name='nyc3'
            )
            logger.info("S3 client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
    
    def extract_year_from_filename(self, filename: str) -> Optional[int]:
        """
        Extract publication year from filename
        Looks for patterns like: 1965, 1970, etc. (1965-1985)
        """
        # Try to find 4-digit year between 1965-1985
        matches = re.findall(r'(19[6-8][0-9])', filename)
        
        for match in matches:
            year = int(match)
            if 1965 <= year <= 1985:
                return year
        
        return None
    
    def extract_pid_from_s3_key(self, s3_key: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """
        Extract PID from S3 object key or metadata
        
        Strategy:
        1. Check S3 object metadata for 'pid' tag
        2. Parse PID from filename pattern (e.g., pid_12345_document.pdf)
        3. Return None if no PID found (will be filtered out)
        
        Args:
            s3_key: S3 object key
            metadata: S3 object metadata dict
        
        Returns:
            PID string or None
        """
        # Check metadata first (most reliable)
        if metadata and 'pid' in metadata:
            return metadata['pid']
        
        # Parse from filename pattern: pid_XXXXX or PID-XXXXX
        filename = os.path.basename(s3_key)
        pid_patterns = [
            r'pid[_-]([a-zA-Z0-9]+)',  # pid_12345 or pid-12345
            r'PID[_-]([a-zA-Z0-9]+)',  # PID_12345 or PID-12345
            r'^([a-zA-Z0-9]+)_',       # 12345_document.pdf
        ]
        
        for pattern in pid_patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
        
        return None
    
    def get_valid_pids_from_postgres(self) -> set:
        """
        Query Postgres for all valid authority PIDs
        
        This creates the allowlist - only assets with these PIDs will be synced
        
        Returns:
            Set of valid PID strings
        """
        if self._valid_pids_cache is not None:
            return self._valid_pids_cache
        
        db = LocalSessionLocal()
        try:
            # Get all PIDs from documents table (already ingested)
            from sqlalchemy import text
            result = db.execute(text(
                "SELECT DISTINCT pid FROM documents WHERE pid IS NOT NULL"
            ))
            valid_pids = {row[0] for row in result}
            
            # TODO: Optionally query DDR Archive GraphQL for authority PIDs
            # For now, we trust what's already in our database
            
            self._valid_pids_cache = valid_pids
            logger.info(f"Loaded {len(valid_pids)} valid PIDs from Postgres")
            return valid_pids
            
        except Exception as e:
            logger.error(f"Error loading valid PIDs: {e}")
            return set()
        finally:
            db.close()
    
    def list_training_assets_in_bucket(self, enforce_pid_filter: bool = True) -> List[Dict]:
        """
        List all PID-linked PDF/TIFF files in S3 bucket (training corpus only)
        
        CRITICAL: Only returns assets with valid PIDs from Postgres authorities
        
        Args:
            enforce_pid_filter: If True, only return assets with valid PIDs (default)
        
        Returns:
            List of asset metadata dicts with PID linkage
        """
        if not self.s3_client:
            return []
        
        # Get allowlist of valid PIDs
        valid_pids = self.get_valid_pids_from_postgres() if enforce_pid_filter else set()
        
        try:
            assets = []
            filtered_count = 0
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.S3_BUCKET)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    
                    # Filter for PDFs and TIFFs only (training-eligible formats)
                    allowed_extensions = ('.pdf', '.tiff', '.tif')
                    if not key.lower().endswith(allowed_extensions):
                        continue
                    
                    # Extract PID from S3 key/metadata
                    # TODO: Fetch metadata for more reliable PID extraction
                    pid = self.extract_pid_from_s3_key(key)
                    
                    # ALLOWLIST FILTER: Skip if no PID or PID not in Postgres
                    if enforce_pid_filter:
                        if not pid:
                            filtered_count += 1
                            logger.debug(f"Skipping {key} - no PID found")
                            continue
                        
                        if pid not in valid_pids:
                            filtered_count += 1
                            logger.debug(f"Skipping {key} - PID {pid} not in authorities")
                            continue
                    
                    year = self.extract_year_from_filename(key)
                    
                    assets.append({
                        'key': key,
                        'filename': os.path.basename(key),
                        'pid': pid,  # CRITICAL: PID linkage
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'publication_year': year
                    })
            
            logger.info(
                f"Found {len(assets)} PID-linked training assets in S3 bucket "
                f"({filtered_count} filtered out - no valid PID)"
            )
            return assets
            
        except ClientError as e:
            logger.error(f"Error listing S3 bucket: {e}")
            return []
    
    def download_pdf_from_s3(self, s3_key: str) -> Optional[str]:
        """Download PDF from S3 to temporary file"""
        if not self.s3_client:
            return None
        
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.pdf',
                prefix='s3_sync_'
            )
            
            # Download from S3
            self.s3_client.download_fileobj(
                settings.S3_BUCKET,
                s3_key,
                temp_file
            )
            
            temp_file.close()
            logger.info(f"Downloaded {s3_key} to {temp_file.name}")
            return temp_file.name
            
        except ClientError as e:
            logger.error(f"Error downloading {s3_key} from S3: {e}")
            return None
    
    async def process_pdf(
        self,
        pdf_info: Dict,
        temp_path: str
    ) -> Optional[str]:
        """
        Process a PDF/TIFF: extract text and store chunks in DB
        
        CRITICAL: Requires PID in pdf_info - only authority-linked assets are processed
        
        Returns:
            document_id if successful, None otherwise
        """
        db = LocalSessionLocal()
        document_id = None
        
        try:
            # CRITICAL: Validate PID presence
            if 'pid' not in pdf_info or not pdf_info['pid']:
                logger.error(f"Cannot process {pdf_info['key']} - no PID (not in training corpus)")
                return None
            
            # Check if already processed
            existing = db.query(Document).filter(
                Document.s3_key == pdf_info['key']
            ).first()
            
            if existing:
                logger.info(f"Document {pdf_info['key']} already processed (PID: {existing.pid})")
                self._upsert_ingestion_state(db, pdf_info['key'], 'completed')
                db.commit()
                return existing.document_id

            self._upsert_ingestion_state(db, pdf_info['key'], 'processing')
            db.commit()
            
            # Generate document ID
            document_id = f"doc_{uuid.uuid4().hex[:12]}"
            
            # Determine file type
            if pdf_info['key'].lower().endswith('.pdf'):
                file_type = 'application/pdf'
            elif pdf_info['key'].lower().endswith(('.tiff', '.tif')):
                file_type = 'image/tiff'
            else:
                file_type = 'application/octet-stream'
            
            # Create document record with PID
            doc = Document(
                document_id=document_id,
                pid=pdf_info['pid'],  # CRITICAL: Authority linkage
                title=pdf_info['filename'],
                publication_year=pdf_info.get('publication_year') or 1970,  # Default mid-period
                filename=pdf_info['filename'],
                file_type=file_type,
                s3_key=pdf_info['key'],
                file_size_bytes=pdf_info['size'],
                processing_status='processing'
            )
            
            db.add(doc)
            db.commit()
            
            # Process with Docling
            logger.info(f"Processing {pdf_info['filename']} with Docling...")
            result = await self.docling.process_pdf(temp_path)
            
            if result['status'] == 'failed':
                doc.processing_status = 'failed'
                doc.processing_error = result.get('error')
                self._upsert_ingestion_state(db, pdf_info['key'], 'failed', result.get('error'))
                db.commit()
                return None
            
            # Update document with extracted text
            doc.extracted_text = result.get('text', '')
            doc.has_diagrams = len(result.get('diagrams', []))
            
            # Chunk text for lightweight full-text retrieval
            chunks_text = self.docling.chunk_text(doc.extracted_text, chunk_size=800, overlap=120)
            
            logger.info(f"Generated {len(chunks_text)} chunks from {pdf_info['filename']}")

            # Store chunks only (FTS retrieval path)
            for idx, chunk_text in enumerate(chunks_text):
                
                chunk_id = f"{document_id}_chunk_{idx}"
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_text=chunk_text,
                    chunk_index=idx,
                    chunk_type='paragraph',
                    publication_year=doc.publication_year,
                    embedding_vector=None,
                    embedding_model=None,
                )
                
                db.add(chunk)
            
            # Mark as completed
            doc.processing_status = 'completed'
            doc.processed_at = datetime.utcnow()
            self._upsert_ingestion_state(db, pdf_info['key'], 'completed')
            
            db.commit()
            logger.info(f"Successfully processed {pdf_info['filename']}")
            
            return document_id
            
        except Exception as e:
            logger.error(f"Error processing {pdf_info.get('filename', 'unknown')}: {e}")
            if document_id:
                doc = db.query(Document).filter(
                    Document.document_id == document_id
                ).first()
                if doc:
                    doc.processing_status = 'failed'
                    doc.processing_error = str(e)
            if 'key' in pdf_info:
                self._upsert_ingestion_state(db, pdf_info['key'], 'failed', str(e))
            db.commit()
            return None
            
        finally:
            db.close()
    
    async def sync_from_s3(self, max_docs: Optional[int] = None) -> Dict:
        """
        Sync all PDFs from S3 bucket
        
        Args:
            max_docs: Maximum number of documents to process (None = all)
        
        Returns:
            Summary of sync operation
        """
        if not self.s3_client:
            return {
                'error': 'S3 not configured',
                'processed': 0,
                'failed': 0,
                'skipped': 0
            }
        
        pdfs = self.list_training_assets_in_bucket(enforce_pid_filter=True)
        
        if not pdfs:
            return {
                'message': 'No PDFs found in bucket',
                'processed': 0,
                'failed': 0,
                'skipped': 0
            }
        
        # Filter by year if possible
        pdfs_with_year = [p for p in pdfs if p['publication_year']]
        pdfs_no_year = [p for p in pdfs if not p['publication_year']]
        
        logger.info(f"PDFs with year: {len(pdfs_with_year)}, without year: {len(pdfs_no_year)}")
        
        # Limit number of documents
        if max_docs:
            pdfs = pdfs[:max_docs]
        
        processed = 0
        failed = 0
        skipped = 0
        
        for pdf_info in pdfs:
            try:
                free_gb = self._get_free_disk_gb("/")
                if free_gb < self.min_free_gb:
                    logger.error(
                        "Stopping ingestion due to low disk space: %.2fGB free < %.2fGB threshold",
                        free_gb,
                        self.min_free_gb,
                    )
                    break

                # Download PDF
                temp_path = self.download_pdf_from_s3(pdf_info['key'])
                
                if not temp_path:
                    db = LocalSessionLocal()
                    try:
                        self._upsert_ingestion_state(
                            db,
                            pdf_info['key'],
                            'failed',
                            'Failed to download from S3',
                        )
                        db.commit()
                    finally:
                        db.close()
                    failed += 1
                    continue
                
                # Process PDF
                doc_id = await self.process_pdf(pdf_info, temp_path)
                
                # Clean up temp file
                os.unlink(temp_path)
                
                if doc_id:
                    processed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error syncing {pdf_info['key']}: {e}")
                failed += 1
        
        return {
            'total_pdfs': len(pdfs),
            'processed': processed,
            'failed': failed,
            'skipped': skipped,
            'pdfs_with_year': len(pdfs_with_year),
            'pdfs_without_year': len(pdfs_no_year)
        }
