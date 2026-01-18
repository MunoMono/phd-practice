"""
Provenance Service - XAI and Academic Attribution
Tracks lineage from archival sources → training data → model predictions
"""
import logging
import hashlib
import json
from typing import List, Dict, Optional
from datetime import datetime
import uuid

from app.core.database import LocalSessionLocal
from app.models.document import (
    Document, 
    DocumentChunk, 
    TrainingRun, 
    InferenceLog, 
    CorpusSnapshot
)
from sqlalchemy import func, text

logger = logging.getLogger(__name__)


class ProvenanceService:
    """
    Service for tracking provenance and enabling explainable AI
    
    Core functions:
    1. Build citations for each chunk (academic attribution)
    2. Log training runs with data lineage
    3. Track inference back to source documents
    4. Version corpus for reproducibility
    """
    
    def build_chunk_citation(
        self,
        chunk_id: str,
        db: Optional[LocalSessionLocal] = None
    ) -> Optional[Dict]:
        """
        Build full academic citation for a chunk
        
        Args:
            chunk_id: Chunk ID to cite
            db: Database session (optional)
        
        Returns:
            Citation dict with full provenance chain
        """
        should_close = db is None
        if db is None:
            db = LocalSessionLocal()
        
        try:
            chunk = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_id == chunk_id
            ).first()
            
            if not chunk:
                return None
            
            # Get parent document
            doc = db.query(Document).filter(
                Document.document_id == chunk.document_id
            ).first()
            
            if not doc or not doc.pid:
                logger.warning(f"Chunk {chunk_id} has no PID linkage - cannot cite")
                return None
            
            # Build citation from authority data + chunk metadata
            authority = doc.authority_data or {}
            
            citation = {
                "chunk_id": chunk_id,
                "pid": doc.pid,
                "title": doc.title or authority.get('title', 'Untitled'),
                "year": doc.publication_year,
                "creator": authority.get('creator_agent_label', 'Unknown'),
                "institution": authority.get('rights_holders', 'Royal College of Art'),
                "page": chunk.source_page,
                "section": chunk.source_section,
                "public_url": authority.get('public_uri', f"https://ddrarchive.org/id/record/{doc.pid}"),
                "rights": authority.get('copyright_holder', 'Copyright © Royal College of Art'),
                "excerpt": chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text,
                "extraction_date": chunk.extraction_timestamp.isoformat() if chunk.extraction_timestamp else None
            }
            
            return citation
            
        finally:
            if should_close:
                db.close()
    
    def log_training_run(
        self,
        model_name: str,
        chunk_ids: List[str],
        hyperparameters: Dict,
        model_checkpoint_s3: str,
        corpus_snapshot_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Log a training run with full provenance
        
        Args:
            model_name: Name/version of model being trained
            chunk_ids: List of chunk IDs used in training
            hyperparameters: Training hyperparameters
            model_checkpoint_s3: S3 path to saved model
            corpus_snapshot_id: Links to specific corpus version
            description: Human-readable description
        
        Returns:
            run_id for this training run
        """
        db = LocalSessionLocal()
        try:
            run_id = f"train_{uuid.uuid4().hex[:12]}"
            
            # Analyze PID distribution
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_id.in_(chunk_ids)
            ).all()
            
            pid_dist = {}
            year_dist = {}
            
            for chunk in chunks:
                doc = db.query(Document).filter(
                    Document.document_id == chunk.document_id
                ).first()
                
                if doc and doc.pid:
                    pid_dist[doc.pid] = pid_dist.get(doc.pid, 0) + 1
                
                if chunk.publication_year:
                    year = str(chunk.publication_year)
                    year_dist[year] = year_dist.get(year, 0) + 1
            
            # Create training run record
            training_run = TrainingRun(
                run_id=run_id,
                model_name=model_name,
                training_date=datetime.utcnow(),
                chunk_ids_used=chunk_ids,
                total_chunks=len(chunk_ids),
                pid_distribution=pid_dist,
                temporal_distribution=year_dist,
                corpus_snapshot_id=corpus_snapshot_id,
                model_checkpoint_s3=model_checkpoint_s3,
                hyperparameters=hyperparameters,
                description=description
            )
            
            db.add(training_run)
            db.commit()
            
            logger.info(f"Logged training run {run_id}: {len(chunk_ids)} chunks from {len(pid_dist)} PIDs")
            return run_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error logging training run: {e}")
            raise
        finally:
            db.close()
    
    def log_inference(
        self,
        query: str,
        prediction: str,
        model_version: str,
        top_k_chunks: List[Dict],
        training_run_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log an inference with provenance back to source documents
        
        Args:
            query: User query
            prediction: Model prediction/response
            model_version: Model used for inference
            top_k_chunks: Top-k similar chunks that influenced prediction
                [{"chunk_id": "...", "similarity": 0.87, ...}]
            training_run_id: Links to training run
            session_id: Research session ID
        
        Returns:
            inference_id
        """
        db = LocalSessionLocal()
        try:
            inference_id = f"inf_{uuid.uuid4().hex[:12]}"
            
            # Extract source PIDs from top_k_chunks
            chunk_ids = [c['chunk_id'] for c in top_k_chunks]
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_id.in_(chunk_ids)
            ).all()
            
            source_pids = []
            source_years = []
            
            # Enrich top_k with citations
            enriched_chunks = []
            for chunk_info in top_k_chunks:
                chunk = next((c for c in chunks if c.chunk_id == chunk_info['chunk_id']), None)
                if chunk:
                    citation = self.build_chunk_citation(chunk.chunk_id, db)
                    chunk_info['citation'] = citation
                    
                    # Track source PIDs
                    doc = db.query(Document).filter(
                        Document.document_id == chunk.document_id
                    ).first()
                    if doc and doc.pid and doc.pid not in source_pids:
                        source_pids.append(doc.pid)
                    if chunk.publication_year and chunk.publication_year not in source_years:
                        source_years.append(chunk.publication_year)
                
                enriched_chunks.append(chunk_info)
            
            # Create inference log
            inference_log = InferenceLog(
                inference_id=inference_id,
                query=query,
                prediction=prediction,
                model_version=model_version,
                training_run_id=training_run_id,
                top_k_chunks=enriched_chunks,
                source_pids=source_pids,
                source_years=sorted(source_years),
                session_id=session_id
            )
            
            db.add(inference_log)
            db.commit()
            
            logger.info(f"Logged inference {inference_id}: {len(source_pids)} source PIDs")
            return inference_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error logging inference: {e}")
            raise
        finally:
            db.close()
    
    def create_corpus_snapshot(
        self,
        name: str,
        description: Optional[str] = None
    ) -> str:
        """
        Create a versioned snapshot of current training corpus
        
        Args:
            name: Snapshot name (e.g., "PhD Submission v1.0")
            description: Description of this snapshot
        
        Returns:
            snapshot_id
        """
        db = LocalSessionLocal()
        try:
            snapshot_id = f"snap_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # Get all current chunks with PIDs
            chunks = db.query(DocumentChunk).join(Document).filter(
                Document.pid.isnot(None)
            ).all()
            
            # Build manifest
            chunk_ids = [c.chunk_id for c in chunks]
            pid_set = set()
            year_dist = {}
            
            for chunk in chunks:
                doc = db.query(Document).filter(
                    Document.document_id == chunk.document_id
                ).first()
                
                if doc and doc.pid:
                    pid_set.add(doc.pid)
                
                if chunk.publication_year:
                    year = str(chunk.publication_year)
                    year_dist[year] = year_dist.get(year, 0) + 1
            
            # Calculate checksum
            manifest_str = json.dumps(sorted(chunk_ids), sort_keys=True)
            checksum = hashlib.sha256(manifest_str.encode()).hexdigest()
            
            # Temporal range
            years = [int(y) for y in year_dist.keys()]
            year_range = (min(years), max(years)) if years else (None, None)
            
            # Statistics
            stats = {
                "total_tokens": sum(len(c.chunk_text.split()) for c in chunks),
                "avg_chunk_length": sum(len(c.chunk_text) for c in chunks) // len(chunks) if chunks else 0,
                "unique_sources": len(pid_set)
            }
            
            # Create snapshot
            snapshot = CorpusSnapshot(
                snapshot_id=snapshot_id,
                snapshot_date=datetime.utcnow(),
                name=name,
                description=description,
                total_documents=len(pid_set),
                total_chunks=len(chunk_ids),
                pid_list=sorted(list(pid_set)),
                year_range_start=year_range[0],
                year_range_end=year_range[1],
                year_distribution=year_dist,
                manifest_checksum=checksum,
                statistics=stats
            )
            
            db.add(snapshot)
            db.commit()
            
            logger.info(f"Created corpus snapshot {snapshot_id}: {len(chunk_ids)} chunks from {len(pid_set)} PIDs")
            return snapshot_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating corpus snapshot: {e}")
            raise
        finally:
            db.close()
    
    def get_chunk_provenance(self, chunk_id: str) -> Dict:
        """
        Get complete provenance chain for a chunk
        
        Returns full path: Archive → Document → Chunk → Training → Inferences
        """
        db = LocalSessionLocal()
        try:
            chunk = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_id == chunk_id
            ).first()
            
            if not chunk:
                return {"error": "Chunk not found"}
            
            doc = db.query(Document).filter(
                Document.document_id == chunk.document_id
            ).first()
            
            # Training runs that used this chunk
            training_runs = db.query(TrainingRun).filter(
                TrainingRun.chunk_ids_used.contains([chunk_id])
            ).all()
            
            # Inferences influenced by this chunk
            inferences = db.query(InferenceLog).all()
            influenced_inferences = [
                inf for inf in inferences
                if any(c['chunk_id'] == chunk_id for c in (inf.top_k_chunks or []))
            ]
            
            return {
                "chunk": {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.chunk_text[:500] + "...",
                    "page": chunk.source_page,
                    "section": chunk.source_section,
                    "extraction_date": chunk.extraction_timestamp.isoformat() if chunk.extraction_timestamp else None
                },
                "document": {
                    "pid": doc.pid if doc else None,
                    "title": doc.title if doc else None,
                    "year": doc.publication_year if doc else None,
                    "authority_url": doc.authority_data.get('public_uri') if doc and doc.authority_data else None
                },
                "citation": self.build_chunk_citation(chunk_id, db),
                "training_runs": [
                    {
                        "run_id": run.run_id,
                        "model": run.model_name,
                        "date": run.training_date.isoformat()
                    }
                    for run in training_runs
                ],
                "inferences_influenced": len(influenced_inferences),
                "sample_inferences": [
                    {
                        "inference_id": inf.inference_id,
                        "query": inf.query[:100] + "...",
                        "date": inf.created_at.isoformat()
                    }
                    for inf in influenced_inferences[:5]
                ]
            }
            
        finally:
            db.close()
