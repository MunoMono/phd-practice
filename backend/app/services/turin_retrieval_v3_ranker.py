"""Inspectable documentary passage ranking for Turin retrieval v3."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _terms(value: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z0-9]+", value) if len(term) > 2}


def _normalised_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\u00ad", "")
    value = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _token_distance(text: str, left: set[str], right: set[str]) -> tuple[int | None, str | None]:
    words = _normalised_text(text).split()
    left_positions = [index for index, word in enumerate(words) if word in left]
    right_positions = [index for index, word in enumerate(words) if word in right]
    if not left_positions or not right_positions:
        return None, None
    distance, pair = min((abs(first - second), f"{words[first]}:{words[second]}") for first in left_positions for second in right_positions)
    return distance, pair


def _variants(values: list[str]) -> set[str]:
    forms = {"teach": {"teach", "teaching", "taught"}, "teaching": {"teach", "teaching", "taught"}, "learn": {"learn", "learning", "learned"}, "close": {"close", "closed", "closure"}, "merge": {"merge", "merged", "merger"}, "computer": {"computer", "computing"}, "computing": {"computer", "computing"}}
    return {variant for value in values for variant in forms.get(value, {value})}


def _quality(text_value: str) -> tuple[float, list[str]]:
    value = " ".join(text_value.split())
    lower = value.lower()
    exclusions: list[str] = []
    if "<!-- image -->" in lower or lower in {"[image]", "image"}:
        exclusions.append("image_marker")
    if len(value) < 80:
        exclusions.append("too_short")
    if sum(char.isalpha() for char in value) / max(len(value), 1) < 0.5:
        exclusions.append("ocr_or_table_fragment")
    return (0.0 if exclusions else min(1.0, len(_terms(value)) / 60)), exclusions


class TurinRetrievalV3Ranker:
    """Scores passages from their text; metadata remains source nomination only."""

    @staticmethod
    def score_passage(candidate: dict[str, Any], analysis: dict[str, Any], v32: bool = False) -> dict[str, Any]:
        text_value = str(candidate.get("chunk_text") or candidate.get("text") or "")
        passage_terms = _terms(text_value)
        lanes = analysis["lane_queries"]
        terms = analysis["terms"]
        entity_terms = _terms(" ".join(terms["ENTITY"] + terms["PROJECT"]))
        relation_terms = _terms(" ".join(lanes["relation_phrase"] + terms["ACTIVITY"] + terms["EVENT"]))
        concept_terms = _terms(" ".join(lanes["concept"]))
        entity_match = len(entity_terms & passage_terms) / max(len(entity_terms), 1)
        relation_match = len(relation_terms & passage_terms) / max(len(relation_terms), 1)
        concept_match = len(concept_terms & passage_terms) / max(len(concept_terms), 1)
        quality, exclusions = _quality(text_value)
        facets = TurinRetrievalV3Ranker.facet_coverage(text_value, analysis)
        proximity = TurinRetrievalV3Ranker._proximity(text_value, entity_terms, relation_terms)
        components = {
            "entity_match": round(entity_match, 4), "relation_match": round(relation_match, 4),
            "phrase_proximity": round(proximity, 4), "facet_coverage": round(len(facets) / max(len(analysis["required_facets"]), 1), 4),
            "documentary_information": round(quality, 4), "source_type_fit": 0.0,
            "temporal_fit": TurinRetrievalV3Ranker._temporal_fit(text_value, terms["TEMPORAL"]),
            "genericity_penalty": 1.0 if exclusions else 0.0,
        }
        score = 2 * components["entity_match"] + 2 * components["relation_match"] + components["phrase_proximity"] + components["facet_coverage"] + components["documentary_information"] + components["temporal_fit"] - 3 * components["genericity_penalty"]
        if v32:
            normalized = _normalised_text(text_value)
            raw_entity = int(bool(terms["ENTITY"]) and all(_normalised_text(entity) in normalized for entity in terms["ENTITY"]))
            raw_project = int(bool(terms["PROJECT"]) and any(_normalised_text(project) in normalized for project in terms["PROJECT"]))
            relation_variants = _variants(terms["ACTIVITY"] + terms["EVENT"])
            raw_relation = int(bool(relation_variants & passage_terms))
            raw_concept = int(bool(concept_terms & passage_terms))
            raw_phrase = int(any(_normalised_text(phrase) in normalized for phrase in terms["RELATION"]))
            raw_temporal = int(bool(set(terms["TEMPORAL"]) & passage_terms))
            core = raw_entity or raw_project or (not terms["ENTITY"] and not terms["PROJECT"] and raw_concept)
            proximity_left = entity_terms or _terms(" ".join(terms["PROJECT"]))
            proximity_right = relation_variants | _terms(" ".join(terms["RELATION"])) or concept_terms
            distance, pair = _token_distance(text_value, proximity_left, proximity_right)
            proximity_score = 0.0 if distance is None else round(max(0.0, 1 - distance / 24), 4)
            components.update({"raw_exact_entity_match": raw_entity, "raw_exact_project_match": raw_project, "raw_relation_term_match": raw_relation, "raw_concept_term_match": raw_concept, "raw_phrase_match": raw_phrase, "raw_temporal_match": raw_temporal, "minimum_token_distance": distance, "proximity_pair": pair, "proximity_score": proximity_score, "core_facets_present": int(core)})
            score = (4 * raw_entity + 4 * raw_project + 1.5 * raw_relation + raw_concept + raw_phrase + raw_temporal + 2 * proximity_score + 1.5 * components["facet_coverage"] + 0.25 * components["documentary_information"] - 3 * components["genericity_penalty"] - (2 if not core else 0))
            components["genericity_penalty"] = 1.0 if exclusions else 0.0
            quality_label = "PASSAGE_IRRELEVANT" if exclusions else "PASSAGE_STRONG" if core else "PASSAGE_PARTIAL" if facets else "PASSAGE_WEAK"
        else:
            quality_label = "PASSAGE_IRRELEVANT" if exclusions else "CORE_FACETS_PRESENT" if facets else "CONTEXT_ONLY"
        return {**candidate, "passage_score": round(score, 4), "passage_score_components": components, "facet_coverage": sorted(facets), "passage_quality_exclusions": exclusions, "passage_adequacy": quality_label, "passage_evidence_channel": "DIRECT_TEXT_MATCH" if entity_match or relation_match else "CONTEXTUAL_TEXT_MATCH"}

    @staticmethod
    def facet_coverage(text_value: str, analysis: dict[str, Any]) -> set[str]:
        terms = _terms(text_value); configured = analysis["terms"]; found: set[str] = set()
        if configured["ENTITY"] and _terms(" ".join(configured["ENTITY"])) <= terms: found.add("PERSON_A")
        if len(configured["ENTITY"]) > 1 and _terms(configured["ENTITY"][1]) <= terms: found.add("PERSON_B")
        if configured["PROJECT"] and any(_terms(item) <= terms for item in configured["PROJECT"]): found.add("PROJECT")
        if set(configured["ACTIVITY"]) & terms: found.add("ACTIVITY")
        if set(configured["EVENT"]) & terms: found.update({"EVENT", "CAUSAL_LANGUAGE"})
        if set(configured["SOURCE_TYPE"]) & terms: found.add("SOURCE_TYPE")
        if set(configured["TEMPORAL"]) & terms: found.add("TEMPORAL")
        if set(configured["CONCEPT"]) & terms: found.add("CONCEPT")
        return found

    @staticmethod
    def _proximity(text_value: str, entity_terms: set[str], relation_terms: set[str]) -> float:
        words = list(_terms(text_value)); positions_a = [index for index, word in enumerate(words) if word in entity_terms]; positions_b = [index for index, word in enumerate(words) if word in relation_terms]
        if not positions_a or not positions_b: return 0.0
        distance = min(abs(left - right) for left in positions_a for right in positions_b)
        return round(max(0.0, 1 - distance / 30), 4)

    @staticmethod
    def _temporal_fit(text_value: str, years: list[str]) -> float:
        return 1.0 if years and any(year in text_value for year in years) else 0.0