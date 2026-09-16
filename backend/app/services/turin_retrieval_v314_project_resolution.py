"""V3.14 persisted project-title authority resolution over V3.13."""
from __future__ import annotations

import re
from typing import Any

from app.services.turin_retrieval_v313_event_selection import TurinRetrievalV313EventSelection


class TurinRetrievalV314ProjectResolution(TurinRetrievalV313EventSelection):
    """Adds exact persisted project labels while retaining numeric alias safety."""

    def _authority_index(self) -> dict[str, dict[str, Any]]:
        index = super()._authority_index()
        for record in self.authority_records:
            if str(record.get("authority_type") or "") != "ddr_projects":
                continue
            label = self._normalise(str(record.get("label") or ""))
            if label:
                index[label] = {"resolved_anchor_type": "PROJECT", "authority_id": str(record.get("authority_id") or ""), "authority_type": "ddr_projects", "resolution_method": "EXACT_LOCAL_AUTHORITY", "confidence_class": "TIER_1_EXACT"}
        return index

    def _profile(self, source_id: str, rows: list[dict[str, Any]], anchors: list[dict[str, Any]], required_facets: list[str], event_question: bool, compare_periods: bool) -> dict[str, Any]:
        profile = super()._profile(source_id, rows, anchors, required_facets, event_question, compare_periods)
        documentary_text = " ".join(str(row.get("chunk_text") or "").casefold() for row in rows)
        source_metadata = " ".join(str(rows[0].get(key) or "") for key in ("title", "filename", "authority_data")).casefold()
        changed = False
        for detail in profile["anchor_match_details"]:
            if detail["resolved_anchor_type"] == "PROJECT" and not detail["normalized_phrase"].startswith("job "):
                detail["matched"] = detail["normalized_phrase"] in documentary_text or detail["normalized_phrase"] in source_metadata
                detail["documentary_match"] = detail["normalized_phrase"] in documentary_text
                detail["match_scope"] = "DOCUMENTARY_TEXT" if detail["documentary_match"] else "ARCHIVAL_SOURCE_SCOPE" if detail["matched"] else "NONE"
                changed = True
        if changed:
            required = [detail for detail in profile["anchor_match_details"] if detail["required_or_preferred"] == "required"]
            profile["required_anchors_matched"] = sum(detail["matched"] for detail in required)
            profile["required_anchor_satisfied"] = profile.get("event_action_or_decision_satisfied", True) and all(detail["matched"] for detail in required if detail["resolved_anchor_type"] != "EVENT_ACTION")
        return profile
