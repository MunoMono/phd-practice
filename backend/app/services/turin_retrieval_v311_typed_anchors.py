"""Typed query-anchor source selection over frozen V3.2 passage candidates."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.services.turin_retrieval_v39_documentary_anchors import ADEQUACY


EVENT_TERMS = {"close", "closed", "closure", "merge", "merged", "decision", "resolved", "resolution", "abolish", "abolished", "dissolve", "dissolved", "reorganise", "reorganised", "reorganization", "reorganisation"}
OBJECT_TERMS = {"console", "ergonomics", "teaching", "learning", "students", "computing", "computer", "research"}
INSTITUTION_SUFFIXES = (" unit", " department", " institute", " school", " centre", " center")


class TurinRetrievalV311TypedAnchors:
    """Resolves local authority labels before applying literal documentary tests."""

    def __init__(self, authority_records: list[dict[str, Any]] | None = None) -> None:
        self.authority_records = authority_records or []

    @staticmethod
    def _normalise(value: str) -> str:
        return re.sub(r"\s+", " ", value.casefold().replace("–", "-").replace("—", "-")).strip()

    def _authority_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for record in self.authority_records:
            authority_type = str(record.get("authority_type") or "")
            resolved_type = "PERSON" if authority_type == "agent_employment" else "PROJECT" if authority_type == "ddr_projects" else "INSTITUTION_OR_UNIT" if authority_type == "ref_fonds" else None
            if not resolved_type:
                continue
            for value in (record.get("label"), record.get("code"), record.get("authority_id")):
                if value:
                    index.setdefault(self._normalise(str(value)), {"resolved_anchor_type": resolved_type, "authority_id": str(record.get("authority_id") or ""), "authority_type": authority_type, "resolution_method": "EXACT_LOCAL_AUTHORITY", "confidence_class": "TIER_1_EXACT"})
        return index

    def analyze(self, question: str) -> list[dict[str, Any]]:
        lower = self._normalise(question)
        authority_index = self._authority_index()
        anchors: list[dict[str, Any]] = []

        def add(raw_phrase: str, anchor_type: str, required: str, resolution: dict[str, Any] | None = None) -> None:
            normalized = self._normalise(raw_phrase)
            if any(item["normalized_phrase"] == normalized and item["resolved_anchor_type"] == anchor_type for item in anchors):
                return
            details = resolution or {"authority_id": None, "authority_type": None, "resolution_method": "LEXICAL_CLASSIFICATION", "confidence_class": "FALLBACK"}
            anchors.append({"raw_phrase": raw_phrase, "normalized_phrase": normalized, "resolved_anchor_type": anchor_type, "required_or_preferred": required, **details})

        for phrase, details in sorted(authority_index.items(), key=lambda item: -len(item[0])):
            if phrase in lower:
                label = next((str(record.get("label")) for record in self.authority_records if self._normalise(str(record.get("label") or "")) == phrase), phrase)
                required = "required" if details["resolved_anchor_type"] in {"PERSON", "PROJECT", "INSTITUTION_OR_UNIT"} else "preferred"
                add(label, details["resolved_anchor_type"], required, details)

        for identifier in re.findall(r"\b(?:job|project)\s+(?:number\s+)?(\d+)\b", question, re.I):
            details = authority_index.get(identifier, {"authority_id": identifier, "authority_type": "ddr_projects", "resolution_method": "EXACT_PROJECT_IDENTIFIER", "confidence_class": "TIER_3_EXACT"})
            add(f"Job {identifier}", "PROJECT", "required", details)
        for asset_id in re.findall(r"\barchival\s+asset\s+(\d+)\b", question, re.I):
            add(f"archival asset {asset_id}", "ARCHIVAL_ASSET", "required", {"authority_id": asset_id, "authority_type": "archive_asset", "resolution_method": "EXACT_ARCHIVAL_IDENTIFIER", "confidence_class": "TIER_3_EXACT"})
        for years in re.findall(r"\b(?:between\s+)?((?:18|19|20)\d{2})\s*(?:-|to|and)\s*((?:\d{2}|(?:18|19|20)\d{2}))\b", lower):
            start, end = years
            end = f"{start[:2]}{end}" if len(end) == 2 else end
            add(f"{start}-{end}", "TEMPORAL", "preferred", {"authority_id": None, "authority_type": None, "resolution_method": "EXACT_TEMPORAL_RANGE", "confidence_class": "TIER_3_EXACT"})

        resolved_phrases = {item["normalized_phrase"] for item in anchors}
        for phrase in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", question):
            normalized = self._normalise(phrase)
            if normalized in resolved_phrases or normalized.endswith(INSTITUTION_SUFFIXES):
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

    @staticmethod
    def _source_class(row: dict[str, Any]) -> tuple[str, str]:
        metadata = row.get("authority_data") or {}
        source_type = " ".join(str(metadata.get(key) or "") for key in ("source_type", "document_type", "collection", "record_title", "caption")).casefold()
        title = str(row.get("title") or "").casefold()
        combined = f"{source_type} {title}"
        if "interview" in combined:
            return "RETROSPECTIVE_INTERVIEW", "SOURCE_METADATA_TITLE"
        if any(value in combined for value in ("oral history", "recollection")):
            return "RETROSPECTIVE_ORAL_HISTORY", "SOURCE_METADATA_TITLE"
        if any(value in combined for value in ("report", "senate", "rector", "memorandum", "memo")):
            return "CONTEMPORARY_INSTITUTIONAL" if any(value in combined for value in ("senate", "rector", "memorandum", "memo")) else "CONTEMPORARY_ADMINISTRATIVE", "SOURCE_METADATA_TITLE"
        if "teaching" in combined or "curriculum" in combined:
            return "CONTEMPORARY_TEACHING", "SOURCE_METADATA"
        if "job " in combined or "project" in combined:
            return "CONTEMPORARY_PROJECT", "SOURCE_METADATA_TITLE"
        return "OTHER_DOCUMENTARY", "SOURCE_METADATA"

    @staticmethod
    def _date_context(row: dict[str, Any]) -> list[str]:
        metadata = row.get("authority_data") or {}
        values = [metadata.get(key) for key in ("date", "date_created", "start_date", "end_date", "year", "publication_date")]
        return [str(value) for value in values if value]

    def _profile(self, source_id: str, rows: list[dict[str, Any]], anchors: list[dict[str, Any]], required_facets: list[str], event_question: bool, compare_periods: bool) -> dict[str, Any]:
        ranked = sorted(rows, key=lambda passage: (-passage["passage_score"], passage.get("chunk_index", 0), str(passage["chunk_id"])))
        best = ranked[0]
        documentary_text = " ".join(str(passage.get("chunk_text") or "").casefold() for passage in ranked)
        source_metadata = " ".join(str(best.get(key) or "") for key in ("title", "filename", "source_type", "authority_data")).casefold()
        source_class, class_method = self._source_class(best)
        date_context = self._date_context(best)
        details = []
        people = []
        for anchor in anchors:
            value = anchor["normalized_phrase"]
            anchor_type = anchor["resolved_anchor_type"]
            if anchor_type == "PROJECT":
                matched = bool(re.search(rf"\b(?:job|project)\s+(?:number\s+)?{re.escape(value.split()[-1])}\b", documentary_text + " " + source_metadata))
            elif anchor_type == "ARCHIVAL_ASSET":
                matched = value.split()[-1] == str(best.get("asset_pid") or "")
            elif anchor_type == "PERSON_PAIR":
                names = [self._normalise(value) for value in value.split("+")]
                passage_match = any(all(name in str(passage.get("chunk_text") or "").casefold() for name in names) for passage in ranked)
                matched = all(name in documentary_text for name in names)
                details.append({**anchor, "matched": matched, "documentary_match": matched, "match_scope": "SAME_PASSAGE" if passage_match else "SOURCE_SEPARATE_PASSAGES" if matched else "NONE"})
                continue
            elif anchor_type == "INSTITUTION_OR_UNIT":
                documentary_match = value in documentary_text
                source_scope = value in source_metadata or any(value in str(label).casefold() for label in best.get("authority_graph_signals", {}).get("authority_labels", []))
                matched = documentary_match or source_scope
                details.append({**anchor, "matched": matched, "documentary_match": documentary_match, "match_scope": "DOCUMENTARY_TEXT" if documentary_match else "ARCHIVAL_SOURCE_SCOPE" if source_scope else "NONE"})
                continue
            elif anchor_type == "TEMPORAL":
                years = re.findall(r"\d{4}", value)
                start_year, end_year = (int(years[0]), int(years[-1])) if years else (0, 0)
                documentary_match = any(year in documentary_text for year in years)
                metadata_years = [int(year) for year in re.findall(r"\d{4}", " ".join(date_context))]
                metadata_match = any(start_year <= year <= end_year for year in metadata_years)
                matched = documentary_match or metadata_match
                details.append({**anchor, "matched": matched, "documentary_match": documentary_match, "match_scope": "DOCUMENTARY_TEXT" if documentary_match else "ARCHIVAL_TEMPORAL_CONTEXT" if metadata_match else "NONE"})
                continue
            else:
                matched = value in documentary_text
            details.append({**anchor, "matched": matched, "documentary_match": matched, "match_scope": "DOCUMENTARY_TEXT" if matched else "NONE"})
            if anchor_type == "PERSON":
                people.append((value, matched))
        required = [item for item in details if item["required_or_preferred"] == "required"]
        matched_required = sum(item["matched"] for item in required)
        required_satisfied = matched_required == len(required)
        person_details = [item for item in required if item["resolved_anchor_type"] == "PERSON"]
        unit_details = [item for item in required if item["resolved_anchor_type"] == "INSTITUTION_OR_UNIT"]
        other_required = [item for item in required if item["resolved_anchor_type"] not in {"PERSON", "INSTITUTION_OR_UNIT"}]
        if len(person_details) >= 2 and unit_details:
            required_satisfied = any(item["matched"] for item in person_details) and all(item["matched"] for item in unit_details) and all(item["matched"] for item in other_required)
        pair_detail = next((item for item in details if item["resolved_anchor_type"] == "PERSON_PAIR"), None)
        pair_state = pair_detail["match_scope"] if pair_detail else None
        person_unit_direct = sum(item["matched"] for item in details if item["resolved_anchor_type"] == "PERSON")
        facets = set().union(*(set(passage.get("facet_coverage", [])) for passage in ranked))
        primary = set(required_facets) & set(best.get("facet_coverage", []))
        adequacy = ADEQUACY.get(best.get("passage_adequacy"), 0)
        event_class_priority = {"CONTEMPORARY_INSTITUTIONAL": 5, "CONTEMPORARY_ADMINISTRATIVE": 4, "CONTEMPORARY_PROJECT": 3, "CONTEMPORARY_TEACHING": 2, "RETROSPECTIVE_INTERVIEW": 1, "RETROSPECTIVE_ORAL_HISTORY": 1, "RETROSPECTIVE_ANALYSIS": 1, "OTHER_DOCUMENTARY": 0}.get(source_class, 0) if event_question else 0
        period_group = "RETROSPECTIVE" if source_class.startswith("RETROSPECTIVE") else "CONTEMPORARY"
        return {"canonical_asset_id": source_id, "document_id": best["document_id"], "title": best.get("title"), "archive_record_pid": best.get("archive_record_pid"), "attached_media_pid": best.get("asset_pid"), "asset_pid": best.get("asset_pid"), "source_type": best.get("source_type"), "source_class": source_class, "source_class_derivation": class_method, "period_group": period_group if compare_periods else None, "archival_temporal_context": date_context, "source_nomination": {"lanes": best.get("lane_nominations", []), "signals": best.get("source_signals", {}), "authority_graph_signals": best.get("authority_graph_signals", {})}, "top_passages": ranked, "required_anchors_total": len(required), "required_anchors_matched": matched_required, "preferred_anchors_total": len(details) - len(required), "preferred_anchors_matched": sum(item["matched"] for item in details if item["required_or_preferred"] == "preferred"), "anchor_match_details": details, "required_anchor_satisfied": required_satisfied, "person_pair_state": pair_state, "person_direct_evidence_count": person_unit_direct, "source_facet_union": sorted(facets), "best_passage_score": best["passage_score"], "best_passage_adequacy": best.get("passage_adequacy"), "additional_useful_passages": sum(ADEQUACY.get(passage.get("passage_adequacy"), 0) > 0 for passage in ranked) - 1, "documentary_anchor": {"best_chunk_id": best["chunk_id"], "passage_adequacy": best.get("passage_adequacy"), "principal_facet_coverage": sorted(primary), "documentary_claim_support": bool(primary), "metadata_is_documentary_evidence": False}, "event_evidence_class_priority": event_class_priority, "selection_status": "NOT_EVALUATED", "source_profile_rank": None}

    @staticmethod
    def _key(profile: dict[str, Any]) -> tuple[Any, ...]:
        pair_priority = {"SAME_PASSAGE": 3, "SOURCE_SEPARATE_PASSAGES": 2, "NONE": 0, None: 0}.get(profile["person_pair_state"], 0)
        return (int(profile["required_anchor_satisfied"]), profile["required_anchors_matched"], profile["event_evidence_class_priority"], pair_priority, profile["preferred_anchors_matched"], ADEQUACY.get(profile["best_passage_adequacy"], 0), len(profile["documentary_anchor"]["principal_facet_coverage"]), profile["best_passage_score"], len(profile["archival_temporal_context"]), sum(profile["source_nomination"]["signals"].values()), profile["canonical_asset_id"])

    def build(self, candidates: list[dict[str, Any]], question: str, required_facets: list[str], source_limit: int = 8) -> dict[str, Any]:
        anchors = self.analyze(question)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            groups[str(candidate.get("canonical_asset_id") or candidate["document_id"])].append(candidate)
        lower = self._normalise(question)
        event_question = bool({"EVENT_ACTION"} & {item["resolved_anchor_type"] for item in anchors})
        compare_periods = "contemporary" in lower and "retrospective" in lower
        profiles = [self._profile(key, rows, anchors, required_facets, event_question, compare_periods) for key, rows in groups.items()]
        ranked = sorted(profiles, key=self._key, reverse=True)
        for rank, profile in enumerate(ranked, 1):
            profile["source_profile_rank"] = rank
        selected, covered, groups_selected = [], set(), set()
        for profile in ranked:
            if len(selected) >= source_limit:
                profile["selection_status"] = "SOURCE_POOL_TRUNCATION"
                continue
            if not profile["required_anchor_satisfied"]:
                profile["selection_status"] = "NOMINATED_BUT_ANCHOR_MISMATCH"
                continue
            period = profile["period_group"]
            gain = set(profile["source_facet_union"]) - covered
            if selected and not gain and not profile["documentary_anchor"]["documentary_claim_support"] and (not period or period in groups_selected):
                profile["selection_status"] = "NOT_SELECTED_NO_DOCUMENTARY_GAIN"
                continue
            profile["selection_status"] = "SELECTED"
            selected.append(profile)
            covered.update(profile["source_facet_union"])
            if period:
                groups_selected.add(period)
        bundles = [self._bundle(profile) for profile in selected]
        return {"query_anchors": anchors, "source_profiles": ranked, "evidence_bundles": bundles, "final_documentary_passages": [passage for bundle in bundles for passage in bundle["documentary_evidence"]], "retrieval_adequacy": "RETRIEVAL_SUFFICIENT" if bundles else "RETRIEVAL_INSUFFICIENT"}

    @staticmethod
    def _bundle(profile: dict[str, Any]) -> dict[str, Any]:
        evidence = [profile["top_passages"][0]]
        for passage in profile["top_passages"][1:]:
            if ADEQUACY.get(passage.get("passage_adequacy"), 0) >= 2 and set(passage.get("facet_coverage", [])) - set(evidence[0].get("facet_coverage", [])):
                evidence.append(passage)
                break
        return {"source": {key: value for key, value in profile.items() if key != "top_passages"}, "documentary_evidence": evidence, "evidential_limit": "Source class and archival temporal context establish provenance, not a documentary historical claim."}