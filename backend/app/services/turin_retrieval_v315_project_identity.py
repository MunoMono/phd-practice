"""V3.15 project-identity alternatives over frozen V3.14 behavior."""
from __future__ import annotations

import re
from typing import Any

from app.services.turin_retrieval_v314_project_resolution import TurinRetrievalV314ProjectResolution


PROJECT_METADATA_FIELDS = ("project_title", "record_title", "attached_media_title", "asset_title", "master_label", "caption", "collection_title")


class TurinRetrievalV315ProjectIdentity(TurinRetrievalV314ProjectResolution):
    """Treats exact controlled Job IDs and titles as equivalent project identities."""

    def _metadata_project_anchors(self, candidates: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
        normalized_question = self._normalise(question)
        anchors = []
        for candidate in candidates:
            metadata = candidate.get("authority_data") or {}
            for field in PROJECT_METADATA_FIELDS:
                value = str(metadata.get(field) or "")
                normalized = self._normalise(value)
                if normalized and self._contains_phrase(normalized_question, normalized):
                    anchors.append({"raw_phrase": value, "normalized_phrase": normalized, "resolved_anchor_type": "PROJECT", "required_or_preferred": "required", "authority_id": None, "authority_type": "PROJECT_TITLE_FROM_ARCHIVE_METADATA", "resolution_method": "EXACT_ARCHIVE_PROJECT_TITLE", "confidence_class": "TIER_2_EXACT", "trigger_field": field, "trigger_value": value})
        return anchors

    def _profile(self, source_id: str, rows: list[dict[str, Any]], anchors: list[dict[str, Any]], required_facets: list[str], event_question: bool, compare_periods: bool) -> dict[str, Any]:
        profile = super()._profile(source_id, rows, anchors, required_facets, event_question, compare_periods)
        details = profile["anchor_match_details"]
        project_details = [detail for detail in details if detail["resolved_anchor_type"] == "PROJECT"]
        if not project_details:
            return profile
        identity = {"normalized_project_id": None, "normalized_project_titles": [], "authority_ids": [], "resolution_sources": []}
        for detail in project_details:
            if detail["normalized_phrase"].startswith("job "):
                identity["normalized_project_id"] = detail["normalized_phrase"].split()[-1]
            else:
                identity["normalized_project_titles"].append(detail["normalized_phrase"])
            if detail.get("authority_id"):
                identity["authority_ids"].append(detail["authority_id"])
            identity["resolution_sources"].append(detail["resolution_method"])
        identity["normalized_project_titles"] = sorted(set(identity["normalized_project_titles"]))
        identity["authority_ids"] = sorted(set(identity["authority_ids"]))
        identity["resolution_sources"] = sorted(set(identity["resolution_sources"]))
        profile["project_anchor"] = identity
        project_satisfied = any(detail["matched"] for detail in project_details)
        non_project_required = [detail for detail in details if detail["required_or_preferred"] == "required" and detail["resolved_anchor_type"] not in {"PROJECT", "EVENT_ACTION"}]
        profile["required_anchor_satisfied"] = project_satisfied and all(detail["matched"] for detail in non_project_required) and profile.get("event_action_or_decision_satisfied", True)
        return profile

    def build(self, candidates: list[dict[str, Any]], question: str, required_facets: list[str], source_limit: int = 8) -> dict[str, Any]:
        original_analyze = self.analyze
        base_anchors = original_analyze(question)
        metadata_anchors = self._metadata_project_anchors(candidates, question)
        if metadata_anchors:
            def analyze_with_metadata(_: str) -> list[dict[str, Any]]:
                return base_anchors + [anchor for anchor in metadata_anchors if anchor["normalized_phrase"] not in {item["normalized_phrase"] for item in base_anchors}]
            self.analyze = analyze_with_metadata
        try:
            return super().build(candidates, question, required_facets, source_limit)
        finally:
            self.analyze = original_analyze
