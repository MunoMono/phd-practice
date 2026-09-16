"""Inspectable lexical planning for non-formal exploratory corpus queries."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.services.retrieval_validation_service import RetrievalValidationService


EXPLORATORY_STRATEGY = "exploratory_archive_retrieval_v3"
ARCHIVE_METADATA_SNAPSHOT_VERSION = "turin-archive-metadata-v1"
CANDIDATE_TOP_K = 15
PASSAGE_CANDIDATE_LIMIT = 50
METADATA_FIELD_WEIGHTS = {
    "title": 1.0,
    "caption": 0.95,
    "keywords": 0.9,
    "asset_label": 0.85,
    "record_title": 0.55,
    "date": 0.35,
    "location": 0.1,
}
LOW_INFORMATION_TERMS = {
    "how", "what", "which", "who", "is", "are", "was", "were", "the", "and", "or", "of", "in", "with", "to", "for",
    "represented", "aspects", "directly", "evidenced", "inferred", "across", "multiple", "documents", "document", "rather", "than",
    "role", "does", "do", "that", "this", "from", "about", "practice", "please", "show", "find",
}


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"['’]s\b", "", value.lower()).split())


def _terms(value: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9]+", value) if len(term) > 2 and term.lower() not in LOW_INFORMATION_TERMS]


class ExploratoryQueryPlanner:
    """Produces a bounded, deterministic lexical plan from natural-language input."""

    def build_plan(self, db: Any, query: str) -> dict[str, Any]:
        normalised = " ".join(query.split())
        query_text = _normalise(normalised)
        authority_rows = db.execute(text("SELECT authority_type, authority_id, label FROM database_authorities WHERE label IS NOT NULL ORDER BY authority_type, label")).mappings().all()
        resolved_entities = []
        entity_terms: set[str] = set()
        for row in authority_rows:
            label = str(row["label"])
            label_text = _normalise(label)
            if len(_terms(label)) >= 2 and label_text in query_text:
                resolved_entities.append({"label": label, "authority_type": row["authority_type"], "authority_id": str(row["authority_id"]), "source": "database_authorities"})
                entity_terms.update(_terms(label))
        resolved_entities = resolved_entities[:3]
        concepts = [term for term in _terms(normalised) if term not in entity_terms][:5]
        variants: list[dict[str, str]] = []

        def add(kind: str, value: str) -> None:
            if value and value not in {item["query"] for item in variants}:
                variants.append({"variant_id": f"variant-{len(variants) + 1}", "kind": kind, "query": value})

        for entity in resolved_entities:
            add("entity_anchor", f'"{entity["label"]}"')
        for entity in resolved_entities:
            for concept in concepts[:3]:
                add("entity_concept", f'"{entity["label"]}" {concept}')
        for quoted in re.findall(r'["“]([^"”]{3,120})["”]', normalised):
            add("quoted_phrase", f'"{quoted.strip()}"')
        for identifier in re.findall(r"\b(?:job|project)\s+(?:number\s+)?\d+\b", normalised, re.IGNORECASE):
            add("project_identifier", f'"{identifier}"')
        for index in range(0, len(concepts) - 1, 2):
            add("concept_pair", f"{concepts[index]} {concepts[index + 1]}")
        for concept in concepts[:3]:
            add("concept_anchor", concept)
        return {
            "query": query,
            "normalised_query": normalised,
            "strategy": EXPLORATORY_STRATEGY,
            "resolved_entities": resolved_entities,
            "concepts": concepts,
            "query_variants": variants[:10],
            "candidate_top_k": CANDIDATE_TOP_K,
            "score_threshold": 0.0,
        }


class ExploratoryRetrievalService:
    """Runs a transparent lexical plan without formal plans, authorizations, or persistence."""

    def __init__(self) -> None:
        self.planner = ExploratoryQueryPlanner()
        self.result_mapper = RetrievalValidationService()

    @staticmethod
    def canonical_asset_identity(candidate: dict[str, Any]) -> str:
        """Collapse technical derivatives to their governing documentary asset."""
        return str(candidate.get("asset_id") or candidate.get("asset_pid") or candidate["document_id"])

    @staticmethod
    def _apply_snapshot_identity(candidate: dict[str, Any], row: dict[str, Any]) -> None:
        metadata = dict(row.get("authority_data") or {})
        candidate["archive_record_pid"] = candidate.get("archive_record_pid") or metadata.get("record_pid")
        candidate["asset_pid"] = candidate.get("asset_pid") or metadata.get("asset_pid")
        candidate["asset_id"] = candidate.get("asset_id") or metadata.get("asset_id")
        candidate["asset_id_or_asset_pid"] = candidate.get("asset_id_or_asset_pid") or metadata.get("asset_id_or_asset_pid")

    @staticmethod
    def _metadata_matches(row: dict[str, Any], query: str) -> list[dict[str, str]]:
        metadata = dict(row.get("authority_data") or {})
        terms = set(_terms(query))
        fields = {
            "title": row.get("title"), "caption": metadata.get("caption"), "asset_label": metadata.get("master_label"),
            "keywords": metadata.get("keywords"), "record_title": metadata.get("record_title"),
            "date": metadata.get("date_text") or metadata.get("normalized_date"),
            "location": metadata.get("location_note") or metadata.get("location_repository"),
        }
        matches = []
        for field, value in fields.items():
            values = value if isinstance(value, list) else [value]
            for item in values:
                label = item.get("label") if isinstance(item, dict) else item
                label_text = str(label or "").strip()
                if label_text and terms.intersection(_terms(label_text)):
                    matches.append({"field": field, "value": label_text})
        return matches

    @staticmethod
    def _merge_source_candidate(candidates: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
        """Aggregate discovery signals by canonical asset, never by arbitrary chunk."""
        identity = ExploratoryRetrievalService.canonical_asset_identity(candidate)
        existing = candidates.get(identity)
        if existing is None:
            candidates[identity] = {
                **candidate,
                "source_nomination_score": candidate["text_score"] + candidate["metadata_score"],
                "source_nomination_channels": list(candidate["retrieval_channels"]),
            }
            return
        existing["text_score"] = max(existing.get("text_score", 0.0), candidate.get("text_score", 0.0))
        existing["metadata_score"] = max(existing.get("metadata_score", 0.0), candidate.get("metadata_score", 0.0))
        existing["source_nomination_score"] = existing["text_score"] + existing["metadata_score"]
        existing["source_nomination_channels"] = sorted(set(existing["source_nomination_channels"] + candidate["retrieval_channels"]))
        existing["metadata_matches"] = existing["metadata_matches"] + [match for match in candidate["metadata_matches"] if match not in existing["metadata_matches"]]
        existing["originating_query_variants"] = sorted(set(existing["originating_query_variants"] + candidate["originating_query_variants"]))
        if candidate.get("text_score", 0.0) > existing.get("selected_text_score", 0.0):
            candidate.update({key: existing[key] for key in ("metadata_score", "metadata_matches", "source_nomination_channels", "originating_query_variants", "source_nomination_score")})
            candidates[identity] = candidate

    @staticmethod
    def _select_diverse_sources(candidates: list[dict[str, Any]], selected_top_k: int) -> list[dict[str, Any]]:
        selected, selected_documents = [], set()
        for candidate in candidates:
            if candidate["document_id"] in selected_documents:
                continue
            selected.append(candidate)
            selected_documents.add(candidate["document_id"])
            if len(selected) == selected_top_k:
                return selected
        for candidate in candidates:
            if candidate not in selected:
                selected.append(candidate)
                if len(selected) == selected_top_k:
                    return selected
        return selected

    @staticmethod
    def _passage_quality(text_value: str) -> tuple[bool, list[str]]:
        text = " ".join(str(text_value or "").split())
        lower = text.lower()
        reasons: list[str] = []
        if "<!-- image -->" in lower or lower in {"[image]", "image"}:
            reasons.append("image_marker")
        if len(text) < 40:
            reasons.append("too_short")
        alphabetic = sum(character.isalpha() for character in text)
        if not text or alphabetic / max(len(text), 1) < 0.45:
            reasons.append("low_alphabetic_content")
        if len(_terms(text)) < 5:
            reasons.append("low_information")
        return not reasons, reasons

    @staticmethod
    def _select_best_passage(rows: list[dict[str, Any]], query_terms: set[str]) -> dict[str, Any] | None:
        """Choose a documentary passage on textual evidence, not source metadata."""
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            valid, exclusions = ExploratoryRetrievalService._passage_quality(str(row.get("chunk_text") or ""))
            if not valid:
                continue
            if float(row.get("score") or 0.0) <= 0:
                continue
            text_terms = set(_terms(str(row.get("chunk_text") or "")))
            section_terms = set(_terms(str(row.get("source_section") or "")))
            entity_matches = len(query_terms.intersection(text_terms))
            section_matches = len(query_terms.intersection(section_terms))
            passage_score = float(row.get("score") or 0.0) + entity_matches + section_matches * 0.25
            ranked.append((passage_score, {**row, "passage_score": passage_score, "passage_entity_matches": entity_matches, "passage_section_matches": section_matches, "passage_quality_exclusions": exclusions}))
        if not ranked:
            return None
        return max(ranked, key=lambda item: (item[0], str(item[1]["chunk_id"])))[1]

    def retrieve(self, db: Any, query: str, selected_top_k: int, corpus_version: str) -> dict[str, Any]:
        plan = self.planner.build_plan(db, query)
        candidates: dict[str, dict[str, Any]] = {}
        raw_match_count = policy_match_count = 0
        for variant in plan["query_variants"]:
            rows = db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       NULLIF(to_jsonb(dc)->>'source_page', '')::integer AS source_page,
                       to_jsonb(dc)->>'source_section' AS source_section, dc.chunk_metadata,
                       d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                       d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :query)) AS score
                FROM document_chunks dc JOIN documents d USING(document_id)
                WHERE dc.search_tsv @@ websearch_to_tsquery('english', :query)
                  AND d.use_for_ml = 1
                  AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                  AND dc.corpus_version = :corpus_version
                ORDER BY score DESC, dc.chunk_id ASC LIMIT :limit
            """), {"query": variant["query"], "corpus_version": corpus_version, "limit": CANDIDATE_TOP_K}).mappings().all()
            counts = db.execute(text("""
                SELECT count(*) FILTER (WHERE dc.search_tsv @@ websearch_to_tsquery('english', :query)) AS raw_count,
                       count(*) FILTER (WHERE dc.search_tsv @@ websearch_to_tsquery('english', :query)
                         AND d.use_for_ml = 1 AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                         AND dc.corpus_version = :corpus_version) AS policy_count
                FROM document_chunks dc JOIN documents d USING(document_id)
            """), {"query": variant["query"], "corpus_version": corpus_version}).mappings().one()
            raw_match_count += counts["raw_count"]
            policy_match_count += counts["policy_count"]
            for rank, row in enumerate(rows, start=1):
                mapped = self.result_mapper._result_from_row(row, rank)
                self._apply_snapshot_identity(mapped, row)
                mapped.update({"text_score": mapped["score"], "metadata_score": 0.0, "retrieval_channels": ["TEXT_MATCH"], "metadata_matches": [], "originating_query_variants": [variant["variant_id"]]})
                self._merge_source_candidate(candidates, mapped)
            metadata_rows = db.execute(text("""
                WITH metadata_hits AS (
                    SELECT d.*, ts_rank(
                        setweight(to_tsvector('simple', coalesce(d.title, '')), 'A') ||
                        setweight(to_tsvector('simple', coalesce(d.authority_data->>'caption', '')), 'A') ||
                        setweight(to_tsvector('simple', coalesce(d.authority_data->>'keywords', '')), 'A') ||
                        setweight(to_tsvector('simple', coalesce(d.authority_data->>'master_label', '')), 'B') ||
                        setweight(to_tsvector('simple', coalesce(d.authority_data->>'record_title', '')), 'C') ||
                        setweight(to_tsvector('simple', coalesce(d.authority_data->>'location_note', '')), 'D'),
                        websearch_to_tsquery('simple', :query)
                    ) AS metadata_score
                    FROM documents d
                    WHERE (setweight(to_tsvector('simple', coalesce(d.title, '')), 'A') ||
                           setweight(to_tsvector('simple', coalesce(d.authority_data->>'caption', '')), 'A') ||
                           setweight(to_tsvector('simple', coalesce(d.authority_data->>'keywords', '')), 'A') ||
                           setweight(to_tsvector('simple', coalesce(d.authority_data->>'master_label', '')), 'B') ||
                           setweight(to_tsvector('simple', coalesce(d.authority_data->>'record_title', '')), 'C') ||
                           setweight(to_tsvector('simple', coalesce(d.authority_data->>'location_note', '')), 'D')) @@ websearch_to_tsquery('simple', :query)
                      AND d.use_for_ml = 1 AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                      AND d.corpus_version = :corpus_version
                )
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type, dc.source_page, dc.source_section, dc.chunk_metadata,
                       m.pid, m.title, m.filename, m.authority_id, m.authority_data, m.archive_record_id, m.archive_record_pid, m.asset_id, m.asset_pid,
                       m.asset_id_or_asset_pid, m.source_uri, m.archive_metadata_source, m.metadata_sync_status, m.corpus_version, m.metadata_score AS score
                FROM metadata_hits m JOIN LATERAL (SELECT * FROM document_chunks WHERE document_id=m.document_id AND corpus_version=:corpus_version ORDER BY chunk_index, chunk_id LIMIT 1) dc ON true
                ORDER BY m.metadata_score DESC, m.document_id LIMIT :limit
            """), {"query": variant["query"], "corpus_version": corpus_version, "limit": CANDIDATE_TOP_K}).mappings().all()
            for rank, row in enumerate(metadata_rows, start=1):
                mapped = self.result_mapper._result_from_row(row, rank)
                self._apply_snapshot_identity(mapped, row)
                metadata_matches = self._metadata_matches(row, variant["query"])
                mapped.update({"text_score": 0.0, "metadata_score": mapped["score"], "retrieval_channels": ["METADATA_MATCH"], "metadata_matches": metadata_matches, "originating_query_variants": [variant["variant_id"]]})
                self._merge_source_candidate(candidates, mapped)
        nominated = sorted(candidates.values(), key=lambda item: (-item["source_nomination_score"], item["document_id"]))
        selected_sources = self._select_diverse_sources(nominated, len(nominated))
        selected = []
        passage_query = " OR ".join([item["label"] for item in plan["resolved_entities"]] + plan["concepts"])
        query_terms = set(_terms(" ".join([item["label"] for item in plan["resolved_entities"]] + plan["concepts"])))
        for source in selected_sources:
            passage_rows = db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       NULLIF(to_jsonb(dc)->>'source_page', '')::integer AS source_page,
                       to_jsonb(dc)->>'source_section' AS source_section, dc.chunk_metadata,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :passage_query)) AS score,
                       d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                       d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version
                FROM document_chunks dc JOIN documents d USING(document_id)
                WHERE dc.document_id = :document_id
                  AND dc.corpus_version = :corpus_version
                  AND d.use_for_ml = 1
                  AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                ORDER BY score DESC, dc.chunk_id ASC LIMIT :limit
            """), {"document_id": source["document_id"], "corpus_version": corpus_version, "passage_query": passage_query or query, "limit": PASSAGE_CANDIDATE_LIMIT}).mappings().all()
            passage = self._select_best_passage([dict(row) for row in passage_rows], query_terms)
            if passage is None:
                continue
            mapped = self.result_mapper._result_from_row(passage, len(selected) + 1)
            self._apply_snapshot_identity(mapped, passage)
            mapped.update({
                "score": passage["passage_score"],
                "text_score": float(passage.get("score") or 0.0),
                "metadata_score": source["metadata_score"],
                "source_nomination_score": source["source_nomination_score"],
                "passage_score": passage["passage_score"],
                "source_nomination_channels": source["source_nomination_channels"],
                "passage_evidence_channel": "DIRECT_TEXT_MATCH" if passage["passage_entity_matches"] else "CONTEXTUAL_TEXT_MATCH",
                "retrieval_channels": source["source_nomination_channels"],
                "metadata_matches": source["metadata_matches"],
                "originating_query_variants": source["originating_query_variants"],
                "combined_score": passage["passage_score"],
                "retrieval_match_type": "TEXT_AND_METADATA_NOMINATED" if len(source["source_nomination_channels"]) == 2 else ("TEXT_NOMINATED" if "TEXT_MATCH" in source["source_nomination_channels"] else "METADATA_NOMINATED"),
            })
            selected.append(mapped)
            if len(selected) == selected_top_k:
                break
        diagnostic_state = "RETRIEVED" if selected else "ZERO_LEXICAL_MATCHES" if raw_match_count == 0 else "FILTERED_OUT" if policy_match_count == 0 else "CANDIDATES_BELOW_THRESHOLD"
        plan.update({"metadata_snapshot_version": ARCHIVE_METADATA_SNAPSHOT_VERSION, "metadata_field_weights": METADATA_FIELD_WEIGHTS, "candidate_count": len(nominated), "selected_count": len(selected), "fusion_strategy": "source_nomination_then_within_source_passage_selection", "source_diversity_strategy": "strongest_canonical_source_then_quality_gated_passage", "diagnostic_state": diagnostic_state})
        metadata_count = sum("METADATA_MATCH" in item["source_nomination_channels"] for item in nominated)
        return {"transparency": plan, "results": selected, "diagnostics": {"result_count": len(selected), "candidate_count": len(nominated), "text_candidate_count": sum("TEXT_MATCH" in item["source_nomination_channels"] for item in nominated), "metadata_candidate_count": metadata_count, "raw_lexical_match_count": raw_match_count, "policy_eligible_match_count": policy_match_count, "diagnostic_state": diagnostic_state}}