"""
Document models for temporal epistemic drift analysis
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
from app.core.database import LocalBase


class Document(LocalBase):
    """Documents for epistemic drift analysis (1965-1985)"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Authority linkage (REQUIRED for training corpus)
    pid = Column(String(255), unique=True, nullable=False, index=True)  # Postgres authority PID
    authority_id = Column(String(255), index=True)  # DDR Archive authority ID
    authority_data = Column(JSONB)  # Cached GraphQL authority metadata
    
    title = Column(String(500))
    publication_year = Column(Integer, nullable=False, index=True)  # 1965-1985
    publication_date = Column(DateTime)  # Full date if available
    
    # File info
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))  # 'pdf', 'tiff', etc.
    s3_key = Column(String(500))  # S3 storage path
    file_size_bytes = Column(Integer)
    
    # Extracted content
    extracted_text = Column(Text)  # Full text from Docling
    has_diagrams = Column(Integer, default=0)  # Count of diagrams
    diagram_s3_keys = Column(JSONB)  # Array of S3 keys for extracted diagrams
    
    # Processing metadata
    processed_at = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(50), default='pending')  # pending, processing, completed, failed
    processing_error = Column(Text)
    
    # Document metadata (renamed to avoid SQLAlchemy reserved word)
    doc_metadata = Column(JSONB)  # Author, journal, keywords, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentChunk(LocalBase):
    """Text chunks from documents for embedding and analysis"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(255), unique=True, nullable=False, index=True)
    document_id = Column(String(255), nullable=False, index=True)  # FK to documents
    
    # Chunk content
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)  # Position in document
    chunk_type = Column(String(50))  # 'paragraph', 'heading', 'caption', etc.
    
    # Temporal context
    publication_year = Column(Integer, nullable=False, index=True)
    
    # Embeddings (pgvector for similarity search)
    embedding_vector = Vector(384)  # pgvector type - matches all-MiniLM-L6-v2
    embedding_model = Column(String(100))  # e.g., 'all-MiniLM-L6-v2'
    
    # PROVENANCE TRACKING (for XAI)
    source_page = Column(Integer)  # Page number in PDF/TIFF
    source_section = Column(String(500))  # Section heading/title
    extraction_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # CITATION METADATA (full academic attribution)
    citation = Column(JSONB)
    # {
    #   "pid": "564310168393",
    #   "title": "Archer Systematic method for designers",
    #   "year": 1963,
    #   "creator": "L.B. Archer",
    #   "institution": "Royal College of Art",
    #   "page": 12,
    #   "section": "Chapter 3: Methodology",
    #   "public_url": "https://ddrarchive.org/id/record/564310168393",
    #   "rights": "Copyright © Royal College of Art"
    # }
    
    # Analysis results
    key_concepts = Column(JSONB)  # Extracted concepts
    drift_score = Column(Float)  # Epistemic drift score
    
    # Chunk metadata
    chunk_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class DriftAnalysis(LocalBase):
    """Temporal epistemic drift analysis results"""
    __tablename__ = "drift_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Time period comparison
    period_start_year = Column(Integer, nullable=False)
    period_end_year = Column(Integer, nullable=False)
    
    # Documents analyzed
    document_count = Column(Integer)
    document_ids = Column(JSONB)  # Array of document IDs
    
    # Drift metrics
    drift_score = Column(Float)  # Overall drift score
    conceptual_shift = Column(JSONB)  # Concepts that changed
    terminology_changes = Column(JSONB)  # Term frequency changes
    semantic_distance = Column(Float)  # Average semantic distance
    
    # Analysis method
    analysis_method = Column(String(100))  # 'embedding_comparison', 'granite_analysis', etc.
    model_used = Column(String(100))
    
    # Results
    results = Column(JSONB)  # Full analysis results
    visualization_data = Column(JSONB)  # Data for charts
    
    # Analysis metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    analysis_metadata = Column(JSONB)


class TrainingRun(LocalBase):
    """Training run provenance for model reproducibility and XAI"""
    __tablename__ = "training_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Model identification
    model_name = Column(String(255), nullable=False)  # e.g., "granite-epistemic-v1"
    model_type = Column(String(100))  # "bert", "granite", "sentence-transformer"
    base_model = Column(String(255))  # Base model used for fine-tuning
    
    # Training metadata
    training_date = Column(DateTime, nullable=False)
    training_duration_seconds = Column(Integer)
    
    # PROVENANCE: Which data was used
    chunk_ids_used = Column(JSONB)  # Array of chunk IDs in training set
    total_chunks = Column(Integer)
    pid_distribution = Column(JSONB)  # {"564310168393": 45, "362524095549": 38, ...}
    temporal_distribution = Column(JSONB)  # {"1965": 12, "1970": 34, ...}
    
    # REPRODUCIBILITY
    corpus_snapshot_id = Column(String(255), index=True)  # Links to CorpusSnapshot
    model_checkpoint_s3 = Column(String(500))  # S3 path to saved model
    hyperparameters = Column(JSONB)
    embedding_model_version = Column(String(100))
    framework_versions = Column(JSONB)  # {"pytorch": "2.0.0", "transformers": "4.46.2"}
    
    # Training results
    final_loss = Column(Float)
    metrics = Column(JSONB)
    
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class InferenceLog(LocalBase):
    """Inference provenance for XAI - traces predictions back to training data"""
    __tablename__ = "inference_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    inference_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Query and response
    query = Column(Text, nullable=False)
    query_embedding = Vector(384)  # Query vector for similarity tracking
    prediction = Column(Text)
    
    # Model used
    model_version = Column(String(255), nullable=False, index=True)
    training_run_id = Column(String(255), index=True)  # Links to TrainingRun
    
    # EXPLAINABILITY: Which training chunks influenced this prediction
    top_k_chunks = Column(JSONB)
    # [{"chunk_id": "...", "similarity": 0.87, "citation": {...}, "excerpt": "..."}]
    
    # PROVENANCE CHAIN
    source_pids = Column(JSONB)  # PIDs that influenced prediction
    source_years = Column(JSONB)  # Publication years
    
    confidence_score = Column(Float)
    inference_time_ms = Column(Integer)
    user_id = Column(String(255))
    session_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class CorpusSnapshot(LocalBase):
    """Corpus versioning for reproducibility and auditing"""
    __tablename__ = "corpus_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(String(255), unique=True, nullable=False, index=True)
    snapshot_date = Column(DateTime, nullable=False)
    
    name = Column(String(255))  # e.g., "PhD Submission Dataset v1.0"
    description = Column(Text)
    
    # REPRODUCIBILITY
    total_documents = Column(Integer)
    total_chunks = Column(Integer)
    pid_list = Column(JSONB)  # All PIDs in this version
    chunk_manifest_s3 = Column(String(500))  # S3 path to full manifest
    
    # Temporal coverage
    year_range_start = Column(Integer)
    year_range_end = Column(Integer)
    year_distribution = Column(JSONB)
    
    # AUDIT TRAIL
    changes_since_last = Column(JSONB)
    # {"added_pids": [...], "removed_pids": [...], "chunks_added": 234}
    
    manifest_checksum = Column(String(64))  # SHA-256
    statistics = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

