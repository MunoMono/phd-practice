"""
Visualization API - Data endpoints for D3.js visualizations
Carbon Design System compatible data structures
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from typing import List, Dict, Literal, Optional
from datetime import datetime
import json
import logging
import re
import uuid
import numpy as np

from app.core.database import LocalSessionLocal
from app.core.ddr_temporal_scope import DDR_DOCUMENT_SQL_SCOPE
from app.models.research_outputs import EmbeddingReadinessReview, MissingnessEvent
from app.services.corpus_status_service import get_corpus_status

router = APIRouter()
logger = logging.getLogger(__name__)

try:
    import umap  # type: ignore
except ImportError:  # pragma: no cover - exercised by environment
    umap = None

try:
    from sklearn.decomposition import PCA  # type: ignore
except ImportError:  # pragma: no cover - exercised by environment
    PCA = None


SCOPED_MISSINGNESS_V02_BASELINE = {
    "ingested_granite_pdfs": 4,
    "archive_wide_records_from_scoped_missingness_v02": 19,
    "records_with_pdfs": 17,
    "image_only_records": 1,
    "no_asset_records": 1,
    "unknown_until_docling_records": 19,
}

ReadinessStatus = Literal["draft", "blocked", "approved"]


class EmbeddingReadinessReviewRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: ReadinessStatus
    corpus_release: str
    source_scope: str
    exclusions: str
    embedding_model: str
    model_revision_or_checksum: str
    vector_dimensions: int = Field(gt=0)
    runtime_and_license: str
    normalisation_chunking_version: str
    capacity_retention_plan: str
    fts_separation_plan: str
    analytical_question: str
    reviewed_by: Optional[str] = None

    @field_validator(
        "corpus_release", "source_scope", "exclusions", "embedding_model", "model_revision_or_checksum",
        "runtime_and_license", "normalisation_chunking_version", "capacity_retention_plan", "fts_separation_plan",
        "analytical_question",
    )
    @classmethod
    def required_review_fields_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Readiness review fields must not be blank")
        return value

    @model_validator(mode="after")
    def approved_review_requires_reviewer(self):
        if self.status == "approved" and not (self.reviewed_by or "").strip():
            raise ValueError("An approved readiness review requires the reviewing researcher")
        return self


class AtlasCoverageMissingnessRequest(BaseModel):
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    pid: Optional[str] = None
    projection_id: Optional[str] = None

    @model_validator(mode="after")
    def requires_durable_source_identifier(self):
        if not any((self.document_id, self.chunk_id, self.pid)):
            raise ValueError("A document ID, chunk ID, or PID is required")
        return self


class SemanticNeighbourhoodRequest(BaseModel):
    focal_chunk_id: str = Field(min_length=1, max_length=255)
    size: int = Field(default=25, ge=1, le=50)


class CriticalProbeRequest(BaseModel):
    concept: str = Field(min_length=2, max_length=500)
    size: int = Field(default=25, ge=1, le=50)


class UmapChallengeRequest(BaseModel):
    random_seed: int = Field(default=42, ge=0, le=9999)
    n_neighbors: int = Field(default=15, ge=2, le=100)
    min_dist: float = Field(default=0.1, ge=0.0, le=0.99)
    sample_size: int = Field(default=500, ge=50, le=1000)


def _semantic_point_payload(row) -> dict:
    concepts = _extract_key_concepts(row.key_concepts)
    return {
        "id": row.chunk_id,
        "document_id": row.document_id,
        "chunk_id": row.chunk_id,
        "pid": row.pid,
        "title": row.title or "Untitled trace",
        "year": int(row.year) if row.year is not None else None,
        "source_type": _infer_source_type(row.file_type, row.chunk_type, row.citation),
        "themes": concepts,
        "excerpt": _clean_excerpt(row.chunk_text),
        "source_page": row.source_page,
        "source_section": row.source_section,
        "similarity": round(float(row.similarity), 5),
        "x": float(row.x) if row.x is not None else None,
        "y": float(row.y) if row.y is not None else None,
    }


def _semantic_neighbour_query(where_clause: str, citation_select: str) -> str:
    return f"""
        SELECT
            dc.document_id, dc.chunk_id, d.pid, d.title,
            COALESCE(dc.publication_year, d.publication_year) AS year,
            d.file_type, dc.chunk_type, {citation_select}, dc.key_concepts,
            dc.chunk_text, dc.source_page, dc.source_section,
            pp.x, pp.y, {where_clause} AS similarity
        FROM semantic_chunk_embeddings sce
        JOIN document_chunks dc ON dc.chunk_id = sce.chunk_id
        JOIN documents d ON d.document_id = dc.document_id
        LEFT JOIN semantic_atlas_projection_points pp
            ON pp.chunk_id = sce.chunk_id AND pp.projection_id = :projection_id
        WHERE sce.embedding_set_id = :embedding_set_id
            AND sce.status = 'embedded'
            AND d.pid IS NOT NULL
            AND {DDR_DOCUMENT_SQL_SCOPE}
        ORDER BY sce.embedding <=> CAST(:query_vector AS vector)
        LIMIT :size
    """


def _load_probe_embedding(model_name: str, concept: str) -> list[float]:
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name, trust_remote_code=True)
        vector = model.encode(concept, normalize_embeddings=True)
        return np.asarray(vector, dtype=float).tolist()
    except Exception as error:
        logger.exception("Critical concept probe embedding failed")
        raise HTTPException(status_code=503, detail="A compatible semantic embedding model is unavailable for this concept probe.") from error


def serialize_readiness_review(review: EmbeddingReadinessReview) -> dict:
    return {
        "review_id": review.review_id,
        "status": review.status,
        "corpus_release": review.corpus_release,
        "source_scope": review.source_scope,
        "exclusions": review.exclusions,
        "embedding_model": review.embedding_model,
        "model_revision_or_checksum": review.model_revision_or_checksum,
        "vector_dimensions": review.vector_dimensions,
        "runtime_and_license": review.runtime_and_license,
        "normalisation_chunking_version": review.normalisation_chunking_version,
        "capacity_retention_plan": review.capacity_retention_plan,
        "fts_separation_plan": review.fts_separation_plan,
        "analytical_question": review.analytical_question,
        "reviewed_by": review.reviewed_by,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


@router.get("/embedding-readiness")
async def get_embedding_readiness():
    db = LocalSessionLocal()
    try:
        review = db.query(EmbeddingReadinessReview).order_by(EmbeddingReadinessReview.created_at.desc()).first()
        if review:
            return {"ready_for_embedding": review.status == "approved", "review": serialize_readiness_review(review)}
        return {
            "ready_for_embedding": False,
            "review": None,
            "message": "No readiness review has been recorded. The atlas remains inactive; this is a technical state, not evidence of historical absence.",
        }
    finally:
        db.close()


@router.post("/embedding-readiness", status_code=201)
async def create_embedding_readiness_review(request: EmbeddingReadinessReviewRequest):
    db = LocalSessionLocal()
    try:
        reviewed_by = request.reviewed_by.strip() if request.reviewed_by else None
        review = EmbeddingReadinessReview(
            review_id=f"embed-ready-{uuid.uuid4().hex[:12]}",
            status=request.status,
            corpus_release=request.corpus_release,
            source_scope=request.source_scope,
            exclusions=request.exclusions,
            embedding_model=request.embedding_model,
            model_revision_or_checksum=request.model_revision_or_checksum,
            vector_dimensions=request.vector_dimensions,
            runtime_and_license=request.runtime_and_license,
            normalisation_chunking_version=request.normalisation_chunking_version,
            capacity_retention_plan=request.capacity_retention_plan,
            fts_separation_plan=request.fts_separation_plan,
            analytical_question=request.analytical_question,
            reviewed_by=reviewed_by,
            reviewed_at=datetime.utcnow() if request.status == "approved" else None,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return {"ready_for_embedding": review.status == "approved", "review": serialize_readiness_review(review)}
    finally:
        db.close()


@router.post("/atlas-coverage-missingness", status_code=201)
async def create_atlas_coverage_missingness(request: AtlasCoverageMissingnessRequest):
    """Record a researcher-confirmed computational coverage condition, never archival absence."""
    db = LocalSessionLocal()
    try:
        source = db.execute(text("""
            SELECT document_id, pid, title
            FROM documents
            WHERE (:document_id IS NOT NULL AND document_id = :document_id)
               OR (:pid IS NOT NULL AND pid = :pid)
               OR (:chunk_id IS NOT NULL AND document_id = (
                   SELECT document_id FROM document_chunks WHERE chunk_id = :chunk_id
               ))
            LIMIT 1
        """), request.model_dump()).mappings().first()
        if not source:
            raise HTTPException(status_code=404, detail="The nominated Atlas source is not available in the current document registry.")

        projection = _get_completed_semantic_atlas_projection(db)
        projection_id = request.projection_id or (projection or {}).get("projection_id")
        if projection_id:
            represented = db.execute(text("""
                SELECT EXISTS(
                    SELECT 1
                    FROM semantic_atlas_projection_points point
                    JOIN document_chunks chunk ON chunk.chunk_id = point.chunk_id
                    WHERE point.projection_id = :projection_id
                      AND chunk.document_id = :document_id
                      AND (:chunk_id IS NULL OR chunk.chunk_id = :chunk_id)
                )
            """), {"projection_id": projection_id, "document_id": source["document_id"], "chunk_id": request.chunk_id}).scalar()
            if represented:
                raise HTTPException(status_code=409, detail="The nominated source is represented in the current Semantic Atlas projection.")

        scope = f"projection {projection_id}" if projection_id else "the current Semantic Atlas embedding/projection configuration"
        event = MissingnessEvent(
            event_id=f"miss-{uuid.uuid4().hex[:12]}",
            type="computational",
            query_or_entity_or_field=f"Semantic Atlas coverage for {source['title'] or source['document_id']}",
            evidence=(
                f"Known source {source['document_id']} is not represented in {scope}. "
                "This records a computational embedding or extracted-text coverage condition only; "
                "it does not establish that the source is absent from the archive."
            ),
            source_document_id=source["document_id"],
            source_chunk_id=request.chunk_id,
            source_document_ids_json=[source["document_id"]],
            source_chunk_ids_json=[request.chunk_id] if request.chunk_id else [],
            status="open",
            reviewer_note="Created from a researcher-selected Semantic Atlas coverage gap.",
            follow_up_action="Review extracted text, embedding status, source access, and projection membership before reprocessing.",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return {"event_id": event.event_id, "document_id": event.source_document_id, "chunk_id": event.source_chunk_id, "type": event.type}
    finally:
        db.close()


def _vector_to_list(value) -> List[float]:
    if value is None:
        return []

    if isinstance(value, np.ndarray):
        return value.astype(float).tolist()

    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]

    if isinstance(value, memoryview):
        value = value.tobytes().decode("utf-8")

    if isinstance(value, bytes):
        value = value.decode("utf-8")

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [float(item) for item in parsed]
        except json.JSONDecodeError:
            stripped = stripped.strip("[]")
            if not stripped:
                return []
            return [float(item.strip()) for item in stripped.split(",") if item.strip()]

    try:
        return [float(item) for item in value]
    except TypeError:
        return []


def _clean_excerpt(text_value: Optional[str], limit: int = 240) -> Optional[str]:
    if not text_value:
        return None

    cleaned = re.sub(r"\s+", " ", text_value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _has_meaningful_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "—"}
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _classify_missingness(value, *, missing_key: bool = False):
    if missing_key:
        return {"state": "missing_key"}
    if value is None:
        return {"state": "explicit_null"}
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return {"state": "blank_string"}
        if stripped == "—":
            return {"state": "placeholder"}
    return None


def _slugify_cluster(value: Optional[str]) -> str:
    if not value:
        return "unclustered"
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unclustered"


def _extract_key_concepts(value) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
            if isinstance(parsed, dict):
                concepts = parsed.get("concepts") or parsed.get("themes") or []
                return [str(item).strip() for item in concepts if str(item).strip()]
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]

    if isinstance(value, dict):
        concepts = value.get("concepts") or value.get("themes") or []
        return [str(item).strip() for item in concepts if str(item).strip()]

    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    return []


def _extract_entities(value) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            value = parsed
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]

    if isinstance(value, dict):
        if "entities" in value and isinstance(value["entities"], list):
            return [str(item).strip() for item in value["entities"] if str(item).strip()]
        return [str(key).strip() for key in value.keys() if str(key).strip()]

    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    return []


def _infer_source_type(file_type: Optional[str], chunk_type: Optional[str], citation_value) -> str:
    normalized_file_type = (file_type or "").strip().lower()
    normalized_chunk_type = (chunk_type or "").strip().lower()

    citation_obj = None
    if isinstance(citation_value, str) and citation_value.strip():
        try:
            citation_obj = json.loads(citation_value)
        except json.JSONDecodeError:
            citation_obj = None
    elif isinstance(citation_value, dict):
        citation_obj = citation_value

    citation_text = json.dumps(citation_obj).lower() if citation_obj else ""

    if normalized_chunk_type in {"oral_history", "interview", "transcript"}:
        return "oral_history"
    if normalized_file_type in {"pdf", "tiff"}:
        return normalized_file_type
    if normalized_file_type in {"jpg", "jpeg", "png"}:
        return "publication"
    if "oral" in citation_text or "interview" in citation_text:
        return "oral_history"
    if "publication" in citation_text:
        return "publication"
    return "unknown"


def _empty_scoped_missingness():
    return {
        "item_field_missingness": {},
        "asset_missingness": {},
        "graphql_exposure_missingness": {},
        "llm_evidence_missingness": {},
        "interpretation_limits": [],
    }


def _build_interpretation_warnings() -> List[str]:
    return [
        "Spatial proximity is a prompt for archival investigation, not proof of historical relation.",
        "Absence from this projection should not be read as absence from the DDR archive.",
        "PDF visibility does not imply extracted text.",
        "Image visibility does not imply searchable text.",
        "Authority/context gaps may mean not exposed by the current GraphQL evidence surface, not archival absence.",
    ]


def _infer_evidence_surface(record: Dict) -> Dict:
    has_pdf = bool((record.get("pdf_count") or 0) > 0) or (record.get("file_type") or "").lower() == "pdf" or str(record.get("filename") or "").lower().endswith(".pdf")
    has_image_assets = (record.get("file_type") or "").lower() in {"tiff", "jpg", "jpeg", "png"} or bool((record.get("has_diagrams") or 0) > 0)
    has_extracted_text = _has_meaningful_value(record.get("chunk_text")) or _has_meaningful_value(record.get("document_extracted_text"))
    has_authority_context = _has_meaningful_value(record.get("authority_data"))
    has_embedding = bool(record.get("has_embedding"))
    requires_docling_or_ocr = (not has_extracted_text) and (has_pdf or has_image_assets)

    if has_embedding and has_extracted_text:
        visibility_label = "embedded_text_available"
    elif has_pdf and not has_extracted_text:
        visibility_label = "pdf_available_text_unknown"
    elif has_image_assets and not has_extracted_text:
        visibility_label = "image_only_requires_ocr_or_docling"
    elif not has_pdf and not has_image_assets:
        visibility_label = "no_assets_exposed"
    elif not has_authority_context:
        visibility_label = "authority_context_not_exposed"
    else:
        visibility_label = "unknown_until_docling"

    interpretation_limit = None
    if not has_authority_context:
        interpretation_limit = "Authority/context is not exposed by the current LLM/public GraphQL evidence surface."
    elif requires_docling_or_ocr:
        interpretation_limit = "Interpretation remains limited until Docling or OCR yields searchable text in the current LLM/public GraphQL evidence surface."

    return {
        "is_ingested": True,
        "has_embedding": has_embedding,
        "has_extracted_text": has_extracted_text,
        "has_pdf": has_pdf,
        "has_image_assets": has_image_assets,
        "has_authority_context": has_authority_context,
        "requires_docling_or_ocr": requires_docling_or_ocr,
        "visibility_label": visibility_label,
        "interpretation_limit": interpretation_limit,
    }


def _build_missingness(record: Dict, evidence_surface: Dict) -> Dict:
    missingness = _empty_scoped_missingness()

    title_missing = _classify_missingness(record.get("title"))
    if title_missing:
        missingness["item_field_missingness"]["title"] = title_missing

    year_missing = _classify_missingness(record.get("year"))
    if year_missing:
        missingness["item_field_missingness"]["publication_year"] = year_missing

    source_page_missing = _classify_missingness(record.get("source_page"), missing_key=record.get("source_page") is None)
    if source_page_missing and record.get("chunk_id"):
        missingness["item_field_missingness"]["source_page"] = source_page_missing

    source_section_missing = _classify_missingness(record.get("source_section"), missing_key=record.get("source_section") is None)
    if source_section_missing and record.get("chunk_id"):
        missingness["item_field_missingness"]["source_section"] = source_section_missing

    if not evidence_surface["has_pdf"]:
        missingness["asset_missingness"]["pdf"] = {"state": "not_exposed_by_graphql_preset"}
    if not evidence_surface["has_image_assets"]:
        missingness["asset_missingness"]["image_assets"] = {"state": "not_exposed_by_graphql_preset"}
    if not evidence_surface["has_authority_context"]:
        missingness["graphql_exposure_missingness"]["authority_context"] = {"state": "not_exposed_by_graphql_preset"}
    if not evidence_surface["has_extracted_text"]:
        missingness["llm_evidence_missingness"]["searchable_text"] = {"state": "unknown_until_docling"}
    if not evidence_surface["has_embedding"]:
        missingness["llm_evidence_missingness"]["embedding_vector"] = {"state": "not_ingested_in_ml_surface"}
    if evidence_surface["interpretation_limit"]:
        missingness["interpretation_limits"].append(evidence_surface["interpretation_limit"])

    return missingness


def _project_vectors(
    vectors: List[List[float]],
    *,
    random_seed: int = 42,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
):
    if len(vectors) == 0:
        return [], "none"

    if len(vectors) == 1:
        return [[0.0, 0.0]], "none"

    matrix = np.array(vectors, dtype=float)

    if umap is not None:
        reducer = umap.UMAP(
            n_neighbors=min(n_neighbors, max(2, len(vectors) - 1)),
            n_components=2,
            metric="cosine",
            min_dist=min_dist,
            random_state=random_seed,
        )
        projection = reducer.fit_transform(matrix)
        return projection.tolist(), "umap"

    if PCA is not None:
        projection = PCA(n_components=2).fit_transform(matrix)
        return projection.tolist(), "pca_fallback"

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise HTTPException(status_code=500, detail=f"Projection failed: {exc}") from exc

    components = vt[:2].T
    projection = centered @ components

    if projection.shape[1] == 1:
        projection = np.column_stack([projection[:, 0], np.zeros(len(vectors))])

    return projection.tolist(), "pca_fallback"


def _summarize_clusters(points: List[Dict]) -> List[Dict]:
    cluster_map: Dict[str, Dict] = {}

    for point in points:
        cluster_id = point["cluster_id"]
        cluster = cluster_map.setdefault(
            cluster_id,
            {
                "id": cluster_id,
                "label": point["cluster_label"],
                "points": [],
                "terms": {},
                "years": [],
                "pids": [],
                "with_extracted_text": 0,
                "unknown_until_docling": 0,
                "authority_context_not_exposed": 0,
            },
        )
        cluster["points"].append(point)
        for theme in point.get("themes", []):
            cluster["terms"][theme] = cluster["terms"].get(theme, 0) + 1
        if point.get("year") is not None:
            cluster["years"].append(point["year"])
        if point.get("pid"):
            cluster["pids"].append(point["pid"])
        if point.get("evidence_surface", {}).get("has_extracted_text"):
            cluster["with_extracted_text"] += 1
        if point.get("evidence_surface", {}).get("visibility_label") in {"pdf_available_text_unknown", "unknown_until_docling", "image_only_requires_ocr_or_docling"}:
            cluster["unknown_until_docling"] += 1
        if not point.get("evidence_surface", {}).get("has_authority_context"):
            cluster["authority_context_not_exposed"] += 1

    summaries = []
    for cluster in cluster_map.values():
        top_terms = [
            term for term, _count in sorted(cluster["terms"].items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        representative_pids = list(dict.fromkeys(cluster["pids"]))[:5]
        year_range = []
        if cluster["years"]:
            year_range = [min(cluster["years"]), max(cluster["years"])]

        summaries.append(
            {
                "id": cluster["id"],
                "label": cluster["label"],
                "size": len(cluster["points"]),
                "top_terms": top_terms,
                "year_range": year_range,
                "representative_pids": representative_pids,
                "evidence_surface_summary": {
                    "embedded_points": len(cluster["points"]),
                    "pids": len(set(cluster["pids"])),
                    "with_extracted_text": cluster["with_extracted_text"],
                    "unknown_until_docling": cluster["unknown_until_docling"],
                    "authority_context_not_exposed": cluster["authority_context_not_exposed"],
                },
            }
        )

    return sorted(summaries, key=lambda item: (-item["size"], item["label"]))


def _supports_document_embeddings(db) -> bool:
    result = db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documents'
                    AND column_name = 'embeddings'
            ) AS supported
            """
        )
    ).fetchone()
    return bool(result.supported) if result else False


def _get_table_columns(db, table_name: str) -> set[str]:
    result = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return {row.column_name for row in result}


def _get_database_scope_counts(db) -> Dict:
    document_columns = _get_table_columns(db, "documents")
    document_embedding_count = (
        "COUNT(*) FILTER (WHERE embeddings IS NOT NULL)"
        if "embeddings" in document_columns
        else "0"
    )
    pdf_asset_count = "COUNT(*) FILTER (WHERE pdf_count > 0)" if "pdf_count" in document_columns else "0"
    image_like_count = "COUNT(*) FILTER (WHERE file_type IN ('tiff', 'jpg', 'jpeg', 'png'))" if "file_type" in document_columns else "0"
    counts = db.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS total_documents,
                COUNT(*) FILTER (WHERE NULLIF(BTRIM(COALESCE(extracted_text, '')), '') IS NOT NULL) AS documents_with_extracted_text,
                {document_embedding_count} AS documents_with_embeddings,
                COUNT(*) FILTER (WHERE pid IS NOT NULL) AS total_documents_with_pid,
                {pdf_asset_count} AS documents_with_pdf_assets,
                {image_like_count} AS image_like_documents
            FROM documents
            """
        )
    ).fetchone()
    chunk_columns = _get_table_columns(db, "document_chunks")
    chunk_counts = None
    if chunk_columns:
        chunk_counts = db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE embedding_vector IS NOT NULL) AS embedded_chunks,
                    COUNT(DISTINCT document_id) FILTER (WHERE embedding_vector IS NOT NULL) AS documents_represented_by_chunks
                FROM document_chunks
                """
            )
        ).fetchone()

    return {
        "total_documents": int(counts.total_documents or 0),
        "documents_with_extracted_text": int(counts.documents_with_extracted_text or 0),
        "documents_with_embeddings": int(counts.documents_with_embeddings or 0),
        "total_documents_with_pid": int(counts.total_documents_with_pid or 0),
        "documents_with_pdf_assets": int(counts.documents_with_pdf_assets or 0),
        "image_like_documents": int(counts.image_like_documents or 0),
        "embedded_chunks": int(chunk_counts.embedded_chunks or 0) if chunk_counts else 0,
        "documents_represented_by_chunks": int(chunk_counts.documents_represented_by_chunks or 0) if chunk_counts else 0,
    }


def _build_evidence_surface_scope(point_type: str, total_candidates: int, returned_points: int, distinct_pids: int, db_counts: Dict) -> Dict:
    return {
        "label": "current ML-ingested / public GraphQL evidence surface",
        **SCOPED_MISSINGNESS_V02_BASELINE,
        "total_documents_in_db": db_counts["total_documents"],
        "documents_with_extracted_text": db_counts["documents_with_extracted_text"],
        "documents_with_embeddings": db_counts["documents_with_embeddings"],
        "embedded_chunks": db_counts["embedded_chunks"],
        "documents_represented_by_chunks": db_counts["documents_represented_by_chunks"],
        "distinct_pids_represented": distinct_pids,
        "total_candidates": total_candidates,
        "returned_points": returned_points,
        "point_type": point_type,
        "scope_note": "This projection represents the current ML-ingested evidence surface, not the total DDR archive.",
    }


def _empty_umap_response(point_type: str, message: str, source: str, total_candidates: int = 0):
    db = LocalSessionLocal()
    try:
        db_counts = _get_database_scope_counts(db)
    finally:
        db.close()

    return {
        "points": [],
        "clusters": [],
        "metadata": {
            "embedding_model": None,
            "umap_model": None,
            "projection_method": "none",
            "generated_at": datetime.utcnow().isoformat(),
            "point_type": point_type,
            "is_demo": False,
            "source": source,
            "total_candidates": total_candidates,
            "returned_points": 0,
            "evidence_surface_scope": _build_evidence_surface_scope(point_type, total_candidates, 0, 0, db_counts),
            "interpretation_warnings": _build_interpretation_warnings(),
            "message": message,
        },
        "message": message,
    }


def _get_completed_semantic_atlas_projection(db):
    try:
        return db.execute(text("""
            SELECT projection_id, embedding_set_id, algorithm, library_version,
                   random_seed, parameters_json, input_count, input_ordering_sha256,
                   numerical_tolerance, completed_at
            FROM semantic_atlas_projections
            WHERE status = 'completed'
            ORDER BY completed_at DESC, created_at DESC
            LIMIT 1
        """)).mappings().first()
    except Exception:
        logger.info("Completed Semantic Atlas projection is not available; using legacy projection path")
        return None


@router.post("/semantic-neighbourhood")
async def get_semantic_neighbourhood(request: SemanticNeighbourhoodRequest):
    """Return nearest archival passages for one focal embedded chunk."""
    db = LocalSessionLocal()
    try:
        projection = _get_completed_semantic_atlas_projection(db)
        if not projection:
            raise HTTPException(status_code=404, detail="No completed Semantic Atlas projection is available.")
        focal = db.execute(text("""
            SELECT embedding::text AS embedding
            FROM semantic_chunk_embeddings
            WHERE embedding_set_id = :embedding_set_id
                AND chunk_id = :chunk_id
                AND status = 'embedded'
        """), {"embedding_set_id": projection["embedding_set_id"], "chunk_id": request.focal_chunk_id}).mappings().first()
        if not focal:
            raise HTTPException(status_code=404, detail="The selected source is not represented in the completed embedding set.")
        chunk_columns = _get_table_columns(db, "document_chunks")
        citation_select = "dc.citation" if "citation" in chunk_columns else "NULL::jsonb AS citation"
        rows = db.execute(text(_semantic_neighbour_query("1 - (sce.embedding <=> CAST(:query_vector AS vector))", citation_select)), {
            "embedding_set_id": projection["embedding_set_id"],
            "projection_id": projection["projection_id"],
            "query_vector": focal["embedding"],
            "size": request.size + 1,
        }).fetchall()
        points = [_semantic_point_payload(row) for row in rows if row.chunk_id != request.focal_chunk_id][:request.size]
        return {
            "focal_chunk_id": request.focal_chunk_id,
            "neighbours": points,
            "metadata": {
                "embedding_set_id": projection["embedding_set_id"],
                "projection_id": projection["projection_id"],
                "method": "cosine similarity in the completed embedding space",
                "interpretation_limit": "Computational proximity identifies passages for archival investigation; it does not establish a historical relationship.",
            },
        }
    finally:
        db.close()


@router.post("/critical-probe")
async def run_critical_probe(request: CriticalProbeRequest):
    """Return archival passages nearest to a researcher-supplied critical concept."""
    db = LocalSessionLocal()
    try:
        projection = _get_completed_semantic_atlas_projection(db)
        if not projection:
            raise HTTPException(status_code=404, detail="No completed Semantic Atlas projection is available.")
        embedding_set = db.execute(text("""
            SELECT model_name, vector_dimensions
            FROM semantic_embedding_sets
            WHERE embedding_set_id = :embedding_set_id AND status = 'completed'
        """), {"embedding_set_id": projection["embedding_set_id"]}).mappings().first()
        if not embedding_set:
            raise HTTPException(status_code=404, detail="The completed embedding set is unavailable.")
        query_vector = _load_probe_embedding(embedding_set["model_name"], request.concept.strip())
        if len(query_vector) != embedding_set["vector_dimensions"]:
            raise HTTPException(status_code=503, detail="The critical probe model does not match the completed embedding dimensions.")
        chunk_columns = _get_table_columns(db, "document_chunks")
        citation_select = "dc.citation" if "citation" in chunk_columns else "NULL::jsonb AS citation"
        rows = db.execute(text(_semantic_neighbour_query("1 - (sce.embedding <=> CAST(:query_vector AS vector))", citation_select)), {
            "embedding_set_id": projection["embedding_set_id"],
            "projection_id": projection["projection_id"],
            "query_vector": "[" + ",".join(str(value) for value in query_vector) + "]",
            "size": request.size,
        }).fetchall()
        return {
            "concept": request.concept.strip(),
            "passages": [_semantic_point_payload(row) for row in rows],
            "metadata": {
                "embedding_model": embedding_set["model_name"],
                "vector_dimensions": embedding_set["vector_dimensions"],
                "embedding_set_id": projection["embedding_set_id"],
                "projection_id": projection["projection_id"],
                "interpretation_limit": "Critical lens supplied by researcher. Computational proximity indicates material for investigation, not confirmation of the proposition.",
            },
        }
    finally:
        db.close()


@router.post("/umap/challenge")
async def challenge_umap_projection(request: UmapChallengeRequest):
    """Generate a temporary, parameterised projection without altering the persisted Atlas."""
    db = LocalSessionLocal()
    try:
        projection = _get_completed_semantic_atlas_projection(db)
        if not projection:
            raise HTTPException(status_code=404, detail="No completed Semantic Atlas projection is available.")
        chunk_columns = _get_table_columns(db, "document_chunks")
        citation_select = "dc.citation" if "citation" in chunk_columns else "NULL::jsonb AS citation"
        rows = db.execute(text(f"""
            SELECT dc.document_id, dc.chunk_id, d.pid, d.title,
                   COALESCE(dc.publication_year, d.publication_year) AS year,
                   d.file_type, dc.chunk_type, {citation_select}, dc.key_concepts,
                   dc.chunk_text, dc.source_page, dc.source_section,
                   sce.embedding::text AS embedding
            FROM semantic_chunk_embeddings sce
            JOIN document_chunks dc ON dc.chunk_id = sce.chunk_id
            JOIN documents d ON d.document_id = dc.document_id
            WHERE sce.embedding_set_id = :embedding_set_id
              AND sce.status = 'embedded'
              AND d.pid IS NOT NULL
                            AND {DDR_DOCUMENT_SQL_SCOPE}
            ORDER BY dc.chunk_id
            LIMIT :sample_size
        """), {"embedding_set_id": projection["embedding_set_id"], "sample_size": request.sample_size}).fetchall()
        vectors = [_vector_to_list(row.embedding) for row in rows]
        valid_rows_and_vectors = [(row, vector) for row, vector in zip(rows, vectors) if vector]
        if len(valid_rows_and_vectors) < 3:
            raise HTTPException(status_code=409, detail="At least three embedded passages are required to challenge this map.")
        valid_rows, valid_vectors = zip(*valid_rows_and_vectors)
        coordinates, method = _project_vectors(
            list(valid_vectors),
            random_seed=request.random_seed,
            n_neighbors=request.n_neighbors,
            min_dist=request.min_dist,
        )
        points = []
        for row, coordinates_pair in zip(valid_rows, coordinates):
            concepts = _extract_key_concepts(row.key_concepts)
            cluster_label = concepts[0] if concepts else "Unclustered"
            points.append({
                "id": row.chunk_id,
                "document_id": row.document_id,
                "chunk_id": row.chunk_id,
                "pid": row.pid,
                "title": row.title or "Untitled trace",
                "x": float(coordinates_pair[0]),
                "y": float(coordinates_pair[1]),
                "year": int(row.year) if row.year is not None else None,
                "source_type": _infer_source_type(row.file_type, row.chunk_type, row.citation),
                "themes": concepts,
                "cluster_id": _slugify_cluster(cluster_label),
                "cluster_label": cluster_label,
                "excerpt": _clean_excerpt(row.chunk_text),
                "source_page": row.source_page,
                "source_section": row.source_section,
            })
        return {
            "points": points,
            "metadata": {
                "projection_method": method,
                "embedding_set_id": projection["embedding_set_id"],
                "source_projection_id": projection["projection_id"],
                "random_seed": request.random_seed,
                "n_neighbors": min(request.n_neighbors, max(2, len(points) - 1)),
                "min_dist": request.min_dist,
                "sample_size": len(points),
                "interpretation_limit": "This temporary projection tests computational sensitivity. Apparent relationships must be checked against source evidence and other parameter settings.",
            },
        }
    finally:
        db.close()


@router.get("/document-network")
async def get_document_network(
    min_similarity: float = Query(0.6, ge=0.0, le=1.0),
    max_nodes: int = Query(50, ge=10, le=200),
    theme_filter: Optional[str] = None
):
    """
    Generate network graph data for D3 force-directed layout.
    
    Returns:
        - nodes: Documents with metadata
        - links: Similarity relationships
        - clusters: Theme-based groupings
    
    Carbon component: Custom D3 visualization
    """
    db = LocalSessionLocal()
    
    try:
        # Get documents with embeddings
        query = """
        SELECT 
            document_id,
            pid,
            title,
            pdf_count,
            ml_themes,
            publication_year,
            ml_confidence,
            embeddings
        FROM documents
        WHERE embeddings IS NOT NULL
            AND pid IS NOT NULL
        """
        
        if theme_filter:
            query += f" AND '{theme_filter}' = ANY(ml_themes)"
        
        query += f" LIMIT {max_nodes}"
        
        result = db.execute(text(query))
        documents = result.fetchall()
        
        if not documents:
            return {"nodes": [], "links": [], "clusters": []}
        
        # Build nodes
        nodes = []
        doc_map = {}
        
        for i, doc in enumerate(documents):
            node = {
                "id": doc.document_id,
                "pid": doc.pid,
                "name": doc.title,
                "pdfCount": doc.pdf_count or 0,
                "themes": doc.ml_themes or [],
                "year": doc.publication_year,
                "confidence": float(doc.ml_confidence) if doc.ml_confidence else 0.0,
                "group": doc.ml_themes[0] if doc.ml_themes else "uncategorized",
                "size": (doc.pdf_count or 1) * 3  # Node size based on PDF count
            }
            nodes.append(node)
            doc_map[doc.document_id] = i
        
        # Calculate similarity links
        links = []
        link_query = """
        SELECT 
            document_id_a,
            document_id_b,
            combined_score
        FROM document_similarities
        WHERE combined_score >= :min_similarity
            AND (document_id_a IN :doc_ids OR document_id_b IN :doc_ids)
        ORDER BY combined_score DESC
        LIMIT 200
        """
        
        doc_ids = tuple([d.document_id for d in documents])
        if len(doc_ids) > 1:
            similarity_result = db.execute(
                text(link_query),
                {"min_similarity": min_similarity, "doc_ids": doc_ids}
            )
            
            for row in similarity_result:
                if row.document_id_a in doc_map and row.document_id_b in doc_map:
                    links.append({
                        "source": row.document_id_a,
                        "target": row.document_id_b,
                        "value": float(row.combined_score),
                        "strength": float(row.combined_score)
                    })
        
        # Get theme clusters
        cluster_query = """
        SELECT 
            theme_name,
            description,
            color_hex,
            document_count
        FROM theme_clusters
        ORDER BY document_count DESC
        """
        
        cluster_result = db.execute(text(cluster_query))
        clusters = [
            {
                "id": row.theme_name,
                "name": row.theme_name,
                "description": row.description,
                "color": row.color_hex or "#0f62fe",
                "count": row.document_count
            }
            for row in cluster_result
        ]
        
        return {
            "nodes": nodes,
            "links": links,
            "clusters": clusters,
            "metadata": {
                "totalDocuments": len(nodes),
                "totalLinks": len(links),
                "minSimilarity": min_similarity,
                "generatedAt": datetime.now().isoformat()
            }
        }
        
    finally:
        db.close()


@router.get("/theme-distribution")
async def get_theme_distribution():
    """
    Theme distribution data for Carbon DonutChart/BarChart.
    
    Returns Carbon-compatible dataset structure.
    """
    db = LocalSessionLocal()
    
    try:
        query = """
        SELECT 
            unnest(ml_themes) as theme,
            COUNT(*) as count
        FROM documents
        WHERE ml_themes IS NOT NULL
            AND pid IS NOT NULL
        GROUP BY theme
        ORDER BY count DESC
        LIMIT 15
        """
        
        result = db.execute(text(query))
        data = result.fetchall()
        
        # Carbon color palette
        carbon_colors = [
            "#0f62fe", "#8a3ffc", "#33b1ff", "#24a148", "#f1c21b",
            "#da1e28", "#ff832b", "#fa4d56", "#570408", "#198038",
            "#002d9c", "#ee538b", "#b28600", "#009d9a", "#005d5d"
        ]
        
        return {
            "labels": [row.theme for row in data],
            "datasets": [{
                "label": "Documents per Theme",
                "data": [int(row.count) for row in data],
                "backgroundColor": carbon_colors[:len(data)]
            }],
            "total": sum(row.count for row in data)
        }
        
    finally:
        db.close()


@router.get("/temporal-trends")
async def get_temporal_trends(
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
):
    """
    Time series data for Carbon LineChart.
    Shows document publication trends over time.
    """
    db = LocalSessionLocal()
    
    try:
        query = """
        SELECT 
            publication_year as year,
            COUNT(*) as document_count,
            SUM(pdf_count) as total_pdfs,
            AVG(ml_confidence) as avg_confidence,
            array_agg(DISTINCT ml_themes[1]) FILTER (WHERE ml_themes IS NOT NULL) as top_themes
        FROM documents
        WHERE publication_year IS NOT NULL
            AND pid IS NOT NULL
        """
        
        if start_year:
            query += f" AND publication_year >= {start_year}"
        if end_year:
            query += f" AND publication_year <= {end_year}"
        
        query += """
        GROUP BY publication_year
        ORDER BY publication_year
        """
        
        result = db.execute(text(query))
        data = result.fetchall()
        
        return {
            "labels": [str(row.year) for row in data],
            "datasets": [
                {
                    "label": "Documents Published",
                    "data": [int(row.document_count) for row in data],
                    "borderColor": "#0f62fe",
                    "backgroundColor": "rgba(15, 98, 254, 0.1)"
                },
                {
                    "label": "Total PDFs",
                    "data": [int(row.total_pdfs or 0) for row in data],
                    "borderColor": "#8a3ffc",
                    "backgroundColor": "rgba(138, 63, 252, 0.1)"
                }
            ],
            "trends": [
                {
                    "year": row.year,
                    "themes": row.top_themes or []
                }
                for row in data
            ]
        }
        
    finally:
        db.close()


@router.get("/entity-network")
async def get_entity_network(
    entity_type: Optional[str] = None,
    min_frequency: int = 2,
    max_entities: int = 100
):
    """
    Entity co-occurrence network for D3 visualization.
    Shows relationships between people, organizations, concepts.
    """
    db = LocalSessionLocal()
    
    try:
        # Get top entities
        entity_query = """
        SELECT 
            e.id,
            e.entity_text,
            e.entity_type,
            e.frequency,
            COUNT(DISTINCT de.document_id) as document_count
        FROM entities e
        JOIN document_entities de ON e.id = de.entity_id
        WHERE e.frequency >= :min_freq
        """
        
        if entity_type:
            entity_query += f" AND e.entity_type = '{entity_type}'"
        
        entity_query += """
        GROUP BY e.id, e.entity_text, e.entity_type, e.frequency
        ORDER BY e.frequency DESC
        LIMIT :max_entities
        """
        
        result = db.execute(
            text(entity_query),
            {"min_freq": min_frequency, "max_entities": max_entities}
        )
        entities = result.fetchall()
        
        nodes = [
            {
                "id": f"entity_{e.id}",
                "name": e.entity_text,
                "type": e.entity_type,
                "frequency": e.frequency,
                "documentCount": e.document_count,
                "size": min(e.frequency * 2, 50)
            }
            for e in entities
        ]
        
        # Get co-occurrence links
        entity_ids = tuple([e.id for e in entities])
        
        if len(entity_ids) > 1:
            cooccurrence_query = """
            SELECT 
                de1.entity_id as entity_a,
                de2.entity_id as entity_b,
                COUNT(*) as cooccurrence_count
            FROM document_entities de1
            JOIN document_entities de2 
                ON de1.document_id = de2.document_id
                AND de1.entity_id < de2.entity_id
            WHERE de1.entity_id IN :entity_ids
                AND de2.entity_id IN :entity_ids
            GROUP BY de1.entity_id, de2.entity_id
            HAVING COUNT(*) >= 2
            ORDER BY cooccurrence_count DESC
            LIMIT 200
            """
            
            link_result = db.execute(
                text(cooccurrence_query),
                {"entity_ids": entity_ids}
            )
            
            links = [
                {
                    "source": f"entity_{row.entity_a}",
                    "target": f"entity_{row.entity_b}",
                    "value": row.cooccurrence_count,
                    "strength": min(row.cooccurrence_count / 10, 1.0)
                }
                for row in link_result
            ]
        else:
            links = []
        
        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "entityType": entity_type or "all",
                "totalEntities": len(nodes),
                "totalLinks": len(links)
            }
        }
        
    finally:
        db.close()


@router.get("/umap")
async def get_umap_projection(
    point_type: str = Query("chunks", pattern="^(chunks|documents)$"),
    color_by: Optional[str] = Query("cluster"),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    theme: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    include_missingness: bool = Query(True),
    limit: int = Query(1000, ge=1, le=5000),
    refresh: bool = Query(False),
):
    """
    Project DDR embeddings into a 2D visual-analytics space.
    Uses chunk embeddings where available and falls back to PCA when UMAP is unavailable.
    """
    if point_type not in {"chunks", "documents"}:
        raise HTTPException(status_code=400, detail="Unsupported point_type. Use 'chunks' or 'documents'.")

    db = LocalSessionLocal()

    try:
        db_counts = _get_database_scope_counts(db)
        document_chunk_columns = _get_table_columns(db, "document_chunks") if point_type == "chunks" else set()
        projection_point_columns = _get_table_columns(db, "semantic_atlas_projection_points")
        if point_type == "chunks" and not document_chunk_columns:
            return _empty_umap_response(
                "chunks",
                "Chunk embeddings are not provisioned in the current database. This is a local system coverage state, not evidence of archival absence.",
                "document_chunks",
            )
        chunk_citation_select = "dc.citation" if "citation" in document_chunk_columns else "NULL::jsonb AS citation"
        chunk_title_expr = "COALESCE(d.title, dc.citation->>'title', 'Untitled trace')" if "citation" in document_chunk_columns else "COALESCE(d.title, 'Untitled trace')"
        projection_z_select = "pp.z" if "z" in projection_point_columns else "NULL::double precision AS z"

        atlas_projection = _get_completed_semantic_atlas_projection(db) if point_type == "chunks" else None
        if atlas_projection:
            query = f"""
            SELECT
                dc.chunk_id AS point_id,
                dc.document_id,
                dc.chunk_id,
                d.pid,
                {chunk_title_expr} AS title,
                COALESCE(dc.publication_year, d.publication_year) AS year,
                d.file_type,
                d.filename,
                d.pdf_count,
                (NULLIF(BTRIM(COALESCE(d.extracted_text, '')), '') IS NOT NULL) AS has_document_extracted_text,
                (NULLIF(BTRIM(COALESCE(d.authority_data::text, '')), '') IS NOT NULL) AS has_authority_context,
                d.has_diagrams,
                dc.chunk_type,
                {chunk_citation_select},
                dc.key_concepts,
                NULL::jsonb AS entities,
                NULL::double precision AS confidence,
                dc.drift_score,
                LEFT(dc.chunk_text, 240) AS excerpt,
                (NULLIF(BTRIM(COALESCE(dc.chunk_text, '')), '') IS NOT NULL) AS has_chunk_text,
                dc.source_page,
                dc.source_section,
                pp.x,
                pp.y,
                {projection_z_select}
            FROM semantic_atlas_projection_points pp
            JOIN document_chunks dc ON dc.chunk_id = pp.chunk_id
            JOIN documents d ON d.document_id = dc.document_id
            WHERE pp.projection_id = :projection_id
                AND d.pid IS NOT NULL
                AND {DDR_DOCUMENT_SQL_SCOPE}
            """
            params = {"projection_id": atlas_projection["projection_id"], "limit": limit}
            if year_min is not None:
                query += " AND COALESCE(dc.publication_year, d.publication_year) >= :year_min"
                params["year_min"] = year_min
            if year_max is not None:
                query += " AND COALESCE(dc.publication_year, d.publication_year) <= :year_max"
                params["year_max"] = year_max
            if theme:
                query += " AND LOWER(COALESCE(dc.key_concepts::text, '')) LIKE LOWER(:theme_pattern)"
                params["theme_pattern"] = f"%{theme}%"
            query += " ORDER BY dc.chunk_id LIMIT :limit"
            rows = db.execute(text(query), params).fetchall()
            points = []
            for row in rows:
                concepts = _extract_key_concepts(row.key_concepts)
                inferred_source_type = _infer_source_type(row.file_type, row.chunk_type, row.citation)
                if source_type and inferred_source_type != source_type:
                    continue
                record = {
                    "id": row.point_id,
                    "document_id": row.document_id,
                    "chunk_id": row.chunk_id,
                    "pid": row.pid,
                    "title": row.title or "Untitled trace",
                    "year": int(row.year) if row.year is not None else None,
                    "source_type": inferred_source_type,
                    "themes": concepts,
                    "entities": _extract_entities(row.entities),
                    "confidence": float(row.confidence) if row.confidence is not None else None,
                    "drift_score": float(row.drift_score) if row.drift_score is not None else None,
                    "excerpt": row.excerpt,
                    "filename": row.filename,
                    "pdf_count": int(row.pdf_count or 0),
                    "has_diagrams": int(row.has_diagrams or 0),
                    "document_extracted_text": "available" if row.has_document_extracted_text else None,
                    "authority_data": "available" if row.has_authority_context else None,
                    "has_embedding": True,
                    "chunk_text": "available" if row.has_chunk_text else None,
                    "source_page": row.source_page,
                    "source_section": row.source_section,
                }
                evidence_surface = _infer_evidence_surface(record)
                missingness = _build_missingness(record, evidence_surface) if include_missingness else None
                cluster_label = concepts[0] if concepts else "Unclustered"
                points.append(
                    {
                    "id": record["id"],
                    "document_id": record["document_id"],
                    "chunk_id": record["chunk_id"],
                    "pid": record["pid"],
                    "title": record["title"],
                    "x": float(row.x),
                    "y": float(row.y),
                    "z": float(row.z) if row.z is not None else None,
                    "year": record["year"],
                    "source_type": record["source_type"],
                    "themes": record["themes"],
                    "entities": record["entities"],
                    "cluster_id": _slugify_cluster(cluster_label),
                    "cluster_label": cluster_label,
                    "confidence": record["confidence"],
                    "drift_score": record["drift_score"],
                    "excerpt": record["excerpt"],
                    "evidence_surface": evidence_surface,
                    "missingness": missingness,
                    }
                )
            clusters = _summarize_clusters(points)
            distinct_pids = len({point["pid"] for point in points if point.get("pid")})
            atlas_document_count = db.execute(text("""
                SELECT COUNT(DISTINCT document_id)
                FROM semantic_chunk_embeddings
                WHERE embedding_set_id = :embedding_set_id AND status = 'embedded'
            """), {"embedding_set_id": atlas_projection["embedding_set_id"]}).scalar()
            atlas_db_counts = {
                **db_counts,
                "embedded_chunks": int(atlas_projection["input_count"]),
                "documents_with_embeddings": int(atlas_document_count or 0),
                "documents_represented_by_chunks": int(atlas_document_count or 0),
            }
            interpretation_warnings = _build_interpretation_warnings()
            interpretation_warnings.append(
                "Coordinates come from a completed, versioned projection; proximity is a visual hypothesis, not evidence of a historical relationship."
            )
            return {
                "points": points,
                "clusters": clusters,
                "metadata": {
                    "embedding_model": "BAAI/bge-m3",
                    "umap_model": "persisted-umap",
                    "projection_method": atlas_projection["algorithm"],
                    "generated_at": atlas_projection["completed_at"].isoformat() if atlas_projection["completed_at"] else None,
                    "point_type": point_type,
                    "is_demo": False,
                    "source": "semantic_atlas_projection_points",
                    "embedding_set_id": atlas_projection["embedding_set_id"],
                    "projection_id": atlas_projection["projection_id"],
                    "projection_parameters": atlas_projection["parameters_json"],
                    "projection_library_version": atlas_projection["library_version"],
                    "projection_random_seed": atlas_projection["random_seed"],
                    "projection_input_ordering_sha256": atlas_projection["input_ordering_sha256"],
                    "projection_numerical_tolerance": atlas_projection["numerical_tolerance"],
                    "total_candidates": atlas_projection["input_count"],
                    "returned_points": len(points),
                    "distinct_pids_represented": distinct_pids,
                    "evidence_surface_scope": _build_evidence_surface_scope(point_type, atlas_projection["input_count"], len(points), distinct_pids, atlas_db_counts),
                    "interpretation_warnings": interpretation_warnings,
                    "message": None,
                },
                "message": None,
            }

        if point_type == "documents":
            if not _supports_document_embeddings(db):
                message = "Document-level embeddings are not available; use point_type=chunks."
                logger.info("UMAP requested for documents, but embeddings column is unavailable")
                return _empty_umap_response("documents", message, "documents.embeddings", 0)

            query = """
            SELECT
                d.document_id AS point_id,
                d.document_id,
                NULL AS chunk_id,
                d.pid,
                d.title,
                d.publication_year AS year,
                d.file_type,
                d.filename,
                d.pdf_count,
                d.extracted_text AS document_extracted_text,
                d.authority_data,
                d.processing_status,
                d.has_diagrams,
                d.doc_metadata,
                NULL AS chunk_type,
                NULL AS citation,
                d.ml_themes AS key_concepts,
                d.ml_entities AS entities,
                d.ml_confidence AS confidence,
                NULL AS drift_score,
                d.ml_summary AS chunk_text,
                NULL AS source_page,
                NULL AS source_section,
                d.embeddings::text AS embedding_vector,
                NULL AS embedding_model
            FROM documents d
            WHERE d.embeddings IS NOT NULL
                AND d.pid IS NOT NULL
                AND {DDR_DOCUMENT_SQL_SCOPE}
            """
            params = {"limit": limit}
            source = "documents.embeddings"

            if year_min is not None:
                query += " AND d.publication_year >= :year_min"
                params["year_min"] = year_min
            if year_max is not None:
                query += " AND d.publication_year <= :year_max"
                params["year_max"] = year_max
            if theme:
                query += " AND EXISTS (SELECT 1 FROM unnest(d.ml_themes) AS theme_item WHERE LOWER(theme_item) LIKE LOWER(:theme_pattern))"
                params["theme_pattern"] = f"%{theme}%"

            query += " ORDER BY d.publication_year NULLS LAST, d.document_id LIMIT :limit"
        else:
            query = f"""
            SELECT
                dc.chunk_id AS point_id,
                dc.document_id,
                dc.chunk_id,
                d.pid,
                {chunk_title_expr} AS title,
                COALESCE(dc.publication_year, d.publication_year) AS year,
                d.file_type,
                d.filename,
                d.pdf_count,
                d.extracted_text AS document_extracted_text,
                d.authority_data,
                d.processing_status,
                d.has_diagrams,
                d.doc_metadata,
                dc.chunk_type,
                {chunk_citation_select},
                dc.key_concepts,
                NULL::jsonb AS entities,
                NULL::double precision AS confidence,
                dc.drift_score,
                dc.chunk_text,
                dc.source_page,
                dc.source_section,
                dc.embedding_vector::text AS embedding_vector,
                dc.embedding_model
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE dc.embedding_vector IS NOT NULL
                AND d.pid IS NOT NULL
                AND {DDR_DOCUMENT_SQL_SCOPE}
            """
            params = {"limit": limit}
            source = "document_chunks.embedding_vector"

            if year_min is not None:
                query += " AND COALESCE(dc.publication_year, d.publication_year) >= :year_min"
                params["year_min"] = year_min
            if year_max is not None:
                query += " AND COALESCE(dc.publication_year, d.publication_year) <= :year_max"
                params["year_max"] = year_max
            if theme:
                query += " AND LOWER(COALESCE(dc.key_concepts::text, '')) LIKE LOWER(:theme_pattern)"
                params["theme_pattern"] = f"%{theme}%"

            query += " ORDER BY COALESCE(dc.publication_year, d.publication_year) NULLS LAST, dc.chunk_id LIMIT :limit"

        try:
            result = db.execute(text(query), params)
            rows = result.fetchall()
        except Exception as exc:
            logger.exception("UMAP query failed")
            raise HTTPException(status_code=500, detail=f"Database query failed for UMAP projection: {exc}") from exc

        total_candidates = len(rows)

        if total_candidates == 0:
            message = (
                "Document-level embeddings are not available; use point_type=chunks."
                if point_type == "documents"
                else "No embedded chunks/documents available for UMAP projection."
            )
            logger.warning("UMAP requested with no embedding candidates for point_type=%s", point_type)
            return _empty_umap_response(point_type, message, source, total_candidates)

        records = []
        vectors = []

        for row in rows:
            concepts = _extract_key_concepts(row.key_concepts)
            inferred_source_type = _infer_source_type(row.file_type, row.chunk_type, row.citation)
            if source_type and inferred_source_type != source_type:
                continue

            vector = _vector_to_list(row.embedding_vector)
            if not vector:
                continue

            records.append(
                {
                    "id": row.point_id,
                    "document_id": row.document_id,
                    "chunk_id": row.chunk_id,
                    "pid": row.pid,
                    "title": row.title or "Untitled trace",
                    "year": int(row.year) if row.year is not None else None,
                    "source_type": inferred_source_type,
                    "themes": concepts,
                    "entities": _extract_entities(row.entities),
                    "confidence": float(row.confidence) if row.confidence is not None else None,
                    "drift_score": float(row.drift_score) if row.drift_score is not None else None,
                    "excerpt": row.excerpt,
                    "embedding_model": row.embedding_model,
                    "filename": row.filename,
                    "pdf_count": int(row.pdf_count or 0),
                    "document_extracted_text": row.document_extracted_text,
                    "authority_data": row.authority_data,
                    "processing_status": row.processing_status,
                    "has_diagrams": int(row.has_diagrams or 0),
                    "doc_metadata": row.doc_metadata,
                    "chunk_text": row.chunk_text,
                    "source_page": row.source_page,
                    "source_section": row.source_section,
                    "has_embedding": True,
                }
            )
            vectors.append(vector)

        if len(records) == 0:
            message = "No embedded chunks/documents available for UMAP projection."
            logger.warning("UMAP candidates existed before source_type filtering, but no rows remained")
            return _empty_umap_response(point_type, message, source, total_candidates)

        try:
            coordinates, projection_method = _project_vectors(vectors)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Projection dependency failure")
            raise HTTPException(status_code=501, detail=f"Projection dependency unavailable: {exc}") from exc

        if projection_method is None:
            raise HTTPException(status_code=501, detail="Projection dependency unavailable")

        points = []
        for record, coords in zip(records, coordinates):
            cluster_label = record["themes"][0] if record["themes"] else "Unclustered"
            cluster_id = _slugify_cluster(cluster_label)
            evidence_surface = _infer_evidence_surface(record)
            missingness = _build_missingness(record, evidence_surface) if include_missingness else None
            points.append(
                {
                    "id": record["id"],
                    "document_id": record["document_id"],
                    "chunk_id": record["chunk_id"],
                    "pid": record["pid"],
                    "title": record["title"],
                    "x": float(coords[0]),
                    "y": float(coords[1]),
                    "year": record["year"],
                    "source_type": record["source_type"],
                    "themes": record["themes"],
                    "entities": record["entities"],
                    "cluster_id": cluster_id,
                    "cluster_label": cluster_label,
                    "confidence": record["confidence"],
                    "drift_score": record["drift_score"],
                    "excerpt": record["excerpt"],
                    "evidence_surface": evidence_surface,
                    "missingness": missingness,
                }
            )

        clusters = _summarize_clusters(points)
        message = None
        if len(points) == 1:
            message = "Only one embedded point is available; projection is not meaningful yet."

        embedding_model = next((record["embedding_model"] for record in records if record["embedding_model"]), None)
        distinct_pids = len({point["pid"] for point in points if point.get("pid")})
        interpretation_warnings = _build_interpretation_warnings()
        if color_by == "cluster":
            interpretation_warnings.append(
                "Cluster labels are lightweight groupings derived from available key concepts unless a persisted clustering model is present."
            )

        logger.info(
            "Generated UMAP projection candidates=%s returned=%s method=%s point_type=%s refresh=%s color_by=%s",
            total_candidates,
            len(points),
            projection_method,
            point_type,
            refresh,
            color_by,
        )

        return {
            "points": points,
            "clusters": clusters,
            "metadata": {
                "embedding_model": embedding_model,
                "umap_model": projection_method,
                "projection_method": projection_method,
                "generated_at": datetime.utcnow().isoformat(),
                "point_type": point_type,
                "is_demo": False,
                "source": source,
                "total_candidates": total_candidates,
                "returned_points": len(points),
                "distinct_pids_represented": distinct_pids,
                "evidence_surface_scope": _build_evidence_surface_scope(point_type, total_candidates, len(points), distinct_pids, db_counts),
                "interpretation_warnings": interpretation_warnings,
                "message": message,
            },
            "message": message,
        }

    finally:
        db.close()


@router.get("/dashboard-stats")
async def get_dashboard_stats():
    """
    Real-time ML processing statistics for dashboard.
    Optimized using materialized view.
    """
    db = LocalSessionLocal()
    
    try:
        # Get cached stats
        stats_query = "SELECT * FROM ml_dashboard_stats"
        result = db.execute(text(stats_query))
        stats = result.fetchone()
        corpus_status = get_corpus_status(db)

        # Count files that are actually indexed in chunked corpus.
        ingested_pdf_query = """
        SELECT COUNT(DISTINCT source_filename) AS ingested_pdf_files
        FROM document_chunks
        WHERE source_filename IS NOT NULL
            AND LOWER(source_filename) LIKE '%.pdf'
        """
        ingested_pdf_result = db.execute(text(ingested_pdf_query)).fetchone()
        ingested_pdf_files = int(ingested_pdf_result.ingested_pdf_files or 0)
        
        # Get recent processing activity
        activity_query = """
        SELECT 
            stage,
            status,
            COUNT(*) as count,
            AVG(duration_seconds) as avg_duration
        FROM ml_processing_log
        WHERE started_at > NOW() - INTERVAL '24 hours'
        GROUP BY stage, status
        ORDER BY stage, status
        """
        
        activity_result = db.execute(text(activity_query))
        
        return {
            "overview": {
                "totalDocuments": stats.total_documents,
                "corpusStatus": corpus_status,
                # UI uses this as model-ingested source PDF count.
                "totalPdfs": ingested_pdf_files,
                "totalPdfAssets": stats.total_pdfs,
                "totalPages": stats.total_pages,
                "yearRange": stats.year_range
            },
            "mlProcessing": {
                "documentsWithEmbeddings": stats.documents_with_embeddings,
                "documentsWithSummaries": stats.documents_with_summaries,
                "documentsWithEntities": stats.documents_with_entities,
                "avgConfidence": float(stats.avg_confidence) if stats.avg_confidence else 0.0,
                "completionRate": round(
                    (stats.documents_with_embeddings / stats.total_documents * 100) 
                    if stats.total_documents > 0 else 0, 2
                )
            },
            "themes": {
                "uniqueThemes": stats.unique_themes
            },
            "recentActivity": stats.recent_activity or [],
            "lastUpdated": stats.last_updated.isoformat() if stats.last_updated else None
        }
        
    finally:
        db.close()


@router.get("/dashboard-analytical-surface")
async def get_dashboard_analytical_surface():
    """Return current frozen-corpus measures for the landing-page analytical surface."""
    corpus_version = "corpus_f40d78dbce52"
    db = LocalSessionLocal()

    try:
        composition = db.execute(text("""
            WITH current_documents AS (
                SELECT document_id, use_for_ml
                FROM documents
                WHERE corpus_version = :corpus_version
            ), chunked_documents AS (
                SELECT DISTINCT document_id
                FROM document_chunks
                WHERE corpus_version = :corpus_version
            )
            SELECT
                (SELECT COUNT(*) FROM current_documents) AS current_assets,
                (SELECT COUNT(*) FROM current_documents WHERE use_for_ml = 1) AS ml_eligible_assets,
                (SELECT COUNT(*) FROM current_documents WHERE use_for_ml = 0) AS ml_excluded_assets,
                (SELECT COUNT(*) FROM chunked_documents) AS controlled_ingestible_sources,
                (SELECT COUNT(*) FROM document_chunks WHERE corpus_version = :corpus_version) AS current_chunks
        """), {"corpus_version": corpus_version}).mappings().one()

        density = db.execute(text("""
            SELECT d.document_id, d.title, COUNT(*) AS chunk_count
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE dc.corpus_version = :corpus_version
            GROUP BY d.document_id, d.title
            ORDER BY chunk_count DESC, d.title
            LIMIT 12
        """), {"corpus_version": corpus_version}).mappings().all()

        temporal = db.execute(text("""
            SELECT publication_year, COUNT(*) AS document_count
            FROM documents
            WHERE corpus_version = :corpus_version
                AND publication_year IS NOT NULL
            GROUP BY publication_year
            ORDER BY publication_year
        """), {"corpus_version": corpus_version}).mappings().all()
        undated = db.execute(text("""
            SELECT COUNT(*) AS document_count
            FROM documents
            WHERE corpus_version = :corpus_version
                AND publication_year IS NULL
        """), {"corpus_version": corpus_version}).scalar_one()

        runs = db.execute(text("""
            SELECT
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_runs,
                COUNT(*) FILTER (WHERE status = 'failed') AS bounded_failures,
                COUNT(assessment.run_id) AS assessed_runs
            FROM experiment_runs run
            LEFT JOIN experiment_run_assessments assessment ON assessment.run_id = run.run_id
        """)).mappings().one()

        return {
            "corpus_version": corpus_version,
            "composition": {
                "current_assets": int(composition["current_assets"] or 0),
                "controlled_ingestible_sources": int(composition["controlled_ingestible_sources"] or 0),
                "source_format_anomalies": max(0, int(composition["ml_eligible_assets"] or 0) - int(composition["controlled_ingestible_sources"] or 0)),
                "ml_excluded_assets": int(composition["ml_excluded_assets"] or 0),
                "current_chunks": int(composition["current_chunks"] or 0),
            },
            "density": [{"document_id": row["document_id"], "title": row["title"] or "Untitled document", "chunk_count": int(row["chunk_count"])} for row in density],
            "temporal": {
                "bins": [{"year": int(row["publication_year"]), "document_count": int(row["document_count"])} for row in temporal],
                "undated_documents": int(undated or 0),
            },
            "runs": {key: int(value or 0) for key, value in runs.items()},
        }
    finally:
        db.close()


@router.post("/refresh-stats")
async def refresh_dashboard_stats():
    """
    Manually trigger refresh of materialized view.
    Use after bulk ML processing.
    """
    db = LocalSessionLocal()
    
    try:
        db.execute(text("SELECT refresh_ml_dashboard_stats()"))
        db.commit()
        return {"status": "success", "message": "Dashboard stats refreshed"}
    finally:
        db.close()
