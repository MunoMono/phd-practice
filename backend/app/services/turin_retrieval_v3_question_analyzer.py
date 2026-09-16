"""Deterministic, inspectable question analysis for Turin retrieval v3."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


STOP_WORDS = {
    "a", "about", "across", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "in",
    "is", "it", "of", "or", "the", "to", "what", "when", "where", "which", "who", "with", "within",
}
ACTIVITY_TERMS = {"design", "teach", "teaching", "learn", "learning", "research", "working", "work", "develop", "development", "manage", "management"}
EVENT_TERMS = {"close", "closure", "closed", "merge", "merged", "decision", "decide", "reason", "cause", "caused", "event"}
SOURCE_TYPE_TERMS = {"minutes", "report", "reports", "memoranda", "memorandum", "calendar", "calendars", "interview", "interviews", "oral", "history", "teaching", "notes"}
CONCEPT_VARIANTS = {"ergonomic": ["ergonomic", "ergonomics"], "ergonomics": ["ergonomic", "ergonomics"], "close": ["close", "closure"], "closure": ["close", "closure"], "merge": ["merge", "merged"], "merged": ["merge", "merged"], "computer": ["computer", "computing"], "computing": ["computer", "computing"], "teach": ["teach", "teaching"], "teaching": ["teach", "teaching"], "learn": ["learn", "learning"], "learning": ["learn", "learning"]}


def normalise(value: str) -> str:
    return " ".join(re.sub(r"['’]s\b", "", value.lower()).split())


def tokens(value: str) -> list[str]:
    return [item.lower() for item in re.findall(r"[A-Za-z0-9]+", value) if item.lower() not in STOP_WORDS]


@dataclass(frozen=True)
class QuestionAnalysis:
    question: str
    template: str
    terms: dict[str, list[str]]
    required_facets: list[str]
    optional_facets: list[str]
    lane_queries: dict[str, list[str]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TurinRetrievalV3QuestionAnalyzer:
    """Classifies generic lexical intent without semantic expansion or model calls."""

    def analyze(self, question: str) -> QuestionAnalysis:
        cleaned = " ".join(question.split())
        lowered = normalise(cleaned)
        words = tokens(cleaned)
        quoted = [value.strip() for value in re.findall(r'["“]([^"”]{2,120})["”]', cleaned)]
        projects = re.findall(r"\b(?:job|project)\s+(?:number\s+)?\d+\b", cleaned, flags=re.IGNORECASE)
        people = self._people(cleaned)
        activities = sorted(set(words).intersection(ACTIVITY_TERMS))
        events = sorted(set(words).intersection(EVENT_TERMS))
        source_types = sorted(set(words).intersection(SOURCE_TYPE_TERMS))
        temporal = re.findall(r"\b(?:19|20)\d{2}\b", cleaned)
        concepts = [word for word in words if word not in set(tokens(" ".join(people + projects))) and word not in activities and word not in events][:8]
        template = self._template(people, projects, activities, events, source_types, lowered)
        terms = {"ENTITY": people, "PROJECT": projects, "ACTIVITY": activities, "EVENT": events, "SOURCE_TYPE": source_types, "TEMPORAL": temporal, "CONCEPT": concepts, "RELATION": quoted}
        required = self._required_facets(template, people, projects, activities, events, source_types, temporal)
        optional = [facet for facet in ("CONCEPT", "TEMPORAL", "SOURCE_TYPE") if facet not in required and terms[facet]]
        return QuestionAnalysis(cleaned, template, terms, required, optional, self._lanes(terms))

    @staticmethod
    def _people(question: str) -> list[str]:
        candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", question)
        return [candidate for candidate in candidates if not candidate.lower().startswith(("what ", "how ", "which "))]

    @staticmethod
    def _template(people: list[str], projects: list[str], activities: list[str], events: list[str], source_types: list[str], lowered: str) -> str:
        if "missing" in lowered or "not establish" in lowered or "absence" in lowered:
            return "SCOPED_MISSINGNESS"
        if len(people) >= 2:
            return "PERSON_PERSON_RELATIONSHIP"
        if people and activities:
            return "PERSON_ROLE"
        if projects:
            return "PROJECT_TRACES"
        if events:
            return "EVENT_CAUSATION"
        if source_types or ("contemporary" in lowered and "retrospective" in lowered):
            return "SOURCE_TYPE_COMPARISON"
        return "CONTESTED_CONCEPT"

    @staticmethod
    def _required_facets(template: str, people: list[str], projects: list[str], activities: list[str], events: list[str], source_types: list[str], temporal: list[str]) -> list[str]:
        facets: list[str] = []
        if people:
            facets.extend(["PERSON_A"] + (["PERSON_B"] if len(people) > 1 else []))
        if projects:
            facets.append("PROJECT")
        if activities:
            facets.append("ACTIVITY")
        if events:
            facets.extend(["EVENT", "CAUSAL_LANGUAGE"])
        if source_types or template == "SOURCE_TYPE_COMPARISON":
            facets.append("SOURCE_TYPE")
        if temporal:
            facets.append("TEMPORAL")
        return facets or ["CONCEPT"]

    @staticmethod
    def _lanes(terms: dict[str, list[str]]) -> dict[str, list[str]]:
        entity = terms["ENTITY"] + terms["PROJECT"]
        relation = terms["RELATION"] + [" ".join(entity + terms["ACTIVITY"])] if entity and terms["ACTIVITY"] else terms["RELATION"]
        concept = sorted({variant for term in terms["CONCEPT"] + terms["ACTIVITY"] for variant in CONCEPT_VARIANTS.get(term, [term])})
        metadata = entity + terms["SOURCE_TYPE"] + terms["TEMPORAL"]
        return {"entity": entity, "relation_phrase": relation, "concept": concept, "archival_metadata": metadata, "source_type": terms["SOURCE_TYPE"], "temporal_event": terms["TEMPORAL"] + terms["EVENT"]}