"""Inspectable PostgreSQL FTS retrieval for Turin validation runs."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.models.research_outputs import QueryRun, QueryRunChunk, QueryRunExport
from app.services.corpus_status_service import (
    ARCHIVE_RESOLUTION_RESOLVED_CURRENT,
    archive_resolution_status,
)
from app.services.metadata_roles import extract_metadata_roles


RANKING_FUNCTION = "ts_rank(search_tsv, websearch_to_tsquery('english', query))"


class QueryExpansion(BaseModel):
    value: str = Field(min_length=1)
    source: str = "researcher_supplied"
    authority_source: str | None = None
    authority_id: str | None = None
    authority_field: str | None = None
    authority_role: str | None = None
    authority_document_id: str | None = None


class RetrievalValidationRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    expansions: list[QueryExpansion] = Field(default_factory=list)
    pids: list[str] = Field(default_factory=list)
    corpus_version: str | None = None
    year_from: int | None = None
    year_to: int | None = None


def normalise_query(query: str) -> str:
    return " ".join(query.split())


def build_expanded_query(normalised_query: str, expansions: list[QueryExpansion]) -> str:
    values = [expansion.value.strip() for expansion in expansions if expansion.value.strip()]
    if not values:
        return normalised_query
    quoted_values = [f'"{value}"' if " " in value else value for value in values]
    return " OR ".join([normalised_query, *quoted_values])


def build_query_transparency(request: RetrievalValidationRequest) -> dict[str, Any]:
    normalised = normalise_query(request.query)
    expansions = [expansion.model_dump() for expansion in request.expansions]
    return {
        "original_query": request.query,
        "normalised_query": normalised,
        "expanded_query": build_expanded_query(normalised, request.expansions),
        "query_expansions": [expansion["value"] for expansion in expansions],
        "expansion_sources": expansions,
        "filters": {
            "pids": list(request.pids),
            "corpus_version": request.corpus_version,
            "year_from": request.year_from,
            "year_to": request.year_to,
        },
        "top_k": request.top_k,
        "ranking_function": RANKING_FUNCTION,
    }


def build_retrieval_diagnostics(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [result["score"] for result in results]
    result_count = len(results)
    document_counts: dict[str, int] = {}
    creators: set[str] = set()
    for result in results:
        document_id = result["document_id"]
        document_counts[document_id] = document_counts.get(document_id, 0) + 1
        creator = result["catalogue_metadata"].get("creator")
        if creator:
            creators.add(str(creator))

    dominant_count = max(document_counts.values(), default=0)
    archive_resolved_count = sum(
        result["archive_resolution_status"] == ARCHIVE_RESOLUTION_RESOLVED_CURRENT
        for result in results
    )
    provenance_incomplete = any(
        result["archive_resolution_status"] != ARCHIVE_RESOLUTION_RESOLVED_CURRENT
        or not result["provenance"].get("archive_record_pid")
        for result in results
    )
    notes: list[str] = []
    if result_count == 0:
        notes.append("No source passage was retrieved by this query. This is a retrieval-scope result, not evidence of historical absence.")
    if result_count and dominant_count / result_count >= 0.75 and result_count > 1:
        notes.append("Most returned passages come from one document; inspect evidence concentration before interpreting coverage.")
    if provenance_incomplete:
        notes.append("At least one returned passage lacks a current resolved archive provenance chain.")

    return {
        "result_count": result_count,
        "max_score": max(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "score_spread": (max(scores) - min(scores)) if scores else None,
        "unique_document_count": len(document_counts),
        "unique_creator_count": len(creators) if creators else None,
        "archive_resolved_result_count": archive_resolved_count,
        "unresolved_legacy_result_count": result_count - archive_resolved_count,
        "possible_low_recall": result_count == 0 or (bool(scores) and max(scores) < 0.05),
        "evidence_concentration": result_count > 1 and dominant_count / result_count >= 0.75,
        "retrieval_redundancy": result_count > len(document_counts),
        "provenance_incomplete": provenance_incomplete,
        "extraction_issue_present": False,
        "notes": notes,
    }


def _git_commit() -> str | None:
    try:
        repository_root = Path(__file__).resolve().parents[3]
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


class RetrievalValidationService:
    def _validate_expansions(self, db: Any, expansions: list[QueryExpansion]) -> None:
        for expansion in expansions:
            authority_fields = (
                expansion.authority_source,
                expansion.authority_field,
                expansion.authority_role,
                expansion.authority_document_id,
            )
            if not any(authority_fields):
                continue
            if expansion.authority_source == "database_authorities.ddr_projects":
                if not all((expansion.authority_id, expansion.authority_field, expansion.authority_role)):
                    raise ValueError("Project-authority expansion requires source, authority ID, field, and role.")
                if expansion.authority_field != "title" or expansion.authority_role != "controlled_query_expansion":
                    raise ValueError("Project-authority expansion must use the controlled project title.")
                project = db.execute(
                    text("""
                        SELECT 1 FROM database_authorities
                        WHERE authority_type = 'ddr_projects' AND authority_id = :authority_id
                    """),
                    {"authority_id": expansion.authority_id},
                ).first()
                if project is None:
                    raise ValueError("Project-authority expansion requires a resolved DDR project authority record.")
                continue
            if not all(authority_fields):
                raise ValueError("Authority-assisted expansion requires source, field, role, and resolved document identity.")
            if expansion.authority_role != "controlled_query_expansion":
                raise ValueError("Authority-assisted expansion must declare the controlled_query_expansion role.")
            document = db.execute(
                text(
                    """
                    SELECT archive_metadata_source, metadata_sync_status, archive_record_id,
                           archive_record_pid, asset_id, asset_pid, source_uri
                    FROM documents WHERE document_id = :document_id
                    """
                ),
                {"document_id": expansion.authority_document_id},
            ).mappings().first()
            if document is None or archive_resolution_status(SimpleNamespace(**document)) != ARCHIVE_RESOLUTION_RESOLVED_CURRENT:
                raise ValueError("Authority-assisted expansion requires an explicitly archive-resolved current document identity.")

    @staticmethod
    def _result_from_row(row: Any, rank: int) -> dict[str, Any]:
        document = SimpleNamespace(**dict(row))
        resolution_status = archive_resolution_status(document)
        authority_data = dict(row.get("authority_data") or {})
        authority_data.update(
            {
                "title": row.get("title"),
                "source_filename": row.get("filename"),
                "source_uri": row.get("source_uri"),
                "source_page": row.get("source_page"),
                "source_section": row.get("source_section"),
                "chunk_id": row.get("chunk_id"),
                "chunk_type": row.get("chunk_type"),
            }
        )
        if resolution_status == ARCHIVE_RESOLUTION_RESOLVED_CURRENT:
            authority_data.update(
                {
                    "authority_id": row.get("authority_id"),
                    "archive_record_id": row.get("archive_record_id"),
                    "archive_record_pid": row.get("archive_record_pid"),
                    "asset_id": row.get("asset_id"),
                    "asset_pid": row.get("asset_pid"),
                    "asset_id_or_asset_pid": row.get("asset_id_or_asset_pid"),
                    "pid": row.get("pid"),
                }
            )
        roles = extract_metadata_roles(authority_data)
        provenance = roles["retrieval_provenance"] if resolution_status == ARCHIVE_RESOLUTION_RESOLVED_CURRENT else {}
        chunk_metadata = dict(row.get("chunk_metadata") or {})
        page_start = row.get("source_page")
        page_end = chunk_metadata.get("page_end") or page_start
        return {
            "rank": rank,
            "score": float(row["score"]),
            "pid": row.get("pid"),
            "archive_record_pid": row.get("archive_record_pid") if resolution_status == ARCHIVE_RESOLUTION_RESOLVED_CURRENT else None,
            "document_id": row["document_id"],
            "archive_resolution_status": resolution_status,
            "title": row.get("title"),
            "page_start": page_start,
            "page_end": page_end,
            "chunk_id": row["chunk_id"],
            "chunk_sequence": row.get("chunk_index"),
            "text": row["chunk_text"],
            "included_in_context": True,
            "provenance": provenance,
            "catalogue_metadata": roles["catalogue_metadata"],
        }

    def retrieve(self, db: Any, request: RetrievalValidationRequest) -> dict[str, Any]:
        self._validate_expansions(db, request.expansions)
        transparency = build_query_transparency(request)
        filters = transparency["filters"]
        conditions = [
            "dc.search_tsv @@ websearch_to_tsquery('english', :query)",
            "d.use_for_ml = 1",
            "d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')",
        ]
        params: dict[str, Any] = {"query": transparency["expanded_query"], "limit": request.top_k}
        if filters["pids"]:
            conditions.append("d.pid = ANY(:pids)")
            params["pids"] = filters["pids"]
        if filters["corpus_version"] is not None:
            conditions.append("dc.corpus_version = :corpus_version")
            params["corpus_version"] = filters["corpus_version"]
        if filters["year_from"] is not None:
            conditions.append("dc.publication_year >= :year_from")
            params["year_from"] = filters["year_from"]
        if filters["year_to"] is not None:
            conditions.append("dc.publication_year <= :year_to")
            params["year_to"] = filters["year_to"]

        started = time.perf_counter()
        rows = db.execute(
            text(
                f"""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       NULLIF(to_jsonb(dc)->>'source_page', '')::integer AS source_page,
                       to_jsonb(dc)->>'source_section' AS source_section,
                       dc.chunk_metadata, d.pid, d.title, d.filename, d.authority_id,
                       d.authority_data, d.archive_record_id, d.archive_record_pid, d.asset_id,
                       d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :query)) AS score
                FROM document_chunks dc
                JOIN documents d ON d.document_id = dc.document_id
                WHERE {' AND '.join(conditions)}
                ORDER BY score DESC, dc.chunk_id ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        results = [self._result_from_row(row, index) for index, row in enumerate(rows, start=1)]
        diagnostics = build_retrieval_diagnostics(results)
        transparency["result_count"] = len(results)
        transparency["retrieval_duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return {
            "transparency": transparency,
            "results": results,
            "diagnostics": diagnostics,
            "corpus_versions": sorted({row.get("corpus_version") for row in rows if row.get("corpus_version")}),
        }

    def persist_validation_run(self, db: Any, request: RetrievalValidationRequest, retrieval: dict[str, Any]) -> dict[str, Any]:
        retrieval_run_id = f"retrieval-{uuid.uuid4().hex[:12]}"
        results = retrieval["results"]
        diagnostics = retrieval["diagnostics"]
        run = QueryRun(
            query_id=retrieval_run_id,
            prompt=request.query,
            mode="retrieval_validation",
            model="postgresql_fts",
            response=None,
            caveats=" ".join(diagnostics["notes"]) or None,
            failed_or_partial=not bool(results),
            failure_reason="No source passages retrieved by this query." if not results else None,
            retrieved_chunk_count=len(results),
            export_status="json",
        )
        db.add(run)
        db.flush()
        for result in results:
            db.add(
                QueryRunChunk(
                    query_id=retrieval_run_id,
                    chunk_id=result["chunk_id"],
                    document_id=result["document_id"],
                    page_range=str(result["page_start"]) if result["page_start"] is not None else None,
                    rank=result["rank"],
                    score=result["score"],
                    citation_text=None,
                    provenance_json=result["provenance"] or None,
                    source_metadata_json=result,
                )
            )
        corpus_versions = retrieval["corpus_versions"]
        record = {
            "retrieval_run_id": retrieval_run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corpus_version": corpus_versions[0] if len(corpus_versions) == 1 else None,
            "git_commit": _git_commit(),
            **retrieval["transparency"],
            "results": results,
            "diagnostics": diagnostics,
        }
        db.add(QueryRunExport(query_id=retrieval_run_id, export_type="json", export_payload=json.dumps(record, sort_keys=True)))
        db.commit()
        return record