"""V3.12 exact authority-resolution correction over the V3.11 selector."""
from __future__ import annotations

import re
from typing import Any

from app.services.turin_retrieval_v311_typed_anchors import EVENT_TERMS, OBJECT_TERMS, TurinRetrievalV311TypedAnchors


CONTROLLED_INSTITUTION_ALIASES = {
    "design education unit": ("DEU", "ref_fonds"),
    "department of design research": ("DDR", "ref_fonds"),
    "ddr": ("DDR", "ref_fonds"),
}
NON_PERSON_PHRASE_TERMS = {"design", "education", "research", "general", "department", "unit", "corpus", "current", "what", "how", "does", "can"}


class TurinRetrievalV312AuthorityResolution(TurinRetrievalV311TypedAnchors):
    """Uses only whole authority labels and controlled aliases for typed resolution."""

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        return bool(re.search(rf"(?<![\w]){re.escape(phrase)}(?![\w])", text))

    def _authority_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for record in self.authority_records:
            authority_type = str(record.get("authority_type") or "")
            resolved_type = "PERSON" if authority_type == "agent_employment" else "INSTITUTION_OR_UNIT" if authority_type == "ref_fonds" else None
            if not resolved_type:
                continue
            for value in (record.get("label"), record.get("code"), record.get("authority_id")):
                normalized = self._normalise(str(value or ""))
                if normalized and not normalized.isdigit():
                    index.setdefault(normalized, {"resolved_anchor_type": resolved_type, "authority_id": str(record.get("authority_id") or ""), "authority_type": authority_type, "resolution_method": "EXACT_LOCAL_AUTHORITY", "confidence_class": "TIER_1_EXACT"})
        for alias, (authority_id, authority_type) in CONTROLLED_INSTITUTION_ALIASES.items():
            index.setdefault(alias, {"resolved_anchor_type": "INSTITUTION_OR_UNIT", "authority_id": authority_id, "authority_type": authority_type, "resolution_method": "EXACT_CONTROLLED_ALIAS", "confidence_class": "TIER_2_ALIAS"})
        return index

    def analyze(self, question: str) -> list[dict[str, Any]]:
        lower = self._normalise(question)
        index = self._authority_index()
        anchors: list[dict[str, Any]] = []

        def add(raw_phrase: str, anchor_type: str, required: str, resolution: dict[str, Any] | None = None) -> None:
            normalized = self._normalise(raw_phrase)
            if any(item["normalized_phrase"] == normalized and item["resolved_anchor_type"] == anchor_type for item in anchors):
                return
            details = resolution or {"authority_id": None, "authority_type": None, "resolution_method": "LEXICAL_CLASSIFICATION", "confidence_class": "FALLBACK"}
            anchors.append({"raw_phrase": raw_phrase, "normalized_phrase": normalized, "resolved_anchor_type": anchor_type, "required_or_preferred": required, **details})

        for phrase, details in sorted(index.items(), key=lambda item: -len(item[0])):
            if self._contains_phrase(lower, phrase):
                raw_phrase = next((str(record.get("label")) for record in self.authority_records if self._normalise(str(record.get("label") or "")) == phrase), phrase)
                add(raw_phrase, details["resolved_anchor_type"], "required", details)
        for identifier in re.findall(r"\b(?:job|project)\s+(?:number\s+)?(\d+)\b", question, re.I):
            add(f"Job {identifier}", "PROJECT", "required", {"authority_id": identifier, "authority_type": "ddr_projects", "resolution_method": "EXACT_PROJECT_IDENTIFIER", "confidence_class": "TIER_3_EXACT"})
        for asset_id in re.findall(r"\barchival\s+asset\s+(\d+)\b", question, re.I):
            add(f"archival asset {asset_id}", "ARCHIVAL_ASSET", "required", {"authority_id": asset_id, "authority_type": "archive_asset", "resolution_method": "EXACT_ARCHIVAL_IDENTIFIER", "confidence_class": "TIER_3_EXACT"})
        for start, end in re.findall(r"\b(?:between\s+)?((?:18|19|20)\d{2})\s*(?:-|to|and)\s*((?:\d{2}|(?:18|19|20)\d{2}))\b", lower):
            add(f"{start}-{start[:2] + end if len(end) == 2 else end}", "TEMPORAL", "preferred", {"authority_id": None, "authority_type": None, "resolution_method": "EXACT_TEMPORAL_RANGE", "confidence_class": "TIER_3_EXACT"})
        resolved = {item["normalized_phrase"] for item in anchors}
        for phrase in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", question):
            normalized = self._normalise(phrase)
            words = set(normalized.split())
            if normalized in resolved or words & NON_PERSON_PHRASE_TERMS:
                continue
            add(phrase, "PERSON", "required")
        for term in sorted(EVENT_TERMS & set(re.findall(r"[a-z]+", lower))):
            add(term, "EVENT_ACTION", "required")
        for term in sorted(OBJECT_TERMS & set(re.findall(r"[a-z]+", lower))):
            add(term, "OBJECT_ACTIVITY", "preferred")
        people = [item for item in anchors if item["resolved_anchor_type"] == "PERSON"]
        if len(people) >= 2:
            add(f"{people[0]['raw_phrase']} + {people[1]['raw_phrase']}", "PERSON_PAIR", "preferred", {"authority_id": None, "authority_type": None, "resolution_method": "DERIVED_PERSON_PAIR", "confidence_class": "TIER_4_DERIVED"})
        return anchors
