"""V3.16 exact controlled project identity surface."""
from __future__ import annotations

from typing import Any

from app.services.turin_retrieval_v315_project_identity import TurinRetrievalV315ProjectIdentity


class TurinRetrievalV316ProjectIdentitySurface(TurinRetrievalV315ProjectIdentity):
    def __init__(self, authority_records: list[dict[str, Any]] | None = None, project_identities: list[dict[str, Any]] | None = None) -> None:
        super().__init__(authority_records)
        self.project_identities = project_identities or []

    def _metadata_project_anchors(self, candidates: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
        anchors = super()._metadata_project_anchors(candidates, question)
        normalized_question = self._normalise(question)
        for identity in self.project_identities:
            title = str(identity.get("project_title") or "")
            normalized = self._normalise(title)
            if normalized and self._contains_phrase(normalized_question, normalized):
                anchors.append({"raw_phrase": title, "normalized_phrase": normalized, "resolved_anchor_type": "PROJECT", "required_or_preferred": "required", "authority_id": identity.get("project_authority_id"), "authority_type": "PROJECT_TITLE_FROM_ARCHIVE_METADATA", "resolution_method": "EXACT_MATERIALISED_PROJECT_TITLE", "confidence_class": "TIER_3_EXACT", "trigger_field": identity.get("source_path"), "trigger_value": title, "project_identity_id": identity.get("project_identity_id")})
        return anchors
