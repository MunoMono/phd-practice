"""Archive-first, model-neutral retrieval for interactive Turin interrogation."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Mapping

from sqlalchemy import bindparam, text

from app.services.exploratory_retrieval_service import ExploratoryQueryPlanner, ExploratoryRetrievalService, _terms
from app.services.ml_policy import parse_ml_pages
from app.services.retrieval_contract_service import (
    RetrievalContract,
    candidate_project_anchor_matches,
    candidate_matches_requested_family,
    candidate_matches_facet,
    derive_retrieval_contract,
    diversify_candidates,
)
from app.services.retrieval_validation_service import RetrievalValidationService
from app.services.turin_question_policy import matching_turin_question_policy
from app.services.turin_question_route import classify_question_route, decompose_hybrid_question


ARCHIVE_FIRST_RETRIEVAL_VERSION = "turin-archive-first-retrieval-v1"
ARCHIVE_ASSET_SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"
MAX_ARCHIVE_CANDIDATES = 40
PASSAGES_PER_SOURCE = 3
NAMED_DOCUMENT_MAX_PASSAGES = 8
MAX_DOCUMENTARY_QUOTED_CONCEPT_SOURCES = 3
NAMED_DOCUMENT_OVERVIEW_TERMS = {
    "analysis", "awareness", "creativity", "criteria", "design", "development",
    "economic", "environmental", "ethics", "innovation", "measurement", "model",
    "needs", "planned", "process", "project", "qualitative", "quantitative",
    "research", "social", "strategy", "systems",
}
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
    def _requested_subject_passages(
        rows: list[dict[str, Any]], question: str, contract: RetrievalContract,
    ) -> list[dict[str, Any]]:
        if "rector_report" not in contract.required_evidence_types or not re.search(r"\bDDR\b", question, re.IGNORECASE):
            return rows
        named_department = [
            row for row in rows
            if re.search(r"\b(?:DDR|design\s+research)\b", str(row.get("chunk_text") or ""), re.IGNORECASE)
        ]
        return named_department or [
            row for row in rows
            if re.search(r"\bresearch\s+unit\b", str(row.get("chunk_text") or ""), re.IGNORECASE)
        ]

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
    def _substantive_named_document_passage(text_value: str) -> bool:
        """Exclude cover/title fragments when a question explicitly names a document."""
        text = " ".join(str(text_value or "").split())
        valid, _ = ExploratoryRetrievalService._passage_quality(text)
        return valid and len(text) >= 180 and len(_terms(text)) >= 30

    @staticmethod
    def _complete_sentence_count(text_value: str) -> int:
        """Prefer prose-bearing passages when selecting broad thematic evidence."""
        return sum(
            bool(
                len(sentence.strip()) >= 60
                and re.match(r"[A-Z\"']", sentence.lstrip())
                and "|" not in sentence
                and "##" not in sentence
            )
            for sentence in re.split(r"(?<=[.!?])\s+", str(text_value or ""))
        )

    @staticmethod
    def _is_named_document_overview_question(question: str) -> bool:
        return bool(re.search(
            r"\b(?:key take\s*aways?|main (?:arguments?|themes?)|central (?:arguments?|themes?)|overall argument|broadly)\b",
            question,
            re.IGNORECASE,
        ))

    @staticmethod
    def _named_document_overview_score(text_value: str) -> int:
        return len(set(_terms(text_value)).intersection(NAMED_DOCUMENT_OVERVIEW_TERMS))

    @classmethod
    def _is_archive_scope_overview_question(
        cls, question: str, archive_record_pid: str | None
    ) -> bool:
        return bool(archive_record_pid) and cls._is_named_document_overview_question(question)

    def retrieve_archive_scope_overview(
        self,
        db: Any,
        question: str,
        corpus_version: str,
        archive_record_pid: str,
        selected_top_k: int,
        thematic_terms: tuple[str, ...] = (),
        preset_id: str | None = None,
        contract: RetrievalContract | None = None,
    ) -> dict[str, Any]:
        """Select a broad, inspectable passage set from one controlled archive scope."""
        contract = contract or derive_retrieval_contract(
            question,
            preset_id=preset_id,
            single_document_mode=self._is_named_document_overview_question(question),
        )
        allow_cross_scope = contract.allow_cross_preset_backfill and bool(
            len(contract.required_evidence_types) > 1
            or contract.entity_anchors
            or contract.project_anchors
        )
        evidence_terms = set(NAMED_DOCUMENT_OVERVIEW_TERMS)
        if thematic_terms:
            evidence_terms = set().union(*(_terms(term) for term in thematic_terms))
        overview_query = " | ".join(sorted(evidence_terms))
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version, d.ml_page_scope,
                   ts_rank(dc.search_tsv, to_tsquery('english', :overview_query)) AS score
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE d.corpus_version = :corpus_version
              AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
              AND dc.search_tsv @@ to_tsquery('english', :overview_query)
              AND (:allow_cross_scope OR EXISTS (
                    SELECT 1
                    FROM turin_archive_asset_snapshots snapshot
                    WHERE snapshot.source_snapshot_version = :snapshot_version
                      AND snapshot.record_pid = :archive_record_pid
                      AND (
                        snapshot.asset_pid = d.asset_pid
                        OR snapshot.asset_id = d.asset_id
                        OR d.asset_id_or_asset_pid IN (snapshot.asset_pid, snapshot.asset_id)
                      )
                            ))
            ORDER BY score DESC, dc.chunk_index, dc.chunk_id
            LIMIT 600
        """), {
            "overview_query": overview_query,
            "corpus_version": corpus_version,
            "snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION,
            "archive_record_pid": archive_record_pid,
            "allow_cross_scope": allow_cross_scope,
        }).mappings().all()
        assets = self._asset_rows(db, None if allow_cross_scope else archive_record_pid)
        assets_by_identity = {
            self._asset_identity(asset): asset
            for asset in assets
        }
        candidates = [
            {
                **dict(row),
                **{
                    field: asset.get(field)
                    for field in (
                        "source_type", "record_title", "collection_title", "preset_groups",
                        "display_date", "normalized_date", "exact_job_id", "people",
                    )
                },
                "preferred_scope": str(row.get("archive_record_pid") or "") == archive_record_pid,
            }
            for row in rows
            for asset in [assets_by_identity.get(self._asset_identity(row), {})]
            if self._page_permitted(row.get("source_page"), row.get("ml_page_scope"))
            and self._substantive_named_document_passage(str(row.get("chunk_text") or ""))
        ]
        candidates.sort(key=lambda row: (
            0 if row.get("preferred_scope") else 1,
            -self._complete_sentence_count(str(row.get("chunk_text") or "")),
            -len(set(_terms(str(row.get("chunk_text") or ""))).intersection(evidence_terms)),
            -float(row.get("score") or 0.0),
            row.get("chunk_index") or 0,
            row["chunk_id"],
        ))
        limit = max(selected_top_k, NAMED_DOCUMENT_MAX_PASSAGES)
        selected, coverage = diversify_candidates(candidates, contract, limit)
        results = []
        for rank, row in enumerate(selected, start=1):
            mapped = self.mapper._result_from_row(row, rank)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, row)
            chunk_terms = set(_terms(str(row.get("chunk_text") or "")))
            matched_terms = sorted(chunk_terms.intersection(evidence_terms))
            evidence_anchor = {
                "document_id": row["document_id"],
                "chunk_id": row["chunk_id"],
                "page": row.get("source_page"),
                "retrieval_reason": "preset_thematic_documentary_term_match" if thematic_terms else "archive_scope_overview_term_match",
                "retrieval_channel": "ARCHIVE_SCOPE_OVERVIEW_FTS",
                "score": float(row.get("score") or 0.0),
                "matched_terms": matched_terms,
                "preset_id": preset_id,
            }
            results.append({
                **mapped,
                "retrieval_match_type": "ARCHIVE_SCOPE_OVERVIEW_PASSAGE",
                "retrieval_channels": ["ARCHIVE_SCOPE_OVERVIEW_FTS"],
                "evidence_anchor": evidence_anchor,
                "required_facets": list(row.get("required_facets") or []),
                "supported_facets": list(row.get("supported_facets") or []),
            })
        return {
            "results": results,
            "transparency": {
                "strategy": "archive_scope_overview_v1",
                "archive_record_pid": archive_record_pid,
                "source_nomination_unit": "controlled_archive_scope",
                "archive_question_preset": preset_id,
                "retrieval_contract": asdict(contract),
            },
            "diagnostics": {
                "archive_candidate_count": len(assets),
                "materialised_candidate_count": len({row["document_id"] for row in candidates}),
                "retrieved_documentary_source_count": len(results),
                "overview_document_count": len({row["document_id"] for row in selected}),
                "retrieval_coverage": coverage.as_dict(),
            },
            "archival_discovery": [],
            "document_availability": [],
            "archival_context_only": [],
            "corpus_representation_gaps": [],
        }

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

    def _asset_rows(self, db: Any, archive_record_pid: str | None = None) -> list[dict[str, Any]]:
        rows = db.execute(text("""
            SELECT record_pid, attached_media_pid, asset_pid, asset_id, label,
                   display_date, normalized_date, use_for_ml, ml_pages, source_type,
                   record_title, attached_media_title, keywords, people, projects,
                   box_title, collection_title, exact_project_title, exact_job_id,
                   controlled_aliases, preset_groups, source_snapshot_version
            FROM turin_archive_asset_snapshots
            WHERE source_snapshot_version = :snapshot_version
              AND (:archive_record_pid IS NULL OR record_pid = :archive_record_pid)
            ORDER BY asset_pid, asset_id
        """), {
            "snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION,
            "archive_record_pid": archive_record_pid,
        }).mappings().all()
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

    @classmethod
    def _explicit_source_title_matches(cls, question: str, titles: list[str]) -> list[str]:
        """Resolve a distinctive source title before thematic retrieval."""
        quoted_titles = [
            _normalise(concept)
            for concept in cls._quoted_concepts(question)
            if len(_terms(concept)) >= 3
        ]
        question_words = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
        project_ids = set(re.findall(r"\b(?:job|project)\s+(\d{1,3})\b", question, re.IGNORECASE))
        matches = []
        for title in titles:
            normalised_title = _normalise(title)
            title_words = re.findall(r"[a-z0-9]+", title.lower())
            distinctive_short_title = (
                len(title_words) == 2
                and any(len(word) >= 10 for word in title_words)
                and " ".join(title_words) in question_words
            )
            unquoted_title_phrases = [
                " ".join(title_words[index:index + length])
                for length in range(4, min(6, len(title_words)) + 1)
                for index in range(len(title_words) - length + 1)
                if any(len(word) >= 8 for word in title_words[index:index + length])
            ]
            if (
                any(quoted_title in normalised_title or normalised_title in quoted_title for quoted_title in quoted_titles)
                or distinctive_short_title
                or any(phrase in question_words for phrase in unquoted_title_phrases)
                or any(re.search(rf"\bjob\s+{re.escape(project_id)}\b", normalised_title) for project_id in project_ids)
            ):
                matches.append(title)
        return matches

    @staticmethod
    def _explicit_title_route_is_sufficient(question: str, matched_document_count: int) -> bool:
        if matched_document_count != 1:
            return False
        contract = derive_retrieval_contract(question, single_document_mode=True)
        comparison_surfaces = set(contract.required_evidence_types) - {"documentary", "project_report"}
        return contract.temporal_requirement == "none" and not comparison_surfaces

    def _explicit_title_document_ids(
        self, db: Any, question: str, corpus_version: str, archive_record_pid: str | None = None,
    ) -> list[str]:
        rows = db.execute(text("""
            SELECT document_id, title
                        FROM documents d
                        WHERE d.corpus_version = :corpus_version
              AND ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                            AND (
                                    :archive_record_pid IS NULL
                                    OR EXISTS (
                                            SELECT 1
                                            FROM turin_archive_asset_snapshots snapshot
                                            WHERE snapshot.source_snapshot_version = :snapshot_version
                                                AND snapshot.record_pid = :archive_record_pid
                                                AND (
                                                        snapshot.asset_pid = d.asset_pid
                                                        OR snapshot.asset_id = d.asset_id
                                                        OR d.asset_id_or_asset_pid IN (snapshot.asset_pid, snapshot.asset_id)
                                                )
                                    )
                            )
                        ORDER BY d.document_id
        """), {
            "corpus_version": corpus_version,
            "archive_record_pid": archive_record_pid,
                        "snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION,
        }).mappings().all()
        titles = [str(row["title"] or "") for row in rows]
        matched_titles = set(self._explicit_source_title_matches(question, titles))
        return [str(row["document_id"]) for row in rows if str(row["title"] or "") in matched_titles]

    @classmethod
    def _question_without_explicit_titles(cls, question: str) -> str:
        stripped = question
        for title in cls._quoted_concepts(question):
            stripped = re.sub(re.escape(title), " ", stripped, flags=re.IGNORECASE)
        return " ".join(stripped.split()) or question

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
            ORDER BY docling_text_available DESC,
                     (d.corpus_version = :corpus_version) DESC, d.document_id
            LIMIT 1
        """), {"corpus_version": corpus_version, "asset_pid": asset.get("asset_pid"), "asset_id": asset.get("asset_id")}).mappings().first()
        if asset.get("use_for_ml") is not True:
            return {"classification": "ARCHIVAL_CONTEXT_ONLY", "document_id": None, "docling_text_available": False}
        if document is None:
            return {"classification": "CORPUS_REPRESENTATION_GAP", "document_id": None, "docling_text_available": False}
        if not document["docling_text_available"]:
            return {"classification": "DOCLING_TEXT_MISSING", "document_id": document["document_id"], "docling_text_available": False}
        return {"classification": "DOCLING_TEXT_AVAILABLE", "document_id": document["document_id"], "docling_text_available": True}

    def retrieve(self, db: Any, question: str, selected_top_k: int, corpus_version: str, archive_record_pid: str | None = None) -> dict[str, Any]:
        policy = matching_turin_question_policy(question)
        if policy and policy.reservation_type == "SCOPED_MISSINGNESS":
            results = self._configured_document_page_results(db, question, corpus_version)
            if not results:
                results = self._configured_reservation_results(db, question)
            if results:
                return {
                    "results": results,
                    "transparency": {
                        "strategy": "configured_question_policy_reservation_v1",
                        "policy_id": policy.policy_id,
                    },
                    "diagnostics": {
                        "archive_candidate_count": 0,
                        "retrieved_documentary_source_count": len(results),
                        "configured_reservation_exclusive": True,
                    },
                    "archival_discovery": [], "document_availability": [],
                    "archival_context_only": [], "corpus_representation_gaps": [],
                }
        explicit_title_document_ids = self._explicit_title_document_ids(
            db, question, corpus_version, archive_record_pid,
        )
        if self._explicit_title_route_is_sufficient(question, len(explicit_title_document_ids)):
            contract = derive_retrieval_contract(question, single_document_mode=True)
            retrieval = self.retrieve_explicit_title_documents(
                db, question, explicit_title_document_ids, corpus_version, selected_top_k
            )
            retrieval["results"], coverage = diversify_candidates(
                retrieval["results"], contract, max(selected_top_k, NAMED_DOCUMENT_MAX_PASSAGES)
            )
            retrieval["transparency"] = {
                **retrieval["transparency"],
                "strategy": "explicit_source_title_v2",
                "matched_document_ids": explicit_title_document_ids,
                "retrieval_contract": asdict(contract),
            }
            retrieval["diagnostics"] = {
                **retrieval["diagnostics"],
                "retrieval_coverage": coverage.as_dict(),
            }
            return retrieval
        if self._is_archive_scope_overview_question(question, archive_record_pid):
            return self.retrieve_archive_scope_overview(
                db, question, corpus_version, str(archive_record_pid), selected_top_k
            )
        results = self._configured_document_page_results(db, question, corpus_version)
        if not results:
            results = self._configured_reservation_results(db, question)
        route_decision = classify_question_route(question)
        hybrid_decomposition = decompose_hybrid_question(question)
        if route_decision.family == "HYBRID_AUTHORITY_DOCUMENTARY" and hybrid_decomposition is None:
            return {
                "results": [],
                "transparency": {
                    "strategy": "hybrid_documentary_clause_unavailable_v1",
                    "route_family": route_decision.family,
                    "route_decision": route_decision.as_dict(),
                },
                "diagnostics": {
                    "archive_candidate_count": 0,
                    "retrieved_documentary_source_count": 0,
                    "diagnostic_state": "DOCUMENTARY_CLAUSE_UNAVAILABLE",
                },
                "archival_discovery": [], "document_availability": [],
                "archival_context_only": [], "corpus_representation_gaps": [],
            }
        if hybrid_decomposition:
            authority_plan = self.planner.build_plan(db, question)
            plan = self.planner.build_plan(
                db,
                hybrid_decomposition.documentary_query,
                entity_anchors=authority_plan["resolved_entities"],
                documentary_anchors=hybrid_decomposition.documentary_anchors,
            )
        else:
            plan = self.planner.build_plan(db, question)
        resolved_entity_labels = tuple(
            str(entity.get("label"))
            for entity in plan.get("resolved_entities", [])
            if entity.get("label")
        )
        contract = derive_retrieval_contract(question, entity_anchors=resolved_entity_labels)
        source_selection = policy.source_selection or {} if policy else {}
        required_source_families = set(source_selection.get("required_source_families", []))
        assets = self._asset_rows(db, archive_record_pid)
        if contract.project_anchors:
            assets = [
                asset for asset in assets
                if candidate_project_anchor_matches(asset, contract.project_anchors)
            ]
        nominations = []
        for asset in assets:
            if not candidate_matches_requested_family({**asset, "title": asset.get("label")}, contract):
                continue
            matches = self._candidate_matches(asset, plan)
            if matches["score"]:
                nominations.append({
                    "record_pid": asset.get("record_pid"), "attached_media_pid": asset.get("attached_media_pid"),
                    "asset_pid": asset.get("asset_pid"), "asset_id": asset.get("asset_id"), "label": asset.get("label"),
                    "display_date": asset.get("display_date"), "normalized_date": asset.get("normalized_date"),
                    "use_for_ml": asset.get("use_for_ml"), "ml_pages": asset.get("ml_pages"), **matches,
                    "source_type": asset.get("source_type"), "record_title": asset.get("record_title"),
                    "collection_title": asset.get("collection_title"), "preset_groups": asset.get("preset_groups"),
                    "exact_job_id": asset.get("exact_job_id"), "people": asset.get("people"),
                    "availability": self._availability(db, asset, corpus_version),
                })
        nominations.sort(key=lambda item: (-item["score"], str(item.get("asset_pid") or item.get("asset_id"))))
        nominations = nominations[:MAX_ARCHIVE_CANDIDATES]
        query_terms = set(_terms(str(plan["normalised_query"])))
        query_terms.update(
            term
            for entity in plan["resolved_entities"]
            for term in _terms(str(entity["label"]))
        )
        documentary_query = str(plan["normalised_query"])
        if not results:
            results = self._documentary_quoted_concept_results(
                db, documentary_query, corpus_version, min(MAX_DOCUMENTARY_QUOTED_CONCEPT_SOURCES, selected_top_k)
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
        covered_activities = {
            facet.value for facet in contract.required_facets
            if facet.facet_type == "activity"
            and any(candidate_matches_facet(result, facet) for result in results)
        }
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
            """), {"document_id": availability["document_id"], "corpus_version": corpus_version, "question": documentary_query}).mappings().all()
            permitted = [dict(row) for row in chunk_rows if self._page_permitted(row.get("source_page"), nomination["ml_pages"])]
            permitted = self._requested_subject_passages(permitted, question, contract)
            uncovered_facets = [
                facet for facet in contract.required_facets
                if facet.facet_type == "activity" and facet.value == "measurement"
                and facet.value not in covered_activities
            ]
            facet_passages = [
                row for row in permitted
                if any(candidate_matches_facet(row, facet) for facet in uncovered_facets)
            ]
            if facet_passages:
                permitted = facet_passages
            passage = ExploratoryRetrievalService._select_best_passage(permitted, query_terms)
            if passage is None:
                nomination["availability"] = {**availability, "classification": "DOCUMENTARY_EVIDENCE_INSUFFICIENT"}
                continue
            if passage["document_id"] in selected_document_ids:
                continue
            mapped = self.mapper._result_from_row({**passage, "score": passage["passage_score"]}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, passage)
            results.append({
                **mapped,
                "source_type": nomination.get("source_type"),
                "record_title": nomination.get("record_title"),
                "collection_title": nomination.get("collection_title"),
                "preset_groups": nomination.get("preset_groups"),
                "display_date": mapped.get("display_date") or nomination.get("display_date"),
                "exact_job_id": nomination.get("exact_job_id"),
                "people": nomination.get("people"),
                "archive_nomination": nomination,
                "retrieval_match_type": "ARCHIVE_FIRST_WITHIN_SOURCE_PASSAGE",
                "metadata_is_documentary_evidence": False,
            })
            covered_activities.update(
                facet.value for facet in contract.required_facets
                if facet.facet_type == "activity"
                and candidate_matches_facet(results[-1], facet)
            )
            selected_document_ids.add(passage["document_id"])
            selected_families.add(self._source_family(nomination))
            if len(results) == max(selected_top_k * 3, selected_top_k):
                break
        results, coverage = diversify_candidates(results, contract, selected_top_k)
        for rank, result in enumerate(results, start=1):
            result["rank"] = rank
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
            "transparency": {**plan, "strategy": ARCHIVE_FIRST_RETRIEVAL_VERSION, "archive_record_pid": archive_record_pid, "asset_snapshot_version": ARCHIVE_ASSET_SNAPSHOT_VERSION, "source_nomination_unit": "canonical_digital_asset", "global_corpus_competition_before_nomination": False, "retrieval_contract": asdict(contract), **({"hybrid_decomposition": hybrid_decomposition.as_dict()} if hybrid_decomposition else {})},
            "diagnostics": {"archive_candidate_count": len(nominations), "ml_eligible_candidate_count": sum(item["use_for_ml"] is True for item in nominations), "materialised_candidate_count": sum(item["availability"]["docling_text_available"] for item in nominations), "retrieved_documentary_source_count": len(results), "corpus_representation_gaps": len(gaps), "oral_history_coverage": oral_history_coverage, "source_family_diversity": source_family_diagnostics, "authority_asset_coverage": authority_asset_coverage, "retrieval_coverage": coverage.as_dict()},
            "archival_discovery": nominations,
            "document_availability": [{"asset_pid": item["asset_pid"], "asset_id": item["asset_id"], "label": item["label"], **item["availability"]} for item in nominations],
            "archival_context_only": archival_context_only,
            "corpus_representation_gaps": gaps,
        }

    def retrieve_person_evidence(
        self,
        db: Any,
        person_name: str,
        question: str,
        corpus_version: str,
        selected_top_k: int,
        archive_record_pid: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve substantive passages that explicitly name a resolved staff authority."""
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version, d.ml_page_scope,
                   ts_rank(dc.search_tsv, websearch_to_tsquery('english', :person_name)) AS score
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.search_tsv @@ websearch_to_tsquery('english', :person_name)
              AND d.use_for_ml = 1
              AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
              AND dc.corpus_version = :corpus_version
              AND (:archive_record_pid IS NULL OR d.archive_record_pid = :archive_record_pid)
            ORDER BY score DESC, dc.chunk_index, dc.chunk_id
        """), {
            "person_name": person_name,
            "corpus_version": corpus_version,
            "archive_record_pid": archive_record_pid,
        }).mappings().all()
        name_terms = set(_terms(person_name))
        activity_terms = {
            "appointed", "contribution", "curriculum", "design", "education", "joined",
            "lectured", "lecture", "philosophy", "professor", "research", "teaching",
            "tutor", "work", "wrote",
        }
        candidates = []
        for row in rows:
            row = dict(row)
            if not self._page_permitted(row.get("source_page"), row["ml_page_scope"]):
                continue
            passage = " ".join(str(row.get("chunk_text") or "").split())
            valid, _ = ExploratoryRetrievalService._passage_quality(passage)
            terms = set(_terms(passage))
            if not valid or not name_terms.issubset(terms):
                continue
            if len(passage) < 180 or "|" in passage or passage.upper().startswith("CURRICULUM VITAE"):
                continue
            activity_matches = len(terms & activity_terms)
            if not activity_matches:
                continue
            candidates.append((activity_matches, float(row.get("score") or 0.0), row))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]["chunk_index"], item[2]["chunk_id"]))
        results = []
        seen_documents = set()
        for _, score, row in candidates:
            if row["document_id"] in seen_documents:
                continue
            mapped = self.mapper._result_from_row({**row, "score": score}, len(results) + 1)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, row)
            results.append({**mapped, "retrieval_match_type": "EXPLICIT_PERSON_AUTHORITY_PASSAGE"})
            seen_documents.add(row["document_id"])
            if len(results) == selected_top_k:
                break
        return {
            "results": results,
            "transparency": {
                "strategy": "explicit_person_authority_v1",
                "person_name": person_name,
                "archive_record_pid": archive_record_pid,
            },
            "diagnostics": {
                "person_name": person_name,
                "person_named_candidate_count": len(candidates),
                "retrieved_documentary_source_count": len(results),
            },
            "archival_discovery": [], "document_availability": [],
            "archival_context_only": [], "corpus_representation_gaps": [],
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

    def retrieve_explicit_title_documents(
        self, db: Any, question: str, document_ids: list[str], corpus_version: str, selected_top_k: int,
    ) -> dict[str, Any]:
        """Retrieve several strong passages from a document explicitly named by title."""
        documents = db.execute(text("""
            SELECT document_id, title, ml_policy_status, ml_page_scope
            FROM documents
            WHERE document_id IN :document_ids AND corpus_version = :corpus_version
            ORDER BY document_id
        """).bindparams(bindparam("document_ids", expanding=True)), {
            "document_ids": document_ids, "corpus_version": corpus_version,
        }).mappings().all()
        found_ids = {row["document_id"] for row in documents}
        missing_ids = sorted(set(document_ids) - found_ids)
        if missing_ids:
            raise ValueError(f"Explicitly named documents are unavailable in the active corpus: {', '.join(missing_ids)}")

        passage_question = self._question_without_explicit_titles(question)
        results, availability = [], []
        for document in documents:
            if document["ml_policy_status"] not in {"eligible_unrestricted", "eligible_page_restricted"}:
                continue
            document_question = re.sub(
                re.escape(str(document["title"] or "")), " ", passage_question, flags=re.IGNORECASE,
            )
            chunk_rows = db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                       dc.source_page, dc.source_section, dc.chunk_metadata,
                       d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                       d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                       d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                       ts_rank(dc.search_tsv, websearch_to_tsquery('english', :question)) AS score
                FROM document_chunks dc JOIN documents d USING(document_id)
                WHERE dc.document_id = :document_id AND dc.corpus_version = :corpus_version
                ORDER BY score DESC, dc.chunk_index, dc.chunk_id
            """), {"document_id": document["document_id"], "corpus_version": corpus_version, "question": document_question}).mappings().all()
            permitted = [dict(row) for row in chunk_rows if self._page_permitted(row.get("source_page"), document["ml_page_scope"])]
            overview_question = self._is_named_document_overview_question(document_question)
            ranked_passages = [] if overview_question else [
                row for row in permitted
                if self._substantive_named_document_passage(str(row.get("chunk_text") or ""))
                and float(row.get("score") or 0.0) > 0
            ]
            selected_chunk_ids = {row["chunk_id"] for row in ranked_passages}
            question_terms = set(_terms(document_question))
            supplemental_passages = []
            for row in permitted:
                if row["chunk_id"] in selected_chunk_ids:
                    continue
                if not self._substantive_named_document_passage(str(row.get("chunk_text") or "")):
                    continue
                passage_text = str(row.get("chunk_text") or "")
                overlap = len(question_terms.intersection(_terms(passage_text)))
                overview_score = self._named_document_overview_score(passage_text) if overview_question else 0
                supplemental_passages.append((overview_score, overlap, float(row.get("score") or 0.0), row))
            supplemental_passages.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]["chunk_index"], item[3]["chunk_id"]))
            passage_limit = max(selected_top_k, NAMED_DOCUMENT_MAX_PASSAGES)
            ranked_passages.extend(
                row for _, _, _, row in supplemental_passages[:max(0, passage_limit - len(ranked_passages))]
            )
            for passage in ranked_passages:
                if len(results) == passage_limit:
                    break
                mapped = self.mapper._result_from_row(passage, len(results) + 1)
                ExploratoryRetrievalService._apply_snapshot_identity(mapped, passage)
                results.append({**mapped, "retrieval_match_type": "EXPLICIT_QUOTED_TITLE_PASSAGE"})
            availability.append({
                "document_id": document["document_id"], "title": document["title"],
                "classification": "DOCLING_TEXT_AVAILABLE" if ranked_passages else "DOCUMENTARY_EVIDENCE_INSUFFICIENT",
            })
            if len(results) == passage_limit:
                break
        return {
            "results": results,
            "transparency": {"strategy": "explicit_quoted_source_title_v1", "selected_document_ids": document_ids},
            "diagnostics": {"selected_document_count": len(documents), "retrieved_documentary_source_count": len(results)},
            "archival_discovery": [], "document_availability": availability,
            "archival_context_only": [], "corpus_representation_gaps": [],
        }

    def retrieve_selected_chunks(
        self, db: Any, chunk_ids: list[str], corpus_version: str
    ) -> dict[str, Any]:
        """Return explicitly selected passages after enforcing corpus and page policy."""
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type,
                   dc.source_page, dc.source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version, d.ml_policy_status,
                   d.ml_page_scope
            FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.chunk_id IN :chunk_ids AND dc.corpus_version = :corpus_version
            ORDER BY dc.chunk_index, dc.chunk_id
        """).bindparams(bindparam("chunk_ids", expanding=True)), {
            "chunk_ids": chunk_ids,
            "corpus_version": corpus_version,
        }).mappings().all()
        found_ids = {row["chunk_id"] for row in rows}
        missing_ids = sorted(set(chunk_ids) - found_ids)
        if missing_ids:
            raise ValueError(f"Selected chunks are unavailable in the active corpus: {', '.join(missing_ids)}")

        results = []
        for rank, row in enumerate(rows, start=1):
            if row["ml_policy_status"] not in {"eligible_unrestricted", "eligible_page_restricted"}:
                raise ValueError(f"Selected chunk is not eligible for model interrogation: {row['chunk_id']}")
            if not self._page_permitted(row["source_page"], row["ml_page_scope"]):
                raise ValueError(f"Selected chunk is outside its permitted page scope: {row['chunk_id']}")
            mapped = self.mapper._result_from_row({**dict(row), "score": 1.0}, rank)
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, row)
            results.append({**mapped, "retrieval_match_type": "EXPLICIT_CHUNK_SELECTION"})

        return {
            "results": results,
            "transparency": {"strategy": "explicit_chunk_selection_v1", "selected_chunk_ids": chunk_ids},
            "diagnostics": {"selected_chunk_count": len(chunk_ids), "retrieved_documentary_source_count": len(results)},
            "archival_discovery": [],
            "document_availability": [],
            "archival_context_only": [],
            "corpus_representation_gaps": [],
        }