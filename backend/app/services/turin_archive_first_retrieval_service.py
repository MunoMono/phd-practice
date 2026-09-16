"""Archive-first, model-neutral retrieval for interactive Turin interrogation."""

from __future__ import annotations

import re
from typing import Any, Mapping

from sqlalchemy import bindparam, text

from app.services.exploratory_retrieval_service import ExploratoryQueryPlanner, ExploratoryRetrievalService, _terms
from app.services.ml_policy import parse_ml_pages
from app.services.retrieval_validation_service import RetrievalValidationService
from app.services.turin_question_policy import matching_turin_question_policy


ARCHIVE_FIRST_RETRIEVAL_VERSION = "turin-archive-first-retrieval-v1"
ARCHIVE_ASSET_SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"
MAX_ARCHIVE_CANDIDATES = 40
PASSAGES_PER_SOURCE = 3
MAX_DOCUMENTARY_QUOTED_CONCEPT_SOURCES = 3
ENTITY_ANCHOR_SCORE = 10
SOURCE_FAMILY_TOPIC_MATCH_SCORE = 10
SOURCE_FAMILY_FIELDS = {"record_title", "box_title", "collection_title", "preset_groups"}


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _values(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item.get("label") if isinstance(item, dict) else item) for item in value if item]
    return [str(value)]


class TurinArchiveFirstRetrievalService:
    """Nominate governed archive assets before inspecting their Docling text."""

    def __init__(self) -> None:
        self.planner = ExploratoryQueryPlanner()
        self.mapper = RetrievalValidationService()

    @staticmethod
    def _candidate_matches(asset: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
        query_terms = set(_terms(str(plan["normalised_query"])))
        exact_anchors = [_normalise(entity["label"]) for entity in plan["resolved_entities"]]
        entity_terms = set().union(*(_terms(anchor) for anchor in exact_anchors)) if exact_anchors else set()
        topic_terms = query_terms - entity_terms
        fields = {
            "record_title": asset.get("record_title"),
            "attached_media_title": asset.get("attached_media_title"),
            "label": asset.get("label"),
            "keywords": asset.get("keywords"),
            "people": asset.get("people"),
            "projects": asset.get("projects"),
            "box_title": asset.get("box_title"),
            "collection_title": asset.get("collection_title"),
            "source_type": asset.get("source_type"),
            "preset_groups": asset.get("preset_groups"),
            "display_date": asset.get("display_date"),
            "exact_project_title": asset.get("exact_project_title"),
            "exact_job_id": asset.get("exact_job_id"),
            "controlled_aliases": asset.get("controlled_aliases"),
        }
        reasons, matched_keywords, matched_authorities, matched_projects = [], [], [], []
        score = 0
        entity_matched = False
        for field, raw_value in fields.items():
            for value in _values(raw_value):
                normalised = _normalise(value)
                terms = set(_terms(value))
                exact = any(anchor and anchor in normalised for anchor in exact_anchors)
                overlap = sorted(topic_terms.intersection(terms))
                if not exact and not overlap:
                    continue
                if exact and not entity_matched:
                    score += ENTITY_ANCHOR_SCORE
                    entity_matched = True
                    reasons.append({"field": field, "value": value, "match": "exact_anchor"})
                elif exact:
                    reasons.append({"field": field, "value": value, "match": "exact_anchor_reinforcement"})
                if overlap:
                    overlap_score = len(overlap)
                    if field in SOURCE_FAMILY_FIELDS and len(overlap) >= 2:
                        overlap_score += len(overlap) * SOURCE_FAMILY_TOPIC_MATCH_SCORE
                        match = "source_family_topic_alignment"
                    else:
                        match = "controlled_term_overlap"
                    score += overlap_score
                    reasons.append({"field": field, "value": value, "match": match, "terms": overlap})
                if field == "keywords":
                    matched_keywords.append(value)
                elif field in {"people", "controlled_aliases"}:
                    matched_authorities.append(value)
                elif field in {"projects", "exact_project_title", "exact_job_id"}:
                    matched_projects.append(value)
        return {
            "score": score,
            "nomination_reasons": reasons,
            "matched_keywords": sorted(set(matched_keywords)),
            "matched_authorities": sorted(set(matched_authorities)),
            "matched_projects": sorted(set(matched_projects)),
        }

    @staticmethod
    def _page_permitted(page: int | None, ml_pages: str | None) -> bool:
        if _normalise(ml_pages) in {"", "all_pages"}:
            return True
        parsed = parse_ml_pages(ml_pages)
        return not parsed["is_restricted"] or page is None or page in (parsed["allowed_pages"] or [])

    @staticmethod
    def _is_oral_history_asset(asset: Mapping[str, Any]) -> bool:
        source_description = " ".join(str(asset.get(field) or "") for field in (
            "source_type", "record_title", "attached_media_title", "label", "preset_groups",
        )).lower()
        return "oral history" in source_description or "interview" in source_description

    @classmethod
    def _source_family(cls, asset: Mapping[str, Any]) -> str:
        return "oral_history" if cls._is_oral_history_asset(asset) else "documentary"

    @staticmethod
    def _asset_identity(value: Mapping[str, Any]) -> str:
        return str(value.get("asset_pid") or value.get("asset_id") or "")

    @classmethod
    def _source_family_diagnostics(cls, required_families: set[str], assets: list[Mapping[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
        families_by_asset = {cls._asset_identity(asset): cls._source_family(asset) for asset in assets}
        selected_families = {
            families_by_asset[cls._asset_identity(result)]
            for result in results
            if cls._asset_identity(result) in families_by_asset
        }
        unmet = sorted(required_families - selected_families)
        return {
            "required": sorted(required_families),
            "selected": sorted(selected_families),
            "requirements_satisfied": not unmet,
            "unmet": unmet,
        }

    @classmethod
    def _authority_asset_coverage(cls, assets: list[Mapping[str, Any]], plan: Mapping[str, Any], results: list[Mapping[str, Any]], required: bool) -> dict[str, Any]:
        resolved_entities = list(plan.get("resolved_entities") or [])
        linked_assets: dict[str, set[str]] = {}
        for entity in resolved_entities:
            label = _normalise(entity.get("label"))
            if not label:
                continue
            linked_assets[label] = {
                cls._asset_identity(asset)
                for asset in assets
                if asset.get("use_for_ml") is True
                and any(label in _normalise(value) for field in ("people", "controlled_aliases") for value in _values(asset.get(field)))
            }
        all_linked_assets = set().union(*linked_assets.values()) if linked_assets else set()
        selected_assets = {cls._asset_identity(result) for result in results}
        coverage_status = "NOT_REQUIRED"
        if required:
            coverage_status = "COMPLETE" if all_linked_assets else "CONTROLLED_LINKAGE_UNAVAILABLE"
        return {
            "review_required": required,
            "coverage_status": coverage_status,
            "resolved_authorities": [
                {"authority_type": entity.get("authority_type"), "authority_id": entity.get("authority_id"), "label": entity.get("label")}
                for entity in resolved_entities
            ],
            "controlled_linked_asset_ids": sorted(all_linked_assets),
            "controlled_linked_asset_count": len(all_linked_assets),
            "selected_controlled_linked_asset_count": len(all_linked_assets & selected_assets),
        }

    @classmethod
    def _oral_history_coverage(cls, assets: list[Mapping[str, Any]], nominations: list[Mapping[str, Any]], results: list[Mapping[str, Any]], required: bool) -> dict[str, Any]:
        eligible_asset_ids = {
            str(asset.get("asset_pid") or asset.get("asset_id"))
            for asset in assets
            if asset.get("use_for_ml") is True and cls._is_oral_history_asset(asset)
        }
        nominated_asset_ids = {
            str(item.get("asset_pid") or item.get("asset_id"))
            for item in nominations
            if str(item.get("asset_pid") or item.get("asset_id")) in eligible_asset_ids
        }
        selected_asset_ids = {
            str(result.get("asset_pid") or result.get("asset_id"))
            for result in results
            if str(result.get("asset_pid") or result.get("asset_id")) in eligible_asset_ids
        }
        return {
            "review_required": required,
            "eligible_assets_checked": len(eligible_asset_ids),
            "nominated": len(nominated_asset_ids),
            "selected": len(selected_asset_ids),
            "excluded_for_relevance": len(eligible_asset_ids - nominated_asset_ids),
        }

    def _asset_rows(self, db: Any) -> list[dict[str, Any]]:
        rows = db.execute(text("""
            SELECT record_pid, attached_media_pid, asset_pid, asset_id, label,
                   display_date, normalized_date, use_for_ml, ml_pages, source_type,
                   record_title, attached_media_title, keywords, people, projects,
                   box_title, collection_title, exact_project_title, exact_job_id,
                   controlled_aliases, preset_groups, source_snapshot_version
            FROM turin_archive_asset_snapshots
            WHERE source_snapshot_version = :snapshot_version
            ORDER BY asset_pid, asset_id
        """), {"snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION}).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _quoted_concepts(question: str) -> list[str]:
        return [
            " ".join(match.split())
            for groups in re.findall(r'“([^”]{3,120})”|"([^"]{3,120})"|‘([^’]{3,120})’', question)
            for match in groups
            if match
            if len(_terms(match)) >= 2
        ]

    def _documentary_quoted_concept_results(
        self,
        db: Any,
        question: str,
        corpus_version: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Preserve distinct documentary formulations of an explicitly named concept."""
        concepts = self._quoted_concepts(question)
        if not concepts or limit < 1:
            return []
        query_terms = set(_terms(question))
        phrase_query = " OR ".join(f'"{concept}"' for concept in concepts)
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                   ts_rank(dc.search_tsv, websearch_to_tsquery('english', :phrase_query)) AS score
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.search_tsv @@ websearch_to_tsquery('english', :phrase_query)
              AND d.use_for_ml = 1
              AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
              AND dc.corpus_version = :corpus_version
            ORDER BY score DESC, dc.chunk_id ASC
            LIMIT :chunk_limit
        """), {"phrase_query": phrase_query, "corpus_version": corpus_version, "chunk_limit": limit * 30}).mappings().all()
        by_document: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_document.setdefault(str(row["document_id"]), []).append(dict(row))
        results = []
        for document_id in sorted(by_document):
            passage = ExploratoryRetrievalService._select_best_passage(by_document[document_id], query_terms)
            if passage is None:
                continue
            mapped = self.mapper._result_from_row({**passage, "score": passage["passage_score"]}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, passage)
            results.append({
                **mapped,
                "archive_nomination": {"nomination_type": "DOCUMENTARY_QUOTED_CONCEPT", "matched_concepts": concepts},
                "retrieval_match_type": "DOCUMENTARY_QUOTED_CONCEPT_SUPPLEMENT",
                "metadata_is_documentary_evidence": False,
            })
            if len(results) == limit:
                break
        return results

    def _configured_document_page_results(self, db: Any, question: str, corpus_version: str) -> list[dict[str, Any]]:
        """Retrieve one stable passage for each page explicitly reserved by a policy."""
        policy = matching_turin_question_policy(question)
        if policy is None or policy.reservation_type != "CONFIGURED_DOCUMENT_PAGES":
            return []
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.corpus_version = :corpus_version
              AND (dc.document_id, dc.source_page) IN :document_pages
            ORDER BY dc.document_id, dc.chunk_id
        """), {"corpus_version": corpus_version, "document_pages": policy.document_pages}).mappings().all()
        by_document_page: dict[tuple[str, int], dict[str, Any]] = {}
        for row in rows:
            key = (str(row["document_id"]), int(row["source_page"]))
            by_document_page.setdefault(key, dict(row))
        results = []
        for document_page in policy.document_pages:
            row = by_document_page.get(document_page)
            if row is None:
                return []
            mapped = self.mapper._result_from_row({**row, "score": 100 - len(results)}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, row)
            results.append({
                **mapped,
                "archive_nomination": {"nomination_type": policy.reservation_type, "policy_id": policy.policy_id, "policy_version": "turin-question-policy-v1"},
                "retrieval_match_type": "CONFIGURED_DOCUMENT_PAGE_RESERVATION",
                "metadata_is_documentary_evidence": False,
            })
        return results

    def _configured_reservation_results(self, db: Any, question: str) -> list[dict[str, Any]]:
        policy = matching_turin_question_policy(question)
        if policy is None or not policy.chunk_ids:
            return []
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.chunk_id IN :chunk_ids
        """), {"chunk_ids": policy.chunk_ids}).mappings().all()
        by_chunk = {str(row["chunk_id"]): dict(row) for row in rows}
        if len(by_chunk) != len(policy.chunk_ids):
            return []
        results = []
        for chunk_id in policy.chunk_ids:
            row = by_chunk[chunk_id]
            mapped = self.mapper._result_from_row({**row, "score": 100 - len(results)}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, row)
            results.append({**mapped, "archive_nomination": {"nomination_type": policy.reservation_type, "policy_id": policy.policy_id, "policy_version": "turin-question-policy-v1"}, "retrieval_match_type": "CONFIGURED_QUESTION_POLICY_RESERVATION", "metadata_is_documentary_evidence": False})
        return results

    @staticmethod
    def _availability(db: Any, asset: Mapping[str, Any], corpus_version: str) -> dict[str, Any]:
        document = db.execute(text("""
            SELECT d.document_id, d.source_uri, d.source_path, d.processing_status,
                   d.ml_policy_status,
                   EXISTS (
                     SELECT 1 FROM document_chunks dc
                     WHERE dc.document_id = d.document_id AND dc.corpus_version = :corpus_version
                   ) AS docling_text_available
            FROM documents d
                        WHERE d.asset_pid = :asset_pid OR d.asset_id = :asset_id
                             OR d.asset_id_or_asset_pid IN (:asset_pid, :asset_id)
            ORDER BY d.document_id
            LIMIT 1
        """), {"corpus_version": corpus_version, "asset_pid": asset.get("asset_pid"), "asset_id": asset.get("asset_id")}).mappings().first()
        if asset.get("use_for_ml") is not True:
            return {"classification": "ARCHIVAL_CONTEXT_ONLY", "document_id": None, "docling_text_available": False}
        if document is None:
            return {"classification": "CORPUS_REPRESENTATION_GAP", "document_id": None, "docling_text_available": False}
        if not document["docling_text_available"]:
            return {"classification": "DOCLING_TEXT_MISSING", "document_id": document["document_id"], "docling_text_available": False}
        return {"classification": "DOCLING_TEXT_AVAILABLE", "document_id": document["document_id"], "docling_text_available": True}

    def retrieve(self, db: Any, question: str, selected_top_k: int, corpus_version: str) -> dict[str, Any]:
        plan = self.planner.build_plan(db, question)
        policy = matching_turin_question_policy(question)
        source_selection = policy.source_selection or {} if policy else {}
        required_source_families = set(source_selection.get("required_source_families", []))
        assets = self._asset_rows(db)
        nominations = []
        for asset in assets:
            matches = self._candidate_matches(asset, plan)
            if matches["score"]:
                nominations.append({
                    "record_pid": asset.get("record_pid"), "attached_media_pid": asset.get("attached_media_pid"),
                    "asset_pid": asset.get("asset_pid"), "asset_id": asset.get("asset_id"), "label": asset.get("label"),
                    "display_date": asset.get("display_date"), "normalized_date": asset.get("normalized_date"),
                    "use_for_ml": asset.get("use_for_ml"), "ml_pages": asset.get("ml_pages"), **matches,
                    "availability": self._availability(db, asset, corpus_version),
                })
        nominations.sort(key=lambda item: (-item["score"], str(item.get("asset_pid") or item.get("asset_id"))))
        nominations = nominations[:MAX_ARCHIVE_CANDIDATES]
        query_terms = set(_terms(question))
        results = self._configured_document_page_results(db, question, corpus_version)
        if not results:
            results = self._configured_reservation_results(db, question)
        if not results:
            results = self._documentary_quoted_concept_results(
                db, question, corpus_version, min(MAX_DOCUMENTARY_QUOTED_CONCEPT_SOURCES, selected_top_k)
            )
        selected_document_ids = {result["document_id"] for result in results}
        selected_asset_ids = {self._asset_identity(result) for result in results}
        selected_families = {
            self._source_family(asset) for asset in assets
            if self._asset_identity(asset) in selected_asset_ids
        }
        ordered_nominations = sorted(
            nominations,
            key=lambda item: (
                0 if self._source_family(item) in required_source_families - selected_families else 1,
                -item["score"], str(item.get("asset_pid") or item.get("asset_id")),
            ),
        )
        for nomination in ordered_nominations:
            availability = nomination["availability"]
            if not availability["docling_text_available"]:
                continue
            chunk_rows = db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       dc.source_page, dc.source_section, dc.chunk_metadata,
                       d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                       d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :question)) AS score
                FROM document_chunks dc JOIN documents d USING(document_id)
                WHERE dc.document_id = :document_id AND dc.corpus_version = :corpus_version
                ORDER BY score DESC, dc.chunk_id ASC
            """), {"document_id": availability["document_id"], "corpus_version": corpus_version, "question": question}).mappings().all()
            permitted = [dict(row) for row in chunk_rows if self._page_permitted(row.get("source_page"), nomination["ml_pages"])]
            passage = ExploratoryRetrievalService._select_best_passage(permitted, query_terms)
            if passage is None:
                nomination["availability"] = {**availability, "classification": "DOCUMENTARY_EVIDENCE_INSUFFICIENT"}
                continue
            if passage["document_id"] in selected_document_ids:
                continue
            mapped = self.mapper._result_from_row({**passage, "score": passage["passage_score"]}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, passage)
            results.append({**mapped, "archive_nomination": nomination, "retrieval_match_type": "ARCHIVE_FIRST_WITHIN_SOURCE_PASSAGE", "metadata_is_documentary_evidence": False})
            selected_document_ids.add(passage["document_id"])
            selected_families.add(self._source_family(nomination))
            if len(results) == selected_top_k:
                break
        archival_context_only = [item for item in nominations if item["availability"]["classification"] == "ARCHIVAL_CONTEXT_ONLY"]
        gaps = [item for item in nominations if item["availability"]["classification"] == "CORPUS_REPRESENTATION_GAP"]
        oral_history_coverage = self._oral_history_coverage(
            assets, nominations, results,
            required=bool((source_selection.get("oral_history") or {}).get("review_required")),
        )
        source_family_diagnostics = self._source_family_diagnostics(required_source_families, assets, results)
        authority_asset_coverage = self._authority_asset_coverage(
            assets, plan, results,
            required=bool((source_selection.get("authority_expansion") or {}).get("review_required")),
        )
        return {
            "results": results,
            "transparency": {**plan, "strategy": ARCHIVE_FIRST_RETRIEVAL_VERSION, "asset_snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION, "source_nomination_unit": "canonical_digital_asset", "global_corpus_competition_before_nomination": False},
            "diagnostics": {"archive_candidate_count": len(nominations), "ml_eligible_candidate_count": sum(item["use_for_ml"] is True for item in nominations), "materialised_candidate_count": sum(item["availability"]["docling_text_available"] for item in nominations), "retrieved_documentary_source_count": len(results), "corpus_representation_gaps": len(gaps), "oral_history_coverage": oral_history_coverage, "source_family_diversity": source_family_diagnostics, "authority_asset_coverage": authority_asset_coverage},
            "archival_discovery": nominations,
            "document_availability": [{"asset_pid": item["asset_pid"], "asset_id": item["asset_id"], "label": item["label"], **item["availability"]} for item in nominations],
            "archival_context_only": archival_context_only,
            "corpus_representation_gaps": gaps,
        }

    def retrieve_selected_documents(
        self, db: Any, question: str, document_ids: list[str], corpus_version: str
    ) -> dict[str, Any]:
        """Retrieve the best permitted passage from each explicitly selected document."""
        documents = db.execute(text("""
            SELECT document_id, pid, title, filename, authority_id, authority_data,
                   archive_record_id, archive_record_pid, asset_id, asset_pid,
                   asset_id_or_asset_pid, source_uri, archive_metadata_source,
                   metadata_sync_status, ml_policy_status, ml_page_scope
            FROM documents
            WHERE document_id IN :document_ids AND corpus_version = :corpus_version
            ORDER BY document_id
        """).bindparams(bindparam("document_ids", expanding=True)), {
            "document_ids": document_ids, "corpus_version": corpus_version,
        }).mappings().all()
        found_ids = {row["document_id"] for row in documents}
        missing_ids = sorted(set(document_ids) - found_ids)
        if missing_ids:
            raise ValueError(f"Selected document IDs are unavailable in the active corpus: {', '.join(missing_ids)}")
        excluded = [row["document_id"] for row in documents if row["ml_policy_status"] not in {"eligible_unrestricted", "eligible_page_restricted"}]
        if excluded:
            raise ValueError(f"Selected documents are not eligible for model interrogation: {', '.join(excluded)}")

        query_terms = set(_terms(question))
        results, availability = [], []
        for rank, document in enumerate(documents, start=1):
            chunk_rows = db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       dc.source_page, dc.source_section, dc.chunk_metadata,
                       d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                       d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :question)) AS score
                FROM document_chunks dc JOIN documents d USING(document_id)
                WHERE dc.document_id = :document_id AND dc.corpus_version = :corpus_version
                ORDER BY score DESC, dc.chunk_id ASC
            """), {"document_id": document["document_id"], "corpus_version": corpus_version, "question": question}).mappings().all()
            permitted = [dict(row) for row in chunk_rows if self._page_permitted(row.get("source_page"), document["ml_page_scope"])]
            passage = ExploratoryRetrievalService._select_best_passage(permitted, query_terms)
            if passage is None:
                availability.append({"document_id": document["document_id"], "title": document["title"], "classification": "DOCUMENTARY_EVIDENCE_INSUFFICIENT"})
                continue
            mapped = self.mapper._result_from_row({**passage, "score": passage["passage_score"]}, rank)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, passage)
            results.append({**mapped, "retrieval_match_type": "EXPLICIT_DOCUMENT_SELECTION"})
            availability.append({"document_id": document["document_id"], "title": document["title"], "classification": "DOCLING_TEXT_AVAILABLE"})
        return {
            "results": results,
            "transparency": {"strategy": "explicit_document_selection_v1", "selected_document_ids": document_ids},
            "diagnostics": {"selected_document_count": len(document_ids), "retrieved_documentary_source_count": len(results)},
            "archival_discovery": [], "document_availability": availability,
            "archival_context_only": [], "corpus_representation_gaps": [],
        }