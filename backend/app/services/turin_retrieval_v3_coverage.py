"""Deterministic final-packet coverage selection and missingness protection."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.turin_retrieval_v34_slots import TurinRetrievalV34Slots


class TurinRetrievalV3Coverage:
    @staticmethod
    def select(candidates: list[dict[str, Any]], required_facets: list[str], top_k: int = 5, selection_version: str = "v3.2", analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if selection_version == "v3.4":
            if analysis is None:
                raise ValueError("V3.4 evidence-slot selection requires question analysis.")
            return TurinRetrievalV3Coverage._select_v34(candidates, analysis, top_k)
        if selection_version != "v3.3":
            return TurinRetrievalV3Coverage._select_v32(candidates, required_facets, top_k)
        selected: list[dict[str, Any]] = []; covered: set[str] = set(); used_assets: set[str] = set(); used_source_types: set[str] = set()
        candidates = [item for item in candidates if item.get("passage_adequacy") != "PASSAGE_IRRELEVANT"]
        scores = [item["passage_score"] for item in candidates]
        score_min, score_max = min(scores, default=0.0), max(scores, default=0.0)
        adequacy = {"PASSAGE_STRONG": 3, "PASSAGE_PARTIAL": 2, "PASSAGE_WEAK": 1, "CONTEXT_ONLY": 1, "CORE_FACETS_PRESENT": 3}
        remaining = []
        for item in candidates:
            documentary = (item["passage_score"] - score_min) / max(score_max - score_min, 1)
            source_confidence = sum(item.get("source_signals", {}).values())
            source_contribution = min(0.05, source_confidence * 0.025)
            remaining.append({**item, "global_score_components": {"raw_documentary_score": item["passage_score"], "normalized_documentary_score": round(documentary, 4), "raw_source_nomination_confidence": round(source_confidence, 4), "bounded_source_contribution": round(source_contribution, 4), "final_global_score": round(documentary + source_contribution, 4)}})
        remaining.sort(key=lambda item: (-adequacy.get(item.get("passage_adequacy"), 0), -int(bool(item.get("passage_score_components", {}).get("core_facets_present"))), -item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        while remaining and len(selected) < top_k:
            eligible = [item for item in remaining if str(item.get("canonical_asset_id") or item.get("asset_id") or item["document_id"]) not in used_assets]
            if not eligible: break
            choice = max(eligible, key=lambda item: (adequacy.get(item.get("passage_adequacy"), 0), int(bool(item.get("passage_score_components", {}).get("core_facets_present"))), item["passage_score"], len(set(item.get("facet_coverage", [])) - covered), int(bool(item.get("source_type")) and item.get("source_type") not in used_source_types), -item.get("chunk_index", 0)))
            added = sorted(set(choice.get("facet_coverage", [])) - covered)
            selected.append({**choice, "selection_reason": {"new_required_facets": [facet for facet in added if facet in required_facets], "marginal_facet_gain": len(added), "new_source_type": choice.get("source_type") if choice.get("source_type") not in used_source_types else None, "passage_adequacy": choice.get("passage_adequacy"), "relevance_score": choice["passage_score"], "canonical_asset_unique": True}})
            covered.update(choice.get("facet_coverage", [])); used_assets.add(str(choice.get("canonical_asset_id") or choice.get("asset_id") or choice["document_id"])); used_source_types.add(str(choice.get("source_type") or "")); remaining.remove(choice)
        return [{**item, "rank": index} for index, item in enumerate(selected, 1)]

    @staticmethod
    def _select_v34(candidates: list[dict[str, Any]], analysis: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
        template = TurinRetrievalV34Slots.template(analysis)
        annotated = TurinRetrievalV34Slots.annotate(candidates, analysis)
        candidates_by_id = {str(item["chunk_id"]): item for item in annotated if item.get("passage_adequacy") != "PASSAGE_IRRELEVANT"}
        selected: dict[str, dict[str, Any]] = {}
        for priority in ("REQUIRED", "PREFERRED", "OPTIONAL"):
            for slot in template[priority]:
                eligible = [item for item in candidates_by_id.values() if slot in item["eligible_slots"]]
                if priority == "OPTIONAL":
                    eligible = [item for item in eligible if item.get("passage_adequacy") in {"PASSAGE_STRONG", "PASSAGE_PARTIAL"}]
                if not eligible:
                    continue
                choice = max(eligible, key=lambda item: (item["slot_match_score"], item["passage_score"], -item.get("chunk_index", 0), str(item["chunk_id"])))
                chunk_id = str(choice["chunk_id"])
                if chunk_id not in selected and len(selected) >= top_k:
                    continue
                entry = selected.setdefault(chunk_id, {**choice, "global_score_components": None, "filled_slots": [], "selection_reason": {"selection_version": "v3.4", "slot_priorities": {}}})
                entry["filled_slots"].append(slot)
                entry["selection_reason"]["slot_priorities"][slot] = priority
        ordered = sorted(selected.values(), key=lambda item: (-len(item["filled_slots"]), -item["slot_match_score"], str(item["chunk_id"])))
        return [{**item, "filled_slots": sorted(item["filled_slots"]), "rank": index} for index, item in enumerate(ordered, 1)]

    @staticmethod
    def _select_v32(candidates: list[dict[str, Any]], required_facets: list[str], top_k: int) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []; covered: set[str] = set(); used_assets: set[str] = set(); used_source_types: set[str] = set()
        remaining = sorted(candidates, key=lambda item: (-item["passage_score"], str(item["chunk_id"])))
        while remaining and len(selected) < top_k:
            eligible = [item for item in remaining if str(item.get("canonical_asset_id") or item.get("asset_id") or item["document_id"]) not in used_assets]
            if not eligible: break
            choice = max(eligible, key=lambda item: (len(set(item.get("facet_coverage", [])) - covered), int(bool(item.get("source_type")) and item.get("source_type") not in used_source_types), item["passage_score"], str(item["chunk_id"])))
            added = sorted(set(choice.get("facet_coverage", [])) - covered)
            selected.append({**choice, "global_score_components": None, "selection_reason": {"new_required_facets": [facet for facet in added if facet in required_facets], "new_source_type": choice.get("source_type") if choice.get("source_type") not in used_source_types else None, "relevance_score": choice["passage_score"], "canonical_asset_unique": True}})
            covered.update(choice.get("facet_coverage", [])); used_assets.add(str(choice.get("canonical_asset_id") or choice.get("asset_id") or choice["document_id"])); used_source_types.add(str(choice.get("source_type") or "")); remaining.remove(choice)
        return [{**item, "rank": index} for index, item in enumerate(selected, 1)]

    @staticmethod
    def adequacy(selected: list[dict[str, Any]], analysis: dict[str, Any]) -> dict[str, Any]:
        if selected and any("filled_slots" in item for item in selected):
            template = TurinRetrievalV34Slots.template(analysis)
            filled = set().union(*(set(item.get("filled_slots", [])) for item in selected))
            required = set(template["REQUIRED"]); preferred = set(template["PREFERRED"]); optional = set(template["OPTIONAL"])
            metrics = {"required_slots_total": len(required), "required_slots_filled": len(required & filled), "preferred_slots_total": len(preferred), "preferred_slots_filled": len(preferred & filled), "optional_slots_filled": len(optional & filled), "slot_coverage_ratio": round(len(filled) / max(len(required | preferred | optional), 1), 4)}
            status = "RETRIEVAL_SUFFICIENT" if required <= filled and len(preferred & filled) >= min(1, len(preferred)) else "RETRIEVAL_PARTIAL" if selected else "RETRIEVAL_INSUFFICIENT"
            return {"status": status, "metrics": metrics, "filled_slots": sorted(filled), "unfilled_required_slots": sorted(required - filled), "unfilled_preferred_slots": sorted(preferred - filled), "corpus_missingness_permitted": status == "RETRIEVAL_SUFFICIENT", "missingness_safety_message": None if status == "RETRIEVAL_SUFFICIENT" else "No retrieved passage filled one or more required evidence slots; this is not a claim of corpus absence."}
        required = set(analysis["required_facets"]); covered = set().union(*(set(item.get("facet_coverage", [])) for item in selected)) if selected else set()
        source_types = Counter(item.get("source_type") or "unclassified" for item in selected)
        metrics = {"entity_coverage": int(bool({"PERSON_A", "PERSON_B", "PROJECT"} & covered)), "relation_coverage": int(bool({"ACTIVITY", "EVENT", "CAUSAL_LANGUAGE"} & covered)), "concept_coverage": int("CONCEPT" in covered), "temporal_coverage": int("TEMPORAL" in covered) if analysis["terms"]["TEMPORAL"] else None, "source_type_coverage": len(source_types), "relevant_passage_count": sum(item["passage_score"] > 0 for item in selected), "question_facet_coverage": round(len(covered & required) / max(len(required), 1), 4)}
        status = "RETRIEVAL_SUFFICIENT" if metrics["question_facet_coverage"] >= 0.75 and metrics["relevant_passage_count"] >= 3 else "RETRIEVAL_PARTIAL" if selected else "RETRIEVAL_INSUFFICIENT"
        if status == "RETRIEVAL_PARTIAL" and metrics["question_facet_coverage"] < 0.25: status = "RETRIEVAL_INSUFFICIENT"
        return {"status": status, "metrics": metrics, "covered_facets": sorted(covered), "missing_required_facets": sorted(required - covered), "corpus_missingness_permitted": status == "RETRIEVAL_SUFFICIENT", "missingness_safety_message": None if status == "RETRIEVAL_SUFFICIENT" else "The current retrieval did not surface evidence sufficient to establish the requested point."}