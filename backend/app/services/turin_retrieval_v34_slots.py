"""Deterministic evidence-slot templates and documentary passage matching for Turin V3.4."""

from __future__ import annotations

from typing import Any


SLOT_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "PERSON_ROLE": {
        "REQUIRED": ["SUBJECT_ROLE_RELATION"],
        "PREFERRED": ["SUBJECT_IDENTITY", "ROLE_OR_ACTIVITY"],
        "OPTIONAL": ["TEMPORAL_CONTEXT", "CORROBORATION"],
    },
    "PERSON_PERSON_RELATIONSHIP": {
        "REQUIRED": ["DIRECT_CO_OCCURRENCE"],
        "PREFERRED": ["PERSON_A_EVIDENCE", "PERSON_B_EVIDENCE", "SHARED_PROJECT_OR_UNIT"],
        "OPTIONAL": ["RELATIONSHIP_LIMIT"],
    },
    "PROJECT_TRACES": {
        "REQUIRED": ["PROJECT_IDENTITY"],
        "PREFERRED": ["PEOPLE", "ACTIVITY", "OUTPUT"],
        "OPTIONAL": ["TEMPORAL_CONTEXT"],
    },
    "EVENT_CAUSATION": {
        "REQUIRED": ["EVENT_OR_DECISION", "EXPLICIT_CAUSAL_STATEMENT"],
        "PREFERRED": ["INSTITUTIONAL_ACTION", "CONTEMPORARY_CONTEXT"],
        "OPTIONAL": ["RETROSPECTIVE_INTERPRETATION"],
    },
    "CONTESTED_CONCEPT": {
        "REQUIRED": ["CONCEPT_EXPLICIT"],
        "PREFERRED": ["DEFINITION_OR_FORMULATION", "ALTERNATIVE_FORMULATION", "NAMED_CONTRIBUTOR"],
        "OPTIONAL": ["TEMPORAL_OR_SOURCE_TYPE_CONTRAST"],
    },
    "SOURCE_TYPE_COMPARISON": {
        "REQUIRED": ["SUBJECT_EVIDENCE", "SOURCE_TYPE_A", "SOURCE_TYPE_B"],
        "PREFERRED": ["CONVERGENCE", "DIVERGENCE"],
        "OPTIONAL": [],
    },
    "SCOPED_MISSINGNESS": {
        "REQUIRED": ["DIRECT_SEARCH_TARGET"],
        "PREFERRED": ["EXPECTED_SOURCE_GENRE", "RELATED_CONTEXT"],
        "OPTIONAL": ["COUNTEREVIDENCE", "RETRIEVAL_LIMIT"],
    },
}


class TurinRetrievalV34Slots:
    """Maps frozen documentary signals to explicit evidential roles."""

    @staticmethod
    def template(analysis: dict[str, Any]) -> dict[str, list[str]]:
        return SLOT_TEMPLATES[analysis["template"]]

    @staticmethod
    def annotate(candidates: list[dict[str, Any]], analysis: dict[str, Any]) -> list[dict[str, Any]]:
        return [TurinRetrievalV34Slots.match(candidate, analysis) for candidate in candidates]

    @staticmethod
    def match(candidate: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        components = candidate.get("passage_score_components", {})
        facets = set(candidate.get("facet_coverage", []))
        terms = analysis["terms"]
        entity_a = bool(components.get("raw_exact_entity_match") or "PERSON_A" in facets)
        entity_b = "PERSON_B" in facets
        project = bool(components.get("raw_exact_project_match") or "PROJECT" in facets)
        activity = bool(components.get("raw_relation_term_match") or "ACTIVITY" in facets)
        event = bool("EVENT" in facets or components.get("raw_relation_term_match"))
        causal = bool(components.get("raw_phrase_match") or any(term in str(candidate.get("chunk_text") or "").lower() for term in ("cause", "caused", "because", "reason")))
        concept = bool(components.get("raw_concept_term_match") or "CONCEPT" in facets)
        temporal = bool(components.get("raw_temporal_match") or "TEMPORAL" in facets)
        source_type = str(candidate.get("source_type") or "").lower()
        source_type_match = bool(set(terms["SOURCE_TYPE"]) & set(source_type.split()))
        proximal = components.get("minimum_token_distance") is not None and components.get("minimum_token_distance") <= 24
        template = analysis["template"]
        checks = {
            "PERSON_ROLE": {"SUBJECT_IDENTITY": entity_a, "ROLE_OR_ACTIVITY": activity, "SUBJECT_ROLE_RELATION": entity_a and activity and proximal, "TEMPORAL_CONTEXT": temporal, "CORROBORATION": entity_a and activity},
            "PERSON_PERSON_RELATIONSHIP": {"PERSON_A_EVIDENCE": entity_a, "PERSON_B_EVIDENCE": entity_b, "DIRECT_CO_OCCURRENCE": entity_a and entity_b, "SHARED_PROJECT_OR_UNIT": project, "RELATIONSHIP_LIMIT": False},
            "PROJECT_TRACES": {"PROJECT_IDENTITY": project, "PEOPLE": entity_a or entity_b, "ACTIVITY": activity, "OUTPUT": concept, "TEMPORAL_CONTEXT": temporal},
            "EVENT_CAUSATION": {"EVENT_OR_DECISION": event, "INSTITUTIONAL_ACTION": event and activity, "EXPLICIT_CAUSAL_STATEMENT": causal, "CONTEMPORARY_CONTEXT": temporal, "RETROSPECTIVE_INTERPRETATION": source_type in {"interview", "oral history"}},
            "CONTESTED_CONCEPT": {"CONCEPT_EXPLICIT": concept, "DEFINITION_OR_FORMULATION": concept and causal, "ALTERNATIVE_FORMULATION": concept and activity, "NAMED_CONTRIBUTOR": entity_a or entity_b, "TEMPORAL_OR_SOURCE_TYPE_CONTRAST": temporal or source_type_match},
            "SOURCE_TYPE_COMPARISON": {"SUBJECT_EVIDENCE": entity_a or project or concept, "SOURCE_TYPE_A": source_type_match, "SOURCE_TYPE_B": source_type_match, "CONVERGENCE": entity_a and activity, "DIVERGENCE": causal},
            "SCOPED_MISSINGNESS": {"DIRECT_SEARCH_TARGET": entity_a or project or concept, "EXPECTED_SOURCE_GENRE": source_type_match, "RELATED_CONTEXT": activity or event or concept, "COUNTEREVIDENCE": False, "RETRIEVAL_LIMIT": False},
        }[template]
        reasons = {slot: TurinRetrievalV34Slots._reason(slot, components, facets) for slot, matched in checks.items() if matched}
        slot_score = round(candidate["passage_score"] + 0.1 * len(reasons) + (0.1 if proximal else 0), 4)
        return {**candidate, "eligible_slots": sorted(reasons), "slot_match_reasons": reasons, "slot_match_score": slot_score}

    @staticmethod
    def _reason(slot: str, components: dict[str, Any], facets: set[str]) -> list[str]:
        signals = [name for name in ("raw_exact_entity_match", "raw_exact_project_match", "raw_relation_term_match", "raw_phrase_match", "raw_temporal_match", "minimum_token_distance") if components.get(name)]
        return signals + sorted(facets) + [f"slot:{slot}"]
