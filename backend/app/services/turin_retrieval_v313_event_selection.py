"""V3.13 event-evidence selection correction over V3.12 typed resolution."""
from __future__ import annotations

from typing import Any

from app.services.turin_retrieval_v312_authority_resolution import TurinRetrievalV312AuthorityResolution
from app.services.turin_retrieval_v39_documentary_anchors import ADEQUACY

EVENT_FAMILIES = (
    {"close", "closed", "closure"},
    {"merge", "merged"},
    {"decision", "resolved", "resolution"},
    {"abolish", "abolished", "dissolve", "dissolved"},
    {"reorganise", "reorganised", "reorganisation", "reorganization"},
)


class TurinRetrievalV313EventSelection(TurinRetrievalV312AuthorityResolution):
    """Requires institutional scope plus any bounded direct event action or decision."""

    def _profile(self, source_id: str, rows: list[dict[str, Any]], anchors: list[dict[str, Any]], required_facets: list[str], event_question: bool, compare_periods: bool) -> dict[str, Any]:
        profile = super()._profile(source_id, rows, anchors, required_facets, event_question, compare_periods)
        if not event_question:
            return profile
        documentary_text = " ".join(str(row.get("chunk_text") or "").casefold() for row in rows)
        details = profile["anchor_match_details"]
        event_details = [item for item in details if item["resolved_anchor_type"] == "EVENT_ACTION"]
        for item in event_details:
            variants = next((family for family in EVENT_FAMILIES if item["normalized_phrase"] in family), {item["normalized_phrase"]})
            item["matched"] = any(variant in documentary_text for variant in variants)
            item["documentary_match"] = item["matched"]
            item["match_scope"] = "DOCUMENTARY_TEXT" if item["matched"] else "NONE"
        non_event_required = [item for item in details if item["required_or_preferred"] == "required" and item["resolved_anchor_type"] != "EVENT_ACTION"]
        profile["required_anchors_matched"] = sum(item["matched"] for item in details if item["required_or_preferred"] == "required")
        profile["event_action_or_decision_satisfied"] = any(item["matched"] for item in event_details)
        profile["required_anchor_satisfied"] = profile["event_action_or_decision_satisfied"] and all(item["matched"] for item in non_event_required)
        return profile

    @staticmethod
    def _key(profile: dict[str, Any]) -> tuple[Any, ...]:
        pair_priority = {"SAME_PASSAGE": 3, "SOURCE_SEPARATE_PASSAGES": 2, "NONE": 0, None: 0}.get(profile["person_pair_state"], 0)
        return (int(profile["required_anchor_satisfied"]), profile["event_evidence_class_priority"], profile["required_anchors_matched"], pair_priority, profile["preferred_anchors_matched"], ADEQUACY.get(profile["best_passage_adequacy"], 0), len(profile["documentary_anchor"]["principal_facet_coverage"]), profile["best_passage_score"], len(profile["archival_temporal_context"]), sum(profile["source_nomination"]["signals"].values()), profile["canonical_asset_id"])
