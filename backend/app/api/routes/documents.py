"""
Document upload and processing endpoints
Handles PDF uploads with temporal metadata for testamentary traces analysis
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import uuid
from datetime import datetime
from sqlalchemy import and_, or_

from app.core.ddr_temporal_scope import DDR_END_DATE, DDR_START_DATE, is_within_ddr_scope, parse_publication_date
from app.services.docling_processor import DoclingProcessor
from app.services.embedding_service import EmbeddingService
from app.core.database import LocalSessionLocal
from app.models.document import Document, DocumentChunk
from app.services.document_source_service import build_document_annotations_payload, build_document_detail_payload, build_document_list_payload, select_source_documents
from app.services.source_metadata_sync import SourceMetadataSyncService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
docling_processor = DoclingProcessor()
embedding_service = EmbeddingService()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    pid: str = Form(...),  # REQUIRED: Postgres authority PID
    title: Optional[str] = Form(None),
    publication_year: int = Form(...),
    publication_date: Optional[str] = Form(None),
    authority_id: Optional[str] = Form(None),  # DDR Archive authority ID
    metadata: Optional[str] = Form("{}")
):
    """
    Upload PDF/TIFF document for testamentary traces analysis

    CRITICAL: Only PID-linked assets are eligible for training corpus

    Args:
        file: PDF or TIFF file upload

    Returns:
        Upload receipt with queued processing status
    """
    try:
        try:
            parsed_publication_date = parse_publication_date(publication_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Publication date must use ISO format YYYY-MM-DD") from error

        if not is_within_ddr_scope(publication_year, parsed_publication_date):
            raise HTTPException(
                status_code=400,
                detail=f"DDR research data must fall between {DDR_START_DATE.isoformat()} and {DDR_END_DATE.isoformat()}; 1985 records require a full publication date."
            )
        
        # Validate file type (PDF or TIFF only)
        allowed_extensions = ['.pdf', '.tiff', '.tif']
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and TIFF files are supported for training corpus"
            )
        
        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Save file temporarily
        import tempfile
        import os
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Create database record
        db = LocalSessionLocal()
        try:
            # Determine file type
            if file.filename.lower().endswith('.pdf'):
                file_type = 'application/pdf'
            elif file.filename.lower().endswith(('.tiff', '.tif')):
                file_type = 'image/tiff'
            else:
                file_type = 'application/octet-stream'
            
            doc = Document(
                document_id=document_id,
                pid=pid.strip(),  # CRITICAL: Authority linkage
                authority_id=authority_id,
                title=title or file.filename,
                publication_year=publication_year,
                publication_date=datetime.combine(parsed_publication_date, datetime.min.time()) if parsed_publication_date else None,
                filename=file.filename,
                file_type=file_type,
                file_size_bytes=len(content),
                processing_status='pending'
            )
            
            db.add(doc)
            db.commit()
            db.refresh(doc)
            
            # Process with Docling (async in background)
            logger.info(f"Processing document {document_id} with Docling...")
            
            # For now, return immediately - implement background processing later
            return {
                "document_id": document_id,
                "filename": file.filename,
                "publication_year": publication_year,
                "status": "pending",
                "message": "Document uploaded successfully. Processing started."
            }
            
        finally:
            db.close()
            # Clean up temp file
            os.unlink(temp_file.name)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get document details"""
    db = LocalSessionLocal()
    try:
        doc = db.query(Document).filter(
            Document.document_id == document_id
        ).first()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return build_document_detail_payload(doc)
    finally:
        db.close()


@router.post("/{document_id}/sync-metadata")
async def sync_document_metadata(document_id: str):
    """Refresh one document's persisted DDR metadata without re-ingesting it."""
    try:
        return SourceMetadataSyncService().sync_archive_metadata(document_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("")
@router.get("/")
async def list_documents(
    year: Optional[int] = None,
    status: Optional[str] = None
):
    """List all documents with optional filters"""
    db = LocalSessionLocal()
    try:
        query = db.query(Document).filter(
            or_(
                Document.publication_year.between(1965, 1984),
                and_(
                    Document.publication_year == 1985,
                    Document.publication_date >= datetime(1985, 1, 1),
                    Document.publication_date < datetime(1985, 8, 1),
                ),
            )
        )
        
        if year:
            query = query.filter(Document.publication_year == year)
        if status:
            query = query.filter(Document.processing_status == status)
        
        docs = query.order_by(Document.publication_year).all()
        docs = select_source_documents(docs)
        
        return {
            "count": len(docs),
            "documents": [build_document_list_payload(doc) for doc in docs]
        }
    finally:
        db.close()


@router.get("/{document_id}/ml-annotations")
async def get_ml_annotations(document_id: str):
    """
    Get ML page annotations for a document
    
    Returns the ml_pages specification and ml_annotation from authority_data
    
    Args:
        document_id: Document identifier
    
    Returns:
        ML annotation metadata including page specifications
    """
    db = LocalSessionLocal()
    try:
        doc = db.query(Document).filter(
            Document.document_id == document_id
        ).first()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return build_document_annotations_payload(doc)
    finally:
        db.close()
