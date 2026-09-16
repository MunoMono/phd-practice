"""V3.9 documentary-anchor-first source selection over unchanged V3.2 passages."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


ADEQUACY = {"PASSAGE_STRONG": 3, "PASSAGE_PARTIAL": 2, "PASSAGE_WEAK": 1, "PASSAGE_IRRELEVANT": 0}


class TurinRetrievalV39DocumentaryAnchors:
    """Protects primary documentary anchors before coverage and diversity completion."""

    @staticmethod
    def build(candidates: list[dict[str, Any]], question: str, required_facets: list[str], source_limit: int = 8) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            grouped[str(candidate.get("canonical_asset_id") or candidate["document_id"])].append(candidate)
        target_pid = TurinRetrievalV39DocumentaryAnchors._requested_asset_pid(question)
        profiles = [TurinRetrievalV39DocumentaryAnchors._profile(source_id, passages, required_facets, target_pid) for source_id, passages in grouped.items()]
        ranked = sorted(profiles, key=TurinRetrievalV39DocumentaryAnchors._rank_key, reverse=True)
        for rank, profile in enumerate(ranked, 1):
            profile["source_profile_rank"] = rank
        selected: list[dict[str, Any]] = []
        covered: set[str] = set()
        families: set[str] = set()
        anchors = [profile for profile in ranked if profile["explicit_asset_target_match"]] or [profile for profile in ranked if profile["documentary_anchor"]["is_strong_principal_anchor"]]
        for profile in anchors:
            if len(selected) >= source_limit:
                profile["selection_status"] = "SOURCE_POOL_TRUNCATION"
                profile["exclusion_reason"] = "STRONG_ANCHOR_LIMIT"
                continue
            TurinRetrievalV39DocumentaryAnchors._select(profile, selected, covered, families, "PASS_A_DOCUMENTARY_ANCHOR")
        for profile in ranked:
            if len(selected) >= source_limit or profile["selection_status"] == "SELECTED":
                continue
            missing = set(required_facets) - covered
            gain = set(profile["source_facet_union"]) & missing
            if not gain:
                profile["selection_status"] = "NOT_SELECTED_NO_MISSING_FACET"
                profile["exclusion_reason"] = "NO_DOCUMENTARY_COVERAGE_GAIN"
                continue
            if profile["source_family_id"] in families and profile["documentary_anchor"]["anchor_score"] <= max(item["documentary_anchor"]["anchor_score"] for item in selected if item["source_family_id"] == profile["source_family_id"]):
                profile["selection_status"] = "SIBLING_SOURCE_SUPPRESSED"
                profile["exclusion_reason"] = "SIBLING_SOURCE_SUPPRESSED_BECAUSE_WEAKER_DOCUMENTARY_ANCHOR"
                continue
            TurinRetrievalV39DocumentaryAnchors._select(profile, selected, covered, families, "PASS_B_COVERAGE_COMPLETION")
        bundles = [TurinRetrievalV39DocumentaryAnchors._bundle(profile) for profile in selected]
        passages = [passage for bundle in bundles for passage in bundle["documentary_evidence"]]
        return {"source_profiles": ranked, "evidence_bundles": bundles, "final_documentary_passages": passages, "selection_diagnostics": {"requested_asset_pid": target_pid, "source_limit": source_limit, "selected_source_count": len(selected), "principal_facets_covered": sorted(covered)}}

    @staticmethod
    def _profile(source_id: str, passages: list[dict[str, Any]], required_facets: list[str], target_pid: str | None) -> dict[str, Any]:
        ranked = sorted(passages, key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        best = ranked[0]
        components = best.get("passage_score_components", {})
        authority_data = best.get("authority_data") or {}
        asset_pid = str(best.get("asset_pid") or authority_data.get("attached_media_pid") or "")
        useful = [item for item in ranked if ADEQUACY.get(item.get("passage_adequacy"), 0) > 0]
        facets = set().union(*(set(item.get("facet_coverage", [])) for item in ranked))
        principal = set(required_facets) & set(best.get("facet_coverage", []))
        adequacy = ADEQUACY.get(best.get("passage_adequacy"), 0)
        entity_relation = int(bool(components.get("raw_exact_entity_match")) and bool(components.get("raw_relation_term_match") or components.get("raw_phrase_match") or principal))
        anchor_score = round(adequacy * 100 + int(bool(components.get("core_facets_present"))) * 20 + entity_relation * 10 + len(principal) * 5 + float(components.get("proximity_score") or 0) * 2 + best["passage_score"], 4)
        signals = best.get("source_signals", {})
        return {"canonical_asset_id": source_id, "document_id": best["document_id"], "archive_record_pid": best.get("archive_record_pid"), "attached_media_pid": authority_data.get("attached_media_pid") or authority_data.get("media_pid") or best.get("asset_pid"), "asset_pid": best.get("asset_pid"), "source_family_id": asset_pid or source_id, "source_type": best.get("source_type"), "source_nomination": {"lanes": best.get("lane_nominations", []), "signals": signals, "authority_graph_signals": best.get("authority_graph_signals", {})}, "source_nomination_confidence": round(sum(signals.values()), 6), "explicit_asset_target_match": bool(target_pid and asset_pid == target_pid), "top_passages": ranked, "best_passage_score": best["passage_score"], "best_passage_adequacy": best.get("passage_adequacy"), "source_facet_union": sorted(facets), "additional_useful_passages": max(len(useful) - 1, 0), "documentary_anchor": {"best_chunk_id": best["chunk_id"], "passage_adequacy": best.get("passage_adequacy"), "core_facets_present": bool(components.get("core_facets_present")), "entity_relation_cooccurrence": bool(entity_relation), "passage_score": best["passage_score"], "proximity_score": components.get("proximity_score", 0.0), "principal_facet_coverage": sorted(principal), "anchor_score": anchor_score, "is_strong_principal_anchor": adequacy == ADEQUACY["PASSAGE_STRONG"] and bool(principal)}, "selection_status": "NOT_EVALUATED", "exclusion_reason": None, "source_profile_rank": None}

    @staticmethod
    def _rank_key(profile: dict[str, Any]) -> tuple[Any, ...]:
        anchor = profile["documentary_anchor"]
        return (int(profile["explicit_asset_target_match"]), ADEQUACY.get(anchor["passage_adequacy"], 0), len(anchor["principal_facet_coverage"]), anchor["anchor_score"], profile["additional_useful_passages"], profile["source_nomination_confidence"], profile["canonical_asset_id"])

    @staticmethod
    def _select(profile: dict[str, Any], selected: list[dict[str, Any]], covered: set[str], families: set[str], reason: str) -> None:
        profile["selection_status"] = "SELECTED"
        profile["selection_reason"] = reason
        selected.append(profile)
        covered.update(profile["source_facet_union"])
        families.add(profile["source_family_id"])

    @staticmethod
    def _bundle(profile: dict[str, Any]) -> dict[str, Any]:
        evidence = [profile["top_passages"][0]]
        seen = set(evidence[0].get("facet_coverage", []))
        for passage in profile["top_passages"][1:]:
            if ADEQUACY.get(passage.get("passage_adequacy"), 0) >= 2 and set(passage.get("facet_coverage", [])) - seen:
                evidence.append(passage)
                break
        return {"source": {key: value for key, value in profile.items() if key != "top_passages"}, "documentary_evidence": evidence, "evidential_limit": "This bundle records retrieved documentary support only; it does not establish corpus-wide absence."}

    @staticmethod
    def _requested_asset_pid(question: str) -> str | None:
        match = re.search(r"\barchival\s+asset\s+(\d+)\b", question, re.IGNORECASE)
        return match.group(1) if match else None
