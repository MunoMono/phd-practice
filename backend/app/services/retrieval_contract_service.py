"""Question-derived retrieval contracts and deterministic source diversification."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, order=True)
class FacetRequirement:
    """A deterministic evidence obligation derived from explicit query structure."""

    facet_type: str
    value: str

    def as_dict(self) -> dict[str, str]:
        return {"facet_type": self.facet_type, "value": self.value}


@dataclass(frozen=True)
class RetrievalContract:
    retrieval_mode: str = "bounded_documentary"
    required_evidence_types: tuple[str, ...] = ("documentary",)
    required_source_presets: tuple[str, ...] = ()
    preferred_source_presets: tuple[str, ...] = ()
    required_authority_types: tuple[str, ...] = ()
    entity_anchors: tuple[str, ...] = ()
    project_anchors: tuple[str, ...] = ()
    collection_anchors: tuple[str, ...] = ()
    required_document_roles: tuple[str, ...] = ()
    required_facets: tuple[FacetRequirement, ...] = ()
    temporal_requirement: str = "none"
    temporal_buckets: tuple[str, ...] = ()
    temporal_start_year: int | None = None
    temporal_end_year: int | None = None
    minimum_distinct_sources: int = 1
    minimum_sources_per_required_surface: int = 1
    initial_max_chunks_per_source: int = 1
    allow_cross_preset_backfill: bool = True
    allow_scoped_limit_if_coverage_unmet: bool = True
    single_document_mode: bool = False


@dataclass(frozen=True)
class RetrievalCoverage:
    coverage_status: str
    required_surfaces_found: tuple[str, ...]
    required_surfaces_missing: tuple[str, ...]
    distinct_source_count: int
    temporal_buckets_found: tuple[str, ...]
    target_entity_evidence_found: bool | None
    target_project_evidence_found: bool | None
    project_anchors_found: tuple[str, ...]
    project_anchors_missing: tuple[str, ...]
    document_roles_found: tuple[str, ...]
    document_roles_missing: tuple[str, ...]
    facets_found: tuple[FacetRequirement, ...]
    facets_missing: tuple[FacetRequirement, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "coverage_status": self.coverage_status,
            "required_surfaces_found": list(self.required_surfaces_found),
            "required_surfaces_missing": list(self.required_surfaces_missing),
            "distinct_source_count": self.distinct_source_count,
            "temporal_buckets_found": list(self.temporal_buckets_found),
            "target_entity_evidence_found": self.target_entity_evidence_found,
            "target_project_evidence_found": self.target_project_evidence_found,
            "project_anchors_found": list(self.project_anchors_found),
            "project_anchors_missing": list(self.project_anchors_missing),
            "document_roles_found": list(self.document_roles_found),
            "document_roles_missing": list(self.document_roles_missing),
            "facets_found": [facet.as_dict() for facet in self.facets_found],
            "facets_missing": [facet.as_dict() for facet in self.facets_missing],
        }


_PROJECT_SERIES_PATTERN = re.compile(
    r"\b(?:job|project)s?\s+(?:number\s+)?(\d{1,3})(?:\s*(?:,|and|&)\s*(\d{1,3}))*",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}(?=\D|$)")
_DOCUMENT_ROLE_PATTERNS = (
    ("rector_report", r"\brector['\u2019]s?\s+reports?\b"),
    ("teaching", r"\bteaching\b"),
    ("paper", r"\bpapers?\b"),
    ("record", r"\brecords?\b"),
    ("note", r"\bnotes?\b"),
    ("assessment", r"\bassessment\b"),
    ("calendar", r"\bcalendars?\b"),
)
_ACTIVITY_FACET_PATTERNS = (
    ("game", r"\bgames?\b"),
    ("simulation", r"\bsimulations?\b"),
    ("modelling", r"\bmodell?ing\b"),
    ("learning_by_doing", r"\blearning[- ]by[- ]doing\b"),
)
_RELATIONSHIP_FACET_PATTERNS = (
    ("collaborated", r"\bcollaborat\w*\b"),
    ("authored", r"\bauthor(?:ed|ship)?\b"),
    ("project_lead", r"\b(?:project )?lead(?:ing)?\b"),
    ("responsible", r"\bresponsib\w*\b"),
)


def project_anchors_from_question(question: str) -> tuple[str, ...]:
    anchors: list[str] = []
    for match in _PROJECT_SERIES_PATTERN.finditer(question):
        anchors.extend(re.findall(r"\d{1,3}", match.group(0)))
    return tuple(dict.fromkeys(anchors))


def candidate_project_anchor_matches(
    candidate: Mapping[str, Any], project_anchors: tuple[str, ...]
) -> tuple[str, ...]:
    exact_job_id = str(candidate.get("exact_job_id") or "").strip()
    searchable = str(candidate)
    mentioned_anchors = set(project_anchors_from_question(searchable))
    return tuple(
        anchor for anchor in project_anchors
        if exact_job_id == anchor
        or anchor in mentioned_anchors
    )


def _question_year_bounds(question: str) -> tuple[int | None, int | None]:
    ranges = []
    for match in _YEAR_PATTERN.finditer(question):
        year = int(match.group())
        decade = question[match.end():match.end() + 1].lower() == "s"
        ranges.append((year, year + 9 if decade else year))
    for match in re.finditer(r"\b((?:19|20)\d{2})\s*[-–]\s*(\d{2})(?!\d)", question):
        start = int(match.group(1))
        end = start // 100 * 100 + int(match.group(2))
        ranges.append((start, end))
    if len(ranges) < 2 and not any(start != end for start, end in ranges):
        return None, None
    return min(start for start, _end in ranges), max(end for _start, end in ranges)


def _document_roles_from_question(question: str) -> tuple[str, ...]:
    return tuple(
        role for role, pattern in _DOCUMENT_ROLE_PATTERNS
        if re.search(pattern, question, flags=re.IGNORECASE)
    )


def _facets_from_question(
    question: str,
    *,
    document_roles: tuple[str, ...],
    entity_anchors: tuple[str, ...],
    asks_for_testimony: bool,
    asks_for_contemporary: bool,
    across_time: bool,
) -> tuple[FacetRequirement, ...]:
    normalized = " ".join(question.lower().split())
    facets = [FacetRequirement("source_role", role) for role in document_roles]
    facets.extend(FacetRequirement("person", anchor) for anchor in entity_anchors)
    if asks_for_testimony and asks_for_contemporary:
        facets.extend((
            FacetRequirement("temporal", "contemporary"),
            FacetRequirement("temporal", "retrospective"),
        ))
    elif across_time:
        facets.append(FacetRequirement("temporal", "multiple_periods"))
    facets.extend(
        FacetRequirement("activity", value)
        for value, pattern in _ACTIVITY_FACET_PATTERNS
        if re.search(pattern, normalized)
    )
    facets.extend(
        FacetRequirement("relationship", value)
        for value, pattern in _RELATIONSHIP_FACET_PATTERNS
        if re.search(pattern, normalized)
    )
    return tuple(dict.fromkeys(facets))


def derive_retrieval_contract(
    question: str,
    *,
    preset_id: str | None = None,
    single_document_mode: bool = False,
    entity_anchors: tuple[str, ...] = (),
) -> RetrievalContract:
    normalized = " ".join(question.lower().split())
    intent_text = normalized.replace("-", " ")
    asks_for_testimony = any(term in intent_text for term in ("oral history", "oral histories", "interview", "testimony", "retrospective"))
    asks_for_contemporary = any(term in normalized for term in ("contemporary", "at the time", "period document", "surviving report"))
    asks_for_prospectus = "prospectus" in normalized or "prospectuses" in normalized
    asks_for_rectors_reports = bool(re.search(dict(_DOCUMENT_ROLE_PATTERNS)["rector_report"], normalized))
    project_anchors = project_anchors_from_question(question)
    document_roles = _document_roles_from_question(question)
    temporal_start_year, temporal_end_year = _question_year_bounds(normalized)
    across_time = any(term in normalized for term in ("across time", "over time", "change", "differ", "earlier", "later", "decade")) or (
        "across" in normalized and bool(_YEAR_PATTERN.search(normalized))
    )
    required_facets = _facets_from_question(
        question,
        document_roles=document_roles,
        entity_anchors=entity_anchors,
        asks_for_testimony=asks_for_testimony,
        asks_for_contemporary=asks_for_contemporary,
        across_time=across_time,
    )

    required_surfaces = ["documentary"]
    if asks_for_testimony:
        required_surfaces.append("oral_history")
    if asks_for_prospectus:
        required_surfaces.append("prospectus")
    if asks_for_rectors_reports:
        required_surfaces.append("rector_report")
    if project_anchors:
        required_surfaces.append("project_report")
    temporal_requirement = "multiple_buckets" if across_time or (asks_for_testimony and asks_for_contemporary) else "none"
    minimum_sources = 1 if single_document_mode else max(2, len(required_surfaces))
    return RetrievalContract(
        retrieval_mode="single_document" if single_document_mode else "bounded_documentary",
        required_evidence_types=tuple(dict.fromkeys(required_surfaces)),
        required_source_presets=(preset_id,) if preset_id else (),
        entity_anchors=entity_anchors,
        project_anchors=project_anchors,
        required_document_roles=document_roles,
        required_facets=required_facets,
        temporal_requirement=temporal_requirement,
        temporal_buckets=(),
        temporal_start_year=temporal_start_year,
        temporal_end_year=temporal_end_year,
        minimum_distinct_sources=minimum_sources,
        initial_max_chunks_per_source=8 if single_document_mode else 1,
        allow_cross_preset_backfill=not bool(project_anchors),
        single_document_mode=single_document_mode,
    )


def candidate_surface(candidate: Mapping[str, Any]) -> str:
    searchable = " ".join(str(candidate.get(field) or "") for field in (
        "source_type", "title", "record_title", "collection_title", "preset_groups", "exact_job_id",
    )).lower()
    if "oral history" in searchable or "interview" in searchable:
        return "oral_history"
    if re.search(dict(_DOCUMENT_ROLE_PATTERNS)["rector_report"], searchable):
        return "rector_report"
    if "prospectus" in searchable:
        return "prospectus"
    if re.search(r"\b(?:calendar|yearbook)\b", searchable):
        return "institutional_publication"
    if re.search(r"\bjob\s+\d{1,3}\b", searchable):
        return "project_report"
    return "documentary"


def candidate_matches_requested_family(candidate: Mapping[str, Any], contract: RetrievalContract) -> bool:
    """Explicit publication families are selection boundaries, not topic synonyms."""
    surfaces = set(contract.required_evidence_types)
    if "rector_report" in surfaces or ("oral_history" in surfaces and "prospectus" in surfaces):
        permitted = surfaces - {"documentary"}
        if "prospectus" in permitted:
            permitted.update({"rector_report", "institutional_publication"})
        return candidate_surface(candidate) in permitted
    return True


def candidate_matches_surface(candidate: Mapping[str, Any], surface: str) -> bool:
    actual = candidate_surface(candidate)
    if surface == "documentary":
        return actual != "oral_history"
    return actual == surface


def candidate_temporal_bucket(candidate: Mapping[str, Any]) -> str | None:
    value = str(candidate.get("display_date") or candidate.get("normalized_date") or "")
    match = _YEAR_PATTERN.search(value)
    if not match:
        return None
    year = int(match.group())
    return f"{year // 10 * 10}s"


def candidate_year(candidate: Mapping[str, Any]) -> int | None:
    value = str(candidate.get("display_date") or candidate.get("normalized_date") or "")
    match = _YEAR_PATTERN.search(value)
    return int(match.group()) if match else None


def candidate_matches_document_role(candidate: Mapping[str, Any], role: str) -> bool:
    searchable = " ".join(str(candidate.get(field) or "") for field in (
        "source_type", "title", "record_title", "collection_title", "preset_groups",
    ))
    pattern = dict(_DOCUMENT_ROLE_PATTERNS).get(role)
    return bool(pattern and re.search(pattern, searchable, flags=re.IGNORECASE))


def candidate_matches_facet(candidate: Mapping[str, Any], facet: FacetRequirement) -> bool:
    if facet.facet_type == "source_role":
        return candidate_matches_document_role(candidate, facet.value)
    if facet.facet_type == "temporal":
        if facet.value == "contemporary":
            return candidate_surface(candidate) != "oral_history"
        if facet.value == "retrospective":
            return candidate_surface(candidate) == "oral_history"
        if facet.value == "multiple_periods":
            return candidate_temporal_bucket(candidate) is not None
    searchable = " ".join(str(candidate.get(field) or "") for field in (
        "chunk_text", "text", "title", "record_title", "collection_title", "source_type",
    )).lower()
    if facet.facet_type == "relationship":
        pattern = dict(_RELATIONSHIP_FACET_PATTERNS).get(facet.value)
        return bool(pattern and re.search(pattern, searchable))
    if facet.facet_type == "activity":
        pattern = dict(_ACTIVITY_FACET_PATTERNS).get(facet.value)
        return bool(pattern and re.search(pattern, searchable))
    return re.sub(r"[-\u2010-\u2014]", " ", facet.value.lower()) in re.sub(r"[-\u2010-\u2014]", " ", searchable)


def diversify_candidates(
    candidates: Iterable[Mapping[str, Any]],
    contract: RetrievalContract,
    limit: int,
) -> tuple[list[dict[str, Any]], RetrievalCoverage]:
    remaining = [
        dict(candidate) for candidate in candidates
        if candidate_matches_requested_family(candidate, contract)
    ]
    if contract.temporal_start_year is not None and contract.temporal_end_year is not None:
        remaining = [
            candidate for candidate in remaining
            if (year := candidate_year(candidate)) is None
            or contract.temporal_start_year <= year <= contract.temporal_end_year
        ]
    if contract.project_anchors:
        scoped = []
        for candidate in remaining:
            matches = candidate_project_anchor_matches(candidate, contract.project_anchors)
            if matches:
                scoped.append({**candidate, "project_anchor_matches": list(matches)})
        if scoped or not contract.allow_cross_preset_backfill:
            remaining = scoped
    if contract.entity_anchors and not contract.project_anchors:
        anchored = [
            candidate for candidate in remaining
            if any(anchor.lower() in str(candidate).lower() for anchor in contract.entity_anchors)
        ]
        if anchored:
            remaining = anchored
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    def source_id(candidate: Mapping[str, Any]) -> str:
        return str(candidate.get("asset_pid") or candidate.get("document_id") or candidate.get("pid") or candidate.get("chunk_id"))

    def eligible(candidate: Mapping[str, Any]) -> bool:
        if contract.single_document_mode:
            return True
        return source_counts.get(source_id(candidate), 0) < contract.initial_max_chunks_per_source

    def take_first(predicate: Any) -> bool:
        for index, candidate in enumerate(remaining):
            if eligible(candidate) and predicate(candidate):
                chosen = remaining.pop(index)
                selected.append(chosen)
                identity = source_id(chosen)
                source_counts[identity] = source_counts.get(identity, 0) + 1
                return True
        return False

    if contract.temporal_requirement == "multiple_buckets" and contract.temporal_start_year is not None:
        dated_years = sorted({year for item in remaining if (year := candidate_year(item)) is not None})
        if dated_years:
            for year in dict.fromkeys((dated_years[0], dated_years[-1])):
                if len(selected) < limit:
                    take_first(lambda item, required=year: candidate_year(item) == required)

    for surface in contract.required_evidence_types:
        while len(selected) < limit and sum(candidate_matches_surface(item, surface) for item in selected) < contract.minimum_sources_per_required_surface:
            if not take_first(lambda item, required=surface: candidate_matches_surface(item, required)):
                break
    for facet in contract.required_facets:
        if len(selected) >= limit or any(candidate_matches_facet(item, facet) for item in selected):
            continue
        take_first(lambda item, required=facet: candidate_matches_facet(item, required))
    for role in contract.required_document_roles:
        if len(selected) >= limit or any(candidate_matches_document_role(item, role) for item in selected):
            continue
        take_first(lambda item, required=role: candidate_matches_document_role(item, required))
    for project_anchor in contract.project_anchors:
        if len(selected) >= limit:
            break
        if any(project_anchor in item.get("project_anchor_matches", []) for item in selected):
            continue
        take_first(lambda item, required=project_anchor: required in item.get("project_anchor_matches", []))
    for bucket in contract.temporal_buckets:
        if len(selected) < limit and not any(candidate_temporal_bucket(item) == bucket for item in selected):
            take_first(lambda item, required=bucket: candidate_temporal_bucket(item) == required)
    if contract.temporal_requirement == "multiple_buckets" and not contract.temporal_buckets:
        while len(selected) < limit:
            selected_buckets = {
                bucket for item in selected if (bucket := candidate_temporal_bucket(item))
            }
            if len(selected_buckets) >= 2:
                break
            if not take_first(
                lambda item, found=selected_buckets: (
                    (bucket := candidate_temporal_bucket(item)) is not None and bucket not in found
                )
            ):
                break
    while len(selected) < limit and len({source_id(item) for item in selected}) < contract.minimum_distinct_sources:
        if not take_first(lambda _item: True):
            break
    while len(selected) < limit:
        if not take_first(lambda _item: True):
            if contract.single_document_mode:
                break
            contract = replace(contract, initial_max_chunks_per_source=limit)
            if not take_first(lambda _item: True):
                break

    found_surfaces = tuple(sorted(
        surface
        for surface in contract.required_evidence_types
        if any(candidate_matches_surface(item, surface) for item in selected)
    ))
    missing_surfaces = tuple(sorted(set(contract.required_evidence_types) - set(found_surfaces)))
    found_buckets = tuple(sorted({bucket for item in selected if (bucket := candidate_temporal_bucket(item))}))
    distinct_sources = len({source_id(item) for item in selected})
    entity_found = None if not contract.entity_anchors else any(
        any(candidate_matches_facet(item, FacetRequirement("person", anchor)) for anchor in contract.entity_anchors)
        for item in selected
    )
    project_found = None if not contract.project_anchors else any(
        item.get("project_anchor_matches")
        for item in selected
    )
    found_project_anchors = tuple(
        anchor for anchor in contract.project_anchors
        if any(anchor in item.get("project_anchor_matches", []) for item in selected)
    )
    missing_project_anchors = tuple(
        anchor for anchor in contract.project_anchors if anchor not in found_project_anchors
    )
    found_document_roles = tuple(
        role for role in contract.required_document_roles
        if any(candidate_matches_document_role(item, role) for item in selected)
    )
    missing_document_roles = tuple(
        role for role in contract.required_document_roles if role not in found_document_roles
    )
    found_facets = tuple(
        facet for facet in contract.required_facets
        if (
            len(found_buckets) >= 2
            if facet == FacetRequirement("temporal", "multiple_periods")
            else any(candidate_matches_facet(item, facet) for item in selected)
        )
    )
    missing_facets = tuple(
        facet for facet in contract.required_facets if facet not in found_facets
    )
    required_facet_records = [facet.as_dict() for facet in contract.required_facets]
    for item in selected:
        item["required_facets"] = required_facet_records
        item["supported_facets"] = [
            facet.as_dict() for facet in contract.required_facets
            if candidate_matches_facet(item, facet)
            and facet != FacetRequirement("temporal", "multiple_periods")
        ]
        item["facet_contributions"] = [
            {
                "facet_type": "temporal",
                "value": "multiple_periods",
                "component": candidate_temporal_bucket(item),
            }
            for facet in contract.required_facets
            if facet == FacetRequirement("temporal", "multiple_periods")
            and candidate_temporal_bucket(item) is not None
        ]
    requirements = [
        not missing_surfaces,
        distinct_sources >= contract.minimum_distinct_sources,
        contract.temporal_requirement == "none" or (
            set(contract.temporal_buckets).issubset(found_buckets)
            if contract.temporal_buckets
            else len(found_buckets) >= 2
        ),
        (not contract.entity_anchors or bool(contract.project_anchors) or entity_found is not False),
        project_found is not False,
        not missing_project_anchors,
        not missing_document_roles,
        not missing_facets,
    ]
    status = "satisfied" if all(requirements) else ("partially_satisfied" if selected else "unsatisfied")
    return selected, RetrievalCoverage(
        coverage_status=status,
        required_surfaces_found=found_surfaces,
        required_surfaces_missing=missing_surfaces,
        distinct_source_count=distinct_sources,
        temporal_buckets_found=found_buckets,
        target_entity_evidence_found=entity_found,
        target_project_evidence_found=project_found,
        project_anchors_found=found_project_anchors,
        project_anchors_missing=missing_project_anchors,
        document_roles_found=found_document_roles,
        document_roles_missing=missing_document_roles,
        facets_found=found_facets,
        facets_missing=missing_facets,
    )