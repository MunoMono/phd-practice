"""
Document upload and processing endpoints
Handles PDF uploads with temporal metadata for epistemic drift analysis
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import uuid
from datetime import datetime

from app.services.docling_processor import DoclingProcessor
from app.services.embedding_service import EmbeddingService
from app.core.database import LocalSessionLocal
from app.models.document import Document, DocumentChunk

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
    Upload PDF/TIFF document for epistemic drift analysis
    
    CRITICAL: Only PID-linked assets are eligible for training corpus
    
    Args:
        file: PDF or TIFF file upload
        pid: Postgres authority PID (REQUIRED - links to source of truth)
        title: Document title
        publication_year: Year published (1965-1985)
        publication_date: Full publication date (optional)
        authority_id: DDR Archive authority ID (optional)
        metadata: JSON string with author, journal, etc.
    """
    try:
        # Validate PID is provided
        if not pid or not pid.strip():
            raise HTTPException(
                status_code=400,
                detail="PID is required - only authority-linked assets can be ingested"
            )
        
        # Validate publication year
        if not (1965 <= publication_year <= 1985):
            raise HTTPException(
                status_code=400,
                detail="Publication year must be between 1965 and 1985"
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
        
        return {
            "document_id": doc.document_id,
            "title": doc.title,
            "publication_year": doc.publication_year,
            "filename": doc.filename,
            "processing_status": doc.processing_status,
            "has_diagrams": doc.has_diagrams,
            "created_at": doc.created_at.isoformat()
        }
    finally:
        db.close()


@router.get("/")
async def list_documents(
    year: Optional[int] = None,
    status: Optional[str] = None
):
    """List all documents with optional filters"""
    db = LocalSessionLocal()
    try:
        query = db.query(Document)
        
        if year:
            query = query.filter(Document.publication_year == year)
        if status:
            query = query.filter(Document.processing_status == status)
        
        docs = query.order_by(Document.publication_year).all()
        
        return {
            "count": len(docs),
            "documents": [
                {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "publication_year": doc.publication_year,
                    "status": doc.processing_status
                }
                for doc in docs
            ]
        }
    finally:
        db.close()
