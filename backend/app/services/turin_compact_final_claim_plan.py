"""Experiment-only compact final claim-plan contract for frozen stage snapshots."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field


CompactClaimText = str
FacetRecord = dict[str, str]
EvidenceClaimType = Literal[
    "DIRECT_DOCUMENTARY",
    "RETROSPECTIVE_TESTIMONY",
    "DATABASE_AUTHORITY",
    "CROSS_SOURCE_INFERENCE",
    "QUALIFIED_SYNTHESIS",
]
ClaimEvidenceStatus = Literal[
    "SUPPORTED",
    "SUPPORTED_WITH_QUALIFICATION",
    "CONFLICTING_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "INVALID_EVIDENCE_TYPE",
]
AnswerShape = Literal[
    "THEMATIC_SYNTHESIS",
    "COMPARE_CONTRAST",
    "TEMPORAL_CHANGE",
    "AUTHORITY_DOCUMENTARY_SYNTHESIS",
    "BOUNDED_MISSINGNESS",
    "SINGLE_REPORT_SUMMARY",
]

_LIMIT_STOP_TERMS = {
    "about", "activity", "cannot", "corpus", "current", "digitised", "does", "evidence",
    "establish", "from", "have", "into", "records", "selected", "that", "the", "this", "with",
}


def relevant_final_limits(
    evidence_map: Mapping[str, Any], question: str, claim_texts: list[str]
) -> list[tuple[str, str]]:
    context_terms = {
        term for term in re.findall(r"[a-z]{4,}", f"{question} {' '.join(claim_texts)}".lower())
        if term not in _LIMIT_STOP_TERMS
    }
    limits = []
    for index, text in enumerate(evidence_map["NOT_ESTABLISHED"], start=1):
        limit_terms = {
            term for term in re.findall(r"[a-z]{4,}", str(text).lower())
            if term not in _LIMIT_STOP_TERMS
        }
        if limit_terms & context_terms:
            limits.append((f"limit-{index}", str(text)))
    return limits


def comparison_move_covered(plan: "FinalClaimPlan", question: str) -> bool:
    labels = list(dict.fromkeys(
        match.group(0).title()
        for match in re.finditer(r"\b(?:job|project|report)\s+\d+\b", question, re.IGNORECASE)
    ))
    return len(labels) >= 2 and any(
        claim.claim_type == "QUALIFIED_SYNTHESIS"
        and len(claim.supporting_source_ids) >= 2
        and len(claim.supporting_evidence_card_ids) >= 2
        and all(label.lower() in claim.text.lower() for label in labels[:2])
        for claim in plan.claims
    )


class CompactFinalClaim(BaseModel):
    claim_id: str = Field(pattern=r"^c[1-8]$")
    claim_type: EvidenceClaimType
    text: CompactClaimText = Field(min_length=1, max_length=300)
    proposition: CompactClaimText | None = Field(default=None, min_length=1, max_length=300)
    supporting_source_ids: list[str] = Field(default_factory=list, max_length=3)
    supporting_evidence_card_ids: list[str] = Field(default_factory=list, max_length=3)
    contradicting_or_qualifying_evidence_ids: list[str] = Field(default_factory=list, max_length=3)
    supporting_authority_ids: list[str] = Field(default_factory=list, max_length=3)
    supporting_cross_source_inference_ids: list[str] = Field(default_factory=list, max_length=3)
    required_evidence_families: list[str] = Field(default_factory=list, max_length=8)
    supported_facets: list[FacetRecord] = Field(default_factory=list, max_length=16)
    limit_ids: list[str] = Field(default_factory=list, max_length=3)
    evidence_status: ClaimEvidenceStatus = "SUPPORTED"
    temporal_position_if_relevant: str | None = None
    required_qualification: str | None = None


class CompactFinalClaimPlan(BaseModel):
    question_intent: str = "EVIDENCE_LED_SYNTHESIS"
    answer_shape: AnswerShape = "THEMATIC_SYNTHESIS"
    claims: list[CompactFinalClaim] = Field(default_factory=list, max_length=8)
    comparison_axes: list[str] = Field(default_factory=list, max_length=4)
    open_uncertainties: list[str] = Field(default_factory=list, max_length=6)
    proposed_scoped_limit: str | None = None
    overall_limit_ids: list[str] = Field(default_factory=list, max_length=6)
    required_facets: list[FacetRecord] = Field(default_factory=list, max_length=16)
    facets_found: list[FacetRecord] = Field(default_factory=list, max_length=16)
    facets_missing: list[FacetRecord] = Field(default_factory=list, max_length=16)
    facet_contributions: list[dict[str, Any]] = Field(default_factory=list, max_length=16)


FinalClaimPlan = CompactFinalClaimPlan


def classify_answer_shape(question: str, has_authority: bool = False) -> AnswerShape:
    lowered = question.lower()
    if has_authority:
        return "AUTHORITY_DOCUMENTARY_SYNTHESIS"
    if any(term in lowered for term in ("responsible", "prove that", "establish that")):
        return "BOUNDED_MISSINGNESS"
    if any(term in lowered for term in ("compare", "contrast", "differ", "difference", "variant", "whereas")):
        return "COMPARE_CONTRAST"
    if any(term in lowered for term in ("over time", "chronolog", "change between", "changed from", "what changes", "earlier", "later")):
        return "TEMPORAL_CHANGE"
    if any(term in lowered for term in ("final report", "surviving report", "single report")):
        return "SINGLE_REPORT_SUMMARY"
    return "THEMATIC_SYNTHESIS"


def compact_claim_plan_input(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    evidence_map = snapshot["evidence_map"]
    cross_source = snapshot["cross_source_analysis"]
    limits = [
        {"limit_id": f"limit-{index}", "text": text}
        for index, text in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)
    ]
    cross_inferences = [
        {"inference_id": f"cross-source-inference-{index}", "text": text}
        for index, text in enumerate(cross_source["cross_source_inferences"], start=1)
    ]
    return {
        "validated_evidence": {
            "direct_documentary": [
                {"source_id": item["source_id"], "claim": item["claim"]}
                for item in evidence_map["DIRECT_DOCUMENTARY"]
            ],
            "contextual": [
                {"source_id": item["source_id"], "claim": item["claim"]}
                for item in evidence_map["CONTEXTUAL"]
            ],
            "source_inferences": [
                {"source_id": item["source_id"], "claim": item["claim"]}
                for item in evidence_map["CROSS_SOURCE_INFERENCE"]
            ],
        },
        "validated_cross_source_inferences": cross_inferences,
        "validated_limits": limits,
        "authority_context_passed_to_final": snapshot["authority"]["authority_context_passed_to_final"],
    }


def build_compact_claim_plan_prompt(question: str, compact_input: Mapping[str, Any]) -> str:
    return (
        "Analyse only the supplied validated evidence index. Return JSON only. "
        "Create a bounded claim plan, not prose: no paragraphs, quotations, citations, source metadata, "
        "or regenerated evidence objects. Select only claims that are supported by IDs in the index. "
        "DIRECT_DOCUMENTARY claims require supporting_source_ids from direct_documentary. "
        "DATABASE_AUTHORITY claims require supporting_authority_ids, but no authority context is supplied here. "
        "CROSS_SOURCE_INFERENCE claims require supporting_cross_source_inference_ids. "
        "Use limit_ids and overall_limit_ids only from validated_limits. Do not invent IDs. "
        "QUESTION: " + question + "\n\nVALIDATED EVIDENCE INDEX:\n" + json.dumps(compact_input, ensure_ascii=True)
    )


def validate_compact_claim_plan(plan: CompactFinalClaimPlan, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    evidence_map = snapshot["evidence_map"]
    direct_source_ids = {item["source_id"] for item in evidence_map["DIRECT_DOCUMENTARY"]}
    evidence_card_ids = {
        str(card.get("evidence_card_id"))
        for card in evidence_map.get("EVIDENCE_CARDS", [])
    }
    evidence_cards_by_id = {
        str(card.get("evidence_card_id")): card
        for card in evidence_map.get("EVIDENCE_CARDS", [])
    }
    source_ids = direct_source_ids | {item["source_id"] for item in evidence_map["CONTEXTUAL"]} | {item["source_id"] for item in evidence_map["CROSS_SOURCE_INFERENCE"]}
    authority_ids = {
        str(authority.get("authority_id"))
        for authority in snapshot["authority"]["authority_context_passed_to_final"]
        if authority.get("authority_id") is not None
    }
    limit_ids = {f"limit-{index}" for index, _ in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)}
    required_facets = {
        (str(facet.get("facet_type") or ""), str(facet.get("value") or ""))
        for card in evidence_map.get("EVIDENCE_CARDS", [])
        for facet in card.get("required_facets") or []
    }
    supported_facets = {
        (str(facet.get("facet_type") or ""), str(facet.get("value") or ""))
        for card in evidence_map.get("EVIDENCE_CARDS", [])
        for facet in card.get("supported_facets") or []
    }
    for index, _facet in enumerate(required_facets - supported_facets, start=len(limit_ids) + 1):
        limit_ids.add(f"limit-{index}")
    inadmissible_cards = [
        card for card in evidence_map.get("EVIDENCE_CARDS", [])
        if (card.get("claim_admissibility") or {}).get("decision", "DIRECT_SUPPORT") != "DIRECT_SUPPORT"
    ]
    if inadmissible_cards:
        limit_ids.add(f"limit-{len(limit_ids) + 1}")
    inference_ids = {
        f"cross-source-inference-{index}"
        for index, _ in enumerate(snapshot["cross_source_analysis"].get("cross_source_inferences", []), start=1)
    }
    invalid = {"source_refs": [], "evidence_card_refs": [], "authority_refs": [], "limit_refs": [], "inference_refs": [], "claim_types": []}
    seen_claim_ids = set()
    claim_results = []
    for claim in plan.claims:
        claim_errors: list[str] = []
        if claim.claim_id in seen_claim_ids:
            claim_errors.append("duplicate claim_id")
        seen_claim_ids.add(claim.claim_id)
        invalid["source_refs"].extend(reference for reference in claim.supporting_source_ids if reference not in source_ids)
        invalid["evidence_card_refs"].extend(reference for reference in claim.supporting_evidence_card_ids if reference not in evidence_card_ids)
        invalid["authority_refs"].extend(reference for reference in claim.supporting_authority_ids if reference not in authority_ids)
        invalid["limit_refs"].extend(reference for reference in claim.limit_ids if reference not in limit_ids)
        invalid["inference_refs"].extend(reference for reference in claim.supporting_cross_source_inference_ids if reference not in inference_ids)
        if claim.claim_type in {"DIRECT_DOCUMENTARY", "RETROSPECTIVE_TESTIMONY", "QUALIFIED_SYNTHESIS"} and (not claim.supporting_source_ids or not set(claim.supporting_source_ids).issubset(direct_source_ids)):
            claim_errors.append("direct claim lacks documentary support")
        if claim.claim_type in {"DIRECT_DOCUMENTARY", "RETROSPECTIVE_TESTIMONY", "QUALIFIED_SYNTHESIS"} and evidence_card_ids and not claim.supporting_evidence_card_ids:
            claim_errors.append("direct claim lacks evidence card support")
        card_types = {
            evidence_cards_by_id[reference].get("evidence_type") or "DIRECT_DOCUMENTARY"
            for reference in claim.supporting_evidence_card_ids
            if reference in evidence_cards_by_id
        }
        if claim.claim_type == "DIRECT_DOCUMENTARY" and card_types - {"DIRECT_DOCUMENTARY"}:
            claim_errors.append("documentary claim uses non-documentary evidence")
        inadmissible_card_ids = [
            reference
            for reference in claim.supporting_evidence_card_ids
            if reference in evidence_cards_by_id
            and (evidence_cards_by_id[reference].get("claim_admissibility") or {}).get("decision", "DIRECT_SUPPORT") != "DIRECT_SUPPORT"
        ]
        if inadmissible_card_ids:
            claim_errors.append(
                "inadmissible evidence card: " + ", ".join(inadmissible_card_ids)
            )
        if claim.claim_type == "RETROSPECTIVE_TESTIMONY" and card_types != {"RETROSPECTIVE_TESTIMONY"}:
            claim_errors.append("testimony claim lacks testimony evidence")
        if claim.claim_type == "DATABASE_AUTHORITY" and not claim.supporting_authority_ids:
            claim_errors.append("authority claim lacks authority support")
        if claim.claim_type == "CROSS_SOURCE_INFERENCE" and not claim.supporting_cross_source_inference_ids:
            claim_errors.append("inference claim lacks cross-source inference support")
        support_text = " ".join(
            str(card.get("normalized_proposition") or card.get("verbatim_passage") or "")
            for card in evidence_cards_by_id.values()
            if card.get("source_id") in claim.supporting_source_ids
        ).lower()
        relation_requirements = {
            "collaborat": ("collaborat",),
            "co-author": ("co-author", "coauthor"),
            "authored": ("authored", "author of", "written by"),
            "project lead": ("project lead", "led by"),
            "caused": ("caused", "because of", "resulted in"),
            "intended": ("intended", "intention", "aimed to"),
        }
        claim_text = claim.text.lower()
        for asserted_term, evidence_terms in relation_requirements.items():
            if (
                claim.claim_type != "DATABASE_AUTHORITY"
                and asserted_term in claim_text
                and not any(term in support_text for term in evidence_terms)
            ):
                claim_errors.append(
                    f"{asserted_term} is not explicit in supporting documentary evidence"
                )
        invalid["claim_types"].extend(f"{claim.claim_id}: {error}" for error in claim_errors)
        wrong_type = any("non-documentary evidence" in error or "testimony evidence" in error for error in claim_errors)
        status: ClaimEvidenceStatus = (
            "INVALID_EVIDENCE_TYPE" if wrong_type
            else "INSUFFICIENT_EVIDENCE" if claim_errors
            else "SUPPORTED_WITH_QUALIFICATION" if claim.limit_ids or claim.required_qualification
            else claim.evidence_status
        )
        claim_results.append({
            "claim_id": claim.claim_id,
            "status": status,
            "supporting_evidence_ids": list(claim.supporting_evidence_card_ids),
            "supporting_source_ids": list(claim.supporting_source_ids),
            "supporting_authority_ids": list(claim.supporting_authority_ids),
            "reasons": claim_errors,
        })
    invalid["limit_refs"].extend(reference for reference in plan.overall_limit_ids if reference not in limit_ids)
    return {"valid": not any(invalid.values()), "invalid": invalid, "claim_results": claim_results}


def compile_final_claim_plan(
    evidence_map: Mapping[str, Any],
    cross_source_analysis: Mapping[str, Any],
    authority_context: list[Mapping[str, Any]] | None = None,
    question: str = "",
) -> FinalClaimPlan:
    """Compile only pre-validated evidence classes; never infer a class from text."""
    claims: list[dict[str, Any]] = []
    evidence_cards_active = "EVIDENCE_CARDS" in evidence_map
    evidence_cards = list(evidence_map.get("EVIDENCE_CARDS") or [])
    source_dates_by_card_id = {
        str(card.get("evidence_card_id") or ""): str(card.get("source_date") or "")
        for card in evidence_cards
    }

    def card_is_admissible(card: Mapping[str, Any]) -> bool:
        return (card.get("claim_admissibility") or {}).get("decision", "DIRECT_SUPPORT") == "DIRECT_SUPPORT"

    def unique_facets(records: list[Mapping[str, Any]]) -> list[FacetRecord]:
        facets: list[FacetRecord] = []
        seen: set[tuple[str, str]] = set()
        for record in records:
            facet_type = str(record.get("facet_type") or "")
            value = str(record.get("value") or "")
            if not facet_type or not value or (facet_type, value) in seen:
                continue
            facets.append({"facet_type": facet_type, "value": value})
            seen.add((facet_type, value))
        return facets

    required_facets = unique_facets([
        facet for card in evidence_cards for facet in card.get("required_facets") or []
    ])
    found_facets = unique_facets([
        facet for card in evidence_cards for facet in card.get("supported_facets") or []
    ])
    facet_contributions = []
    for facet in required_facets:
        contributions = [
            {
                "component": str(contribution.get("component") or ""),
                "evidence_card_id": str(card.get("evidence_card_id") or ""),
                "source_id": str(card.get("source_id") or ""),
                "proposition": str(card.get("normalized_proposition") or ""),
            }
            for card in evidence_cards
            for contribution in card.get("facet_contributions") or []
            if contribution.get("facet_type") == facet["facet_type"]
            and contribution.get("value") == facet["value"]
        ]
        if contributions:
            facet_contributions.append({"facet": facet, "contributions": contributions})
        if facet == {"facet_type": "temporal", "value": "multiple_periods"} and len({item["component"] for item in contributions if item["component"]}) >= 2:
            found_facets = unique_facets([*found_facets, facet])
    missing_facets = [facet for facet in required_facets if facet not in found_facets]

    comparison_labels = list(dict.fromkeys(
        match.group(0).title()
        for match in re.finditer(r"\b(?:job|project|report)\s+\d+\b", question, re.IGNORECASE)
    )) if any(term in question.lower() for term in ("compare", "differ", "difference")) else []

    def add_claim(claim_type: str, text: str, **references: list[str]) -> None:
        if len(claims) >= 8:
            return
        proposition = text[:300]
        if "##" in proposition or "|" in proposition:
            return
        source_dates = [
            source_dates_by_card_id[card_id]
            for card_id in references.get("supporting_evidence_card_ids", [])
            if source_dates_by_card_id.get(card_id)
        ]
        claims.append({
            "claim_id": f"c{len(claims) + 1}", "claim_type": claim_type,
            "text": proposition, "proposition": proposition,
            "temporal_position_if_relevant": source_dates[0] if len(source_dates) == 1 else None,
            **references,
        })

    direct_documentary = list(evidence_map["DIRECT_DOCUMENTARY"])
    if all(term in question.lower() for term in ("teaching", "learning", "archive")):
        theme_terms = (
            ("curriculum", "professional", "practice"),
            ("scientific", "system", "research", "measurement", "model"),
            ("comput", "cad"),
            ("experiential", "simulation", "learning by doing"),
        )
        selected_source_ids: set[str] = set()
        themed = []
        for terms in theme_terms:
            candidate = next(
                (
                    item for item in direct_documentary
                    if item.get("source_id") not in selected_source_ids
                    and any(term in str(item.get("claim") or "").lower() for term in terms)
                ),
                None,
            )
            if candidate is not None:
                themed.append(candidate)
                selected_source_ids.add(candidate["source_id"])
        direct_documentary = [
            *themed,
            *[item for item in direct_documentary if item.get("source_id") not in selected_source_ids],
        ]

    inadmissible_cards = []
    for item in direct_documentary:
        if comparison_labels and len(claims) >= 7:
            break
        if evidence_cards_active and not item.get("evidence_card_id"):
            continue
        card = next(
            (
                candidate for candidate in evidence_map.get("EVIDENCE_CARDS", [])
                if candidate.get("evidence_card_id") == item.get("evidence_card_id")
            ),
            {},
        )
        if evidence_cards_active and not card_is_admissible(card):
            inadmissible_cards.append(card)
            continue
        claim_type = (
            "RETROSPECTIVE_TESTIMONY"
            if card.get("evidence_type") == "RETROSPECTIVE_TESTIMONY"
            else "DIRECT_DOCUMENTARY"
        )
        add_claim(
            claim_type, item["claim"],
            supporting_source_ids=[item["source_id"]], supporting_authority_ids=[],
            supporting_evidence_card_ids=[item["evidence_card_id"]] if item.get("evidence_card_id") else [],
            supporting_cross_source_inference_ids=[],
            required_evidence_families=list(card.get("required_evidence_families") or []),
            supported_facets=list(card.get("supported_facets") or []),
            limit_ids=[],
        )
    if len(comparison_labels) >= 2:
        family_items = []
        for label in comparison_labels[:2]:
            candidates = [
                candidate
                for candidate in evidence_map["DIRECT_DOCUMENTARY"]
                if not evidence_cards_active or card_is_admissible(next(
                    (card for card in evidence_cards if card.get("evidence_card_id") == candidate.get("evidence_card_id")),
                    {},
                ))
                if re.search(rf"\b{re.escape(label)}\b", str(candidate.get("claim") or ""), re.IGNORECASE)
            ]
            item = max(
                candidates,
                key=lambda candidate: (
                    sum(
                        term in str(candidate.get("claim") or "").lower()
                        for term in ("design", "system", "control", "implement", "improve", "working", "condition", "console")
                    ),
                    len(str(candidate.get("claim") or "")),
                ),
                default=None,
            )
            if item and (not evidence_cards_active or item.get("evidence_card_id")):
                family_items.append((label, item))
        if len(family_items) == 2:
            (left_label, left), (right_label, right) = family_items
            left_claim = re.sub(rf"^{re.escape(left_label)}\s*:\s*", "", left["claim"], flags=re.IGNORECASE)
            right_claim = re.sub(rf"^{re.escape(right_label)}\s*:\s*", "", right["claim"], flags=re.IGNORECASE)
            add_claim(
                "QUALIFIED_SYNTHESIS",
                f"{left_label} foregrounds {left_claim[:85].rstrip()}; whereas {right_label} foregrounds {right_claim[:85].rstrip()}. The records establish this contrast, not a complete project history, team continuity, causation, or implementation success.",
                supporting_source_ids=[left["source_id"], right["source_id"]],
                supporting_evidence_card_ids=[left["evidence_card_id"], right["evidence_card_id"]],
                supporting_authority_ids=[], supporting_cross_source_inference_ids=[], limit_ids=[],
            )
    for authority in authority_context or []:
        fields = authority.get("fields") or {}
        authority_id = str(authority.get("authority_id") or "")
        text = fields.get("label") or fields.get("title")
        if authority_id and text:
            add_claim(
                "DATABASE_AUTHORITY", str(text), supporting_source_ids=[],
                supporting_evidence_card_ids=[],
                supporting_authority_ids=[authority_id], supporting_cross_source_inference_ids=[], limit_ids=[],
            )
    valid_source_ids = {
        item["source_id"]
        for evidence_class in ("DIRECT_DOCUMENTARY", "CONTEXTUAL", "CROSS_SOURCE_INFERENCE")
        for item in evidence_map[evidence_class]
    }
    inference_sources = cross_source_analysis.get("cross_source_inference_sources", {})
    for index, inference in enumerate(cross_source_analysis.get("cross_source_inferences", []), start=1):
        supporting_source_ids = list(dict.fromkeys(inference_sources.get(inference, [])))
        if not supporting_source_ids or not set(supporting_source_ids).issubset(valid_source_ids):
            continue
        add_claim(
            "CROSS_SOURCE_INFERENCE", inference,
            supporting_source_ids=supporting_source_ids, supporting_authority_ids=[],
            supporting_evidence_card_ids=[],
            supporting_cross_source_inference_ids=[f"cross-source-inference-{index}"], limit_ids=[],
        )

    relevant_limits = relevant_final_limits(
        evidence_map, question, [claim["text"] for claim in claims],
    ) if question else [
        (f"limit-{index}", str(text))
        for index, text in enumerate(evidence_map["NOT_ESTABLISHED"], start=1)
    ]
    facet_limits = [
        f"Available evidence does not establish the requested {facet['value']} {facet['facet_type']}."
        for facet in missing_facets
    ]
    if inadmissible_cards:
        facet_limits.append(
            "Available evidence is contextual but does not directly establish the requested claim."
        )
    next_limit = len(relevant_limits) + 1
    relevant_limits.extend(
        (f"limit-{next_limit + index}", text)
        for index, text in enumerate(facet_limits)
    )
    limit_ids = [limit_id for limit_id, _ in relevant_limits]
    overall_limit_ids = limit_ids[:6]
    for index, limit_id in enumerate(limit_ids[6:]):
        if not claims:
            break
        claims[index % len(claims)]["limit_ids"].append(limit_id)
    answer_shape = classify_answer_shape(question, bool(authority_context))
    proposed_scoped_limit = relevant_limits[0][1] if relevant_limits else None
    for claim in claims:
        claim["evidence_status"] = (
            "SUPPORTED_WITH_QUALIFICATION"
            if claim.get("limit_ids") or (answer_shape == "BOUNDED_MISSINGNESS" and proposed_scoped_limit)
            else "SUPPORTED"
        )
        if claim["evidence_status"] == "SUPPORTED_WITH_QUALIFICATION":
            claim["required_qualification"] = proposed_scoped_limit
    plan = FinalClaimPlan.model_validate({
        "question_intent": "EVIDENCE_LED_SYNTHESIS",
        "answer_shape": answer_shape,
        "claims": claims,
        "comparison_axes": comparison_labels[:2],
        "open_uncertainties": [text for _, text in relevant_limits[:6]],
        "proposed_scoped_limit": proposed_scoped_limit,
        "overall_limit_ids": overall_limit_ids,
        "required_facets": required_facets,
        "facets_found": found_facets,
        "facets_missing": missing_facets,
        "facet_contributions": facet_contributions,
    })
    snapshot = {
        "evidence_map": evidence_map,
        "cross_source_analysis": cross_source_analysis,
        "authority": {"authority_context_passed_to_final": authority_context or []},
    }
    validation = validate_compact_claim_plan(plan, snapshot)
    if not validation["valid"]:
        raise ValueError(f"Deterministic final claim-plan validation failed: {validation['invalid']}")
    return plan