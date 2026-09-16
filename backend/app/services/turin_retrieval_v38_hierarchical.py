"""Source-first, documentary-backed evidence bundling for Turin V3.8."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


ADEQUACY = {"PASSAGE_STRONG": 3, "PASSAGE_PARTIAL": 2, "PASSAGE_WEAK": 1, "PASSAGE_IRRELEVANT": 0}


class TurinRetrievalV38Hierarchical:
    """Selects source profiles before selecting one or two documentary passages per source."""

    @staticmethod
    def build(candidates: list[dict[str, Any]], required_facets: list[str], source_limit: int = 8) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            grouped[str(candidate.get("canonical_asset_id") or candidate["document_id"])].append(candidate)
        profiles = [TurinRetrievalV38Hierarchical._profile(source_id, passages) for source_id, passages in grouped.items()]
        selected: list[dict[str, Any]] = []
        covered: set[str] = set()
        families: dict[str, set[str]] = defaultdict(set)
        for profile in sorted(profiles, key=TurinRetrievalV38Hierarchical._documentary_order, reverse=True):
            if profile["source_adequacy"] == "SOURCE_NO_DOCUMENTARY_SUPPORT":
                profile["selection_status"] = "NOMINATED_BUT_DOCUMENTARY_SUPPORT_NOT_FOUND"
                continue
            family = profile["source_family_id"]
            new_facets = set(profile["source_facet_union"]) - covered
            if family in families and not (new_facets & set(required_facets)):
                profile["selection_status"] = "SIBLING_SOURCE_SUPPRESSED"
                continue
            if len(selected) >= source_limit:
                profile["selection_status"] = "SOURCE_POOL_TRUNCATION"
                continue
            profile["selection_status"] = "SELECTED"
            profile["marginal_facet_gain"] = len(new_facets)
            if family in families:
                profile["sibling_source_retained_reason"] = "Adds principal question facet"
            selected.append(profile)
            covered.update(profile["source_facet_union"])
            families[family].add(profile["canonical_asset_id"])
        bundles = [TurinRetrievalV38Hierarchical._bundle(profile, covered) for profile in selected]
        documentary = [passage for bundle in bundles for passage in bundle["documentary_evidence"]]
        adequacy = TurinRetrievalV38Hierarchical._adequacy(profiles, bundles, documentary, required_facets)
        return {"source_profiles": profiles, "evidence_bundles": bundles, "final_documentary_passages": documentary, "retrieval_adequacy": adequacy}

    @staticmethod
    def _profile(source_id: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
        ranked = sorted(passages, key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        useful = [item for item in ranked if ADEQUACY.get(item.get("passage_adequacy"), 0) > 0]
        best = useful[0] if useful else ranked[0]
        facets = set().union(*(set(item.get("facet_coverage", [])) for item in useful)) if useful else set()
        components = best.get("passage_score_components", {})
        confidence = sum(best.get("source_signals", {}).values())
        if ADEQUACY.get(best.get("passage_adequacy"), 0) >= 3 and bool(components.get("core_facets_present")):
            source_adequacy = "SOURCE_STRONG"
        elif useful and (components.get("raw_relation_term_match") or facets):
            source_adequacy = "SOURCE_PARTIAL"
        elif useful:
            source_adequacy = "SOURCE_CONTEXTUAL"
        else:
            source_adequacy = "SOURCE_NO_DOCUMENTARY_SUPPORT"
        authority_data = best.get("authority_data") or {}
        attached_media_pid = authority_data.get("attached_media_pid") or authority_data.get("media_pid") or best.get("asset_pid") or best.get("canonical_asset_id")
        return {"canonical_asset_id": source_id, "document_id": best["document_id"], "archive_record_pid": best.get("archive_record_pid"), "attached_media_pid": attached_media_pid, "asset_id": best.get("asset_id"), "asset_pid": best.get("asset_pid"), "collection": authority_data.get("collection") or authority_data.get("collection_name"), "source_family_id": str(attached_media_pid), "source_type": best.get("source_type"), "source_nomination": {"lanes": best.get("lane_nominations", []), "signals": best.get("source_signals", {}), "authority_graph_signals": best.get("authority_graph_signals", {})}, "top_passages": ranked, "best_passage_score": best["passage_score"], "best_passage_adequacy": best.get("passage_adequacy"), "best_passage_core_facets": bool(components.get("core_facets_present")), "best_passage_facet_count": len(best.get("facet_coverage", [])), "top3_non_irrelevant_count": len(useful), "top3_strong_count": sum(item.get("passage_adequacy") == "PASSAGE_STRONG" for item in ranked), "top3_partial_count": sum(item.get("passage_adequacy") == "PASSAGE_PARTIAL" for item in ranked), "source_facet_union": sorted(facets), "source_relation_match": bool(any(item.get("passage_score_components", {}).get("raw_relation_term_match") for item in useful)), "source_entity_match": bool(any(item.get("passage_score_components", {}).get("raw_exact_entity_match") for item in useful)), "source_temporal_match": bool(any(item.get("passage_score_components", {}).get("raw_temporal_match") for item in useful)), "source_nomination_confidence": round(confidence, 6), "source_adequacy": source_adequacy, "selection_status": "NOT_EVALUATED", "marginal_facet_gain": 0}

    @staticmethod
    def _documentary_order(profile: dict[str, Any]) -> tuple[Any, ...]:
        best = profile["top_passages"][0]
        return (ADEQUACY.get(profile["best_passage_adequacy"], 0), int(profile["best_passage_core_facets"]), int(profile["source_relation_match"]), len(profile["source_facet_union"]), profile["top3_non_irrelevant_count"], best["passage_score"], min(profile["source_nomination_confidence"], 1.0))

    @staticmethod
    def _bundle(profile: dict[str, Any], all_covered: set[str]) -> dict[str, Any]:
        evidence = [profile["top_passages"][0]]
        first_facets = set(evidence[0].get("facet_coverage", []))
        for candidate in profile["top_passages"][1:]:
            new_facets = set(candidate.get("facet_coverage", [])) - first_facets
            if ADEQUACY.get(candidate.get("passage_adequacy"), 0) >= 2 and new_facets:
                evidence.append(candidate)
                break
        return {"source": {key: value for key, value in profile.items() if key not in {"top_passages"}}, "archival_context": {"archive_record_pid": profile["archive_record_pid"], "attached_media_pid": profile["attached_media_pid"], "asset_id": profile["asset_id"], "asset_pid": profile["asset_pid"], "collection": profile["collection"], "source_family_id": profile["source_family_id"], "nomination": profile["source_nomination"]}, "documentary_evidence": evidence, "evidential_limit": "This source bundle records retrieved documentary support only; it does not establish unrepresented relations or corpus-wide absence."}

    @staticmethod
    def _adequacy(profiles: list[dict[str, Any]], bundles: list[dict[str, Any]], passages: list[dict[str, Any]], required: list[str]) -> dict[str, Any]:
        facets = set().union(*(set(item.get("facet_coverage", [])) for item in passages)) if passages else set()
        required_set = set(required)
        strong = sum(profile["source_adequacy"] == "SOURCE_STRONG" for profile in profiles)
        status = "RETRIEVAL_SUFFICIENT" if strong and required_set <= facets else "RETRIEVAL_PARTIAL" if bundles else "RETRIEVAL_INSUFFICIENT"
        return {"status": status, "sources_nominated": len(profiles), "sources_with_strong_evidence": strong, "sources_with_partial_evidence": sum(profile["source_adequacy"] == "SOURCE_PARTIAL" for profile in profiles), "sources_contextual_only": sum(profile["source_adequacy"] == "SOURCE_CONTEXTUAL" for profile in profiles), "sources_rejected": sum(profile["selection_status"] != "SELECTED" for profile in profiles), "principal_facets_covered": sorted(facets & required_set), "source_types_covered": sorted({str(bundle["source"].get("source_type") or "unclassified") for bundle in bundles}), "temporal_classes_covered": int("TEMPORAL" in facets), "final_source_bundles": len(bundles), "final_documentary_passages": len(passages), "missingness_safety_message": None if status == "RETRIEVAL_SUFFICIENT" else "The retrieval bundle did not surface sufficient documentary evidence; this is not a claim of corpus absence."}
