from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import LocalBase


class MissingnessEvent(LocalBase):
    __tablename__ = "missingness_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    type = Column(String(32), nullable=False, index=True)
    query_or_entity_or_field = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    query_id = Column(String(255), index=True)
    source_document_id = Column(String(255), index=True)
    source_chunk_id = Column(String(255), index=True)
    source_document_ids_json = Column(JSONB)
    source_chunk_ids_json = Column(JSONB)
    cross_read_mapping_id = Column(String(255), index=True)
    status = Column(String(32), nullable=False, default="open", index=True)
    reviewer_note = Column(Text)
    follow_up_action = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmbeddingReadinessReview(LocalBase):
    __tablename__ = "embedding_readiness_reviews"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    corpus_release = Column(String(255), nullable=False)
    source_scope = Column(Text, nullable=False)
    exclusions = Column(Text, nullable=False)
    embedding_model = Column(String(255), nullable=False)
    model_revision_or_checksum = Column(String(255), nullable=False)
    vector_dimensions = Column(Integer, nullable=False)
    runtime_and_license = Column(Text, nullable=False)
    normalisation_chunking_version = Column(String(255), nullable=False)
    capacity_retention_plan = Column(Text, nullable=False)
    fts_separation_plan = Column(Text, nullable=False)
    analytical_question = Column(Text, nullable=False)
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Claim(LocalBase):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String(255), unique=True, nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    support_level = Column(String(32), nullable=False, default="unresolved", index=True)
    caveats = Column(Text)
    reviewer_status = Column(String(64), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evidence = relationship("ClaimEvidence", back_populates="claim", cascade="all, delete-orphan")


class ClaimEvidence(LocalBase):
    __tablename__ = "claim_evidence"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String(255), ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(255), nullable=False, index=True)
    document_id = Column(String(255), index=True)
    page_range = Column(String(255))
    citation_text = Column(Text)
    provenance_json = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="evidence")


class QueryRun(LocalBase):
    __tablename__ = "query_runs"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(255), unique=True, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    mode = Column(String(64), index=True)
    model = Column(String(255))
    response = Column(Text)
    caveats = Column(Text)
    failed_or_partial = Column(Boolean, nullable=False, default=False, index=True)
    failure_reason = Column(Text)
    retrieved_chunk_count = Column(Integer, nullable=False, default=0)
    export_status = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("QueryRunChunk", back_populates="query_run", cascade="all, delete-orphan")
    exports = relationship("QueryRunExport", back_populates="query_run", cascade="all, delete-orphan")


class QueryRunChunk(LocalBase):
    __tablename__ = "query_run_chunks"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(255), ForeignKey("query_runs.query_id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(255), nullable=False, index=True)
    document_id = Column(String(255), index=True)
    page_range = Column(String(255))
    rank = Column(Integer)
    score = Column(Float)
    citation_text = Column(Text)
    provenance_json = Column(JSONB)
    source_metadata_json = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    query_run = relationship("QueryRun", back_populates="chunks")


class QueryRunExport(LocalBase):
    __tablename__ = "query_run_exports"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(255), ForeignKey("query_runs.query_id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(String(32), nullable=False, index=True)
    export_payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    query_run = relationship("QueryRun", back_populates="exports")


class ExperimentRun(LocalBase):
    """Write-once archival experiment snapshot; assessments live separately."""
    __tablename__ = "experiment_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(255), unique=True, nullable=False, index=True)
    research_case = Column(String(64), nullable=False, index=True)
    prompt_name = Column(String(255), nullable=False)
    prompt_version = Column(String(64), nullable=False)
    system_prompt_version = Column(String(64), nullable=False)
    exact_research_question = Column(Text, nullable=False)
    question_id = Column(String(64), index=True)
    retrieval_protocol_version = Column(String(128))
    retrieval_plan_id = Column(String(255))
    retrieval_plan_version = Column(String(128))
    retrieval_plan_approval_state = Column(String(32))
    retrieval_plan_json = Column(JSONB)
    retrieval_scope = Column(String(64))
    retrieval_run_classification = Column(String(64))
    recovery_of_run_id = Column(String(255))
    recovery_category = Column(String(128))
    formal_authorization_id = Column(String(255))
    execution_environment = Column(String(64))
    corpus_version = Column(String(255))
    git_commit = Column(String(64))
    retrieval_method = Column(String(128), nullable=False)
    retrieval_config_json = Column(JSONB, nullable=False)
    retrieval_diagnostics_json = Column(JSONB, nullable=False)
    context_mode = Column(String(64), nullable=False)
    context_character_count = Column(Integer, nullable=False)
    context_chunk_count = Column(Integer, nullable=False)
    omitted_chunk_ids_json = Column(JSONB, nullable=False)
    context_budget_json = Column(JSONB)
    authority_context_json = Column(JSONB, nullable=False)
    model_name = Column(String(255))
    model_runtime = Column(String(64))
    model_quantisation = Column(String(128))
    model_parameters_json = Column(JSONB, nullable=False)
    model_seed_if_actual = Column(String(64))
    inference_duration_ms = Column(Float)
    raw_model_response = Column(Text)
    repair_attempted = Column(Boolean, nullable=False, default=False)
    raw_repair_response = Column(Text)
    generation_metadata_json = Column(JSONB)
    repair_generation_metadata_json = Column(JSONB)
    response_schema_json = Column(JSONB)
    response_schema_version = Column(String(128))
    response_schema_hash = Column(String(128))
    parse_status = Column(String(64), nullable=False)
    parsed_response_json = Column(JSONB)
    display_response_json = Column(JSONB)
    structured_response_json = Column(JSONB)
    provenance_validation_json = Column(JSONB)
    status = Column(String(64), nullable=False, index=True)
    error_code = Column(String(128))
    error_message = Column(Text)
    fixture_only = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    locked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    evidence = relationship("ExperimentRunEvidence", back_populates="experiment_run", cascade="all, delete-orphan")
    assessment = relationship("ExperimentRunAssessment", back_populates="experiment_run", uselist=False, cascade="all, delete-orphan")


class TurinRetrievalPlan(LocalBase):
    """Versioned plan record; executed plans are locked by database trigger."""
    __tablename__ = "turin_retrieval_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
    question_id = Column(String(64), nullable=False, index=True)
    protocol_version = Column(String(128), nullable=False)
    plan_version = Column(String(128), nullable=False)
    researcher_approval_state = Column(String(32), nullable=False)
    researcher_approved_at = Column(DateTime)
    run_classification = Column(String(64), nullable=False)
    supersedes_plan_id = Column(String(255))
    plan_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TurinAuthorityDocumentLink(LocalBase):
    """Approved DDR provenance relationship usable only by diagnostic retrieval plans."""
    __tablename__ = "turin_authority_document_links"

    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(String(255), unique=True, nullable=False, index=True)
    authority_source = Column(String(255), nullable=False)
    authority_type = Column(String(128), nullable=False)
    authority_id = Column(String(255), nullable=False, index=True)
    document_id = Column(String(255), nullable=False, index=True)
    archive_record_pid = Column(String(255), nullable=False, index=True)
    relationship_type = Column(String(128), nullable=False)
    provenance_source = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    approval_state = Column(String(32), nullable=False)
    approved_by = Column(String(255))
    approved_at = Column(DateTime)
    link_version = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ExperimentRunEvidence(LocalBase):
    """Frozen retrieved-evidence snapshot, including exact source text supplied."""
    __tablename__ = "experiment_run_evidence"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(255), ForeignKey("experiment_runs.run_id", ondelete="RESTRICT"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    score = Column(Float)
    document_id = Column(String(255), nullable=False, index=True)
    pid = Column(String(255))
    archive_record_pid = Column(String(255))
    archive_resolution_status = Column(String(64), nullable=False)
    page_start = Column(Integer)
    page_end = Column(Integer)
    chunk_id = Column(String(255), nullable=False, index=True)
    chunk_sequence = Column(Integer)
    excerpt = Column(Text, nullable=False)
    supplied_excerpt = Column(Text)
    included_in_context = Column(Boolean, nullable=False)
    original_chars = Column(Integer)
    supplied_chars = Column(Integer)
    excerpted = Column(Boolean)
    exclusion_reason = Column(String(128))
    snapshot_json = Column(JSONB, nullable=False)

    experiment_run = relationship("ExperimentRun", back_populates="evidence")


class ExperimentRunAssessment(LocalBase):
    """Researcher-authored evaluation, intentionally mutable and separate."""
    __tablename__ = "experiment_run_assessments"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(255), ForeignKey("experiment_runs.run_id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    retrieval_relevance = Column(Integer)
    provenance_accuracy = Column(Integer)
    interpretative_restraint = Column(Integer)
    preservation_of_contestation = Column(Integer)
    missingness_handling = Column(Integer)
    failure_categories_json = Column(JSONB, nullable=False, default=list)
    notes = Column(Text)
    authority_influence_note = Column(Text)
    assessed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    experiment_run = relationship("ExperimentRun", back_populates="assessment")


class CrossReadPassage(LocalBase):
    __tablename__ = "cross_read_passages"

    id = Column(Integer, primary_key=True, index=True)
    passage_id = Column(String(255), unique=True, nullable=False, index=True)
    passage_text = Column(Text, nullable=False)
    speaker_or_source = Column(String(255))
    passage_label = Column(String(255))
    source_type = Column(String(64), index=True)
    source_reference = Column(Text)
    source_date = Column(String(64))
    access_status = Column(String(32), nullable=False, default="unknown", index=True)
    ingestion_method = Column(String(32), nullable=False, default="researcher_entered")
    memory_position_note = Column(Text)
    status = Column(String(32), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mappings = relationship("CrossReadMapping", back_populates="passage", cascade="all, delete-orphan")


class CrossReadMapping(LocalBase):
    __tablename__ = "cross_read_mappings"

    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(String(255), unique=True, nullable=False, index=True)
    passage_id = Column(String(255), ForeignKey("cross_read_passages.passage_id", ondelete="CASCADE"), nullable=False, index=True)
    query_id = Column(String(255), ForeignKey("query_runs.query_id", ondelete="SET NULL"), index=True)
    chunk_id = Column(String(255), index=True)
    document_id = Column(String(255), index=True)
    page_range = Column(String(255))
    relation_type = Column(String(64), nullable=False, index=True)
    confidence_or_status = Column(String(64), index=True)
    reviewer_note = Column(Text)
    citation_text = Column(Text)
    provenance_json = Column(JSONB)
    source_metadata_json = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    passage = relationship("CrossReadPassage", back_populates="mappings")