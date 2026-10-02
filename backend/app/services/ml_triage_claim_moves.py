"""Auditable benchmark-only required-claim-move evaluation."""

from __future__ import annotations

import hashlib
import re
from typing import Any


_MOVE_STOP_WORDS = {
    "and", "are", "but", "from", "how", "into", "its", "not", "only", "or",
    "that", "the", "their", "these", "this", "what", "with",
}


def _move_id(label: str) -> str:
    digest = hashlib.sha256(label.casefold().encode("utf-8")).hexdigest()[:16]
    return f"move:{digest}"


def required_moves(case: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"required_claim_move_id": _move_id(label), "label": label}
        for value in case.get("required_claim_moves", "").split(";")
        if (label := " ".join(value.split()))
    ]


def _move_terms(label: str) -> set[str]:
    return {
        term.casefold()
        for term in re.findall(r"[A-Za-z]{4,}", label)
        if term.casefold() not in _MOVE_STOP_WORDS
    }


def _documentary_supporting_claims(move_label: str, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Require a conservative lexical bridge from a required move to final prose."""
    terms = _move_terms(move_label)
    if not terms:
        return []
    threshold = min(2, len(terms))
    return [
        claim for claim in claims
        if len(terms.intersection({
            term.casefold() for term in re.findall(r"[A-Za-z]{4,}", str(claim.get("text") or ""))
        })) >= threshold
    ]


def evaluate_required_claim_moves(case: dict[str, str], response: dict[str, Any]) -> dict[str, Any]:
    """Evaluate rendered claim-plan coverage without assigning every claim to every move."""
    claims = (response.get("final_claim_plan") or {}).get("claims") or []
    rendered_claim_ids = {
        claim_id
        for paragraph in response.get("answer_paragraphs") or []
        for rendered in paragraph.get("claims") or []
        for claim_id in rendered.get("claim_ids") or []
    }
    route_family = (response.get("retrieval") or {}).get("route_family")
    evaluations = []
    for move in required_moves(case):
        rendered_claims = [claim for claim in claims if claim.get("claim_id") in rendered_claim_ids]
        if route_family == "AUTHORITY_ONLY":
            supported = [claim for claim in rendered_claims if claim.get("supporting_authority_ids")]
        else:
            supported = _documentary_supporting_claims(move["label"], rendered_claims)
        if not rendered_claims:
            status = "NOT_COVERED"
            reason = "No final claim-plan item for this move was rendered in the answer."
        elif supported:
            status = "COVERED"
            reason = "A rendered final claim-plan item provides the required move's explicit support."
        else:
            status = "NOT_COVERED"
            reason = "Rendered final claim-plan items do not explicitly support this required move."
        evaluations.append({
            **move,
            "supporting_claim_ids": [claim["claim_id"] for claim in supported],
            "supporting_evidence_card_ids": sorted({card_id for claim in supported for card_id in claim.get("supporting_evidence_card_ids", [])}),
            "supporting_authority_ids": sorted({authority_id for claim in supported for authority_id in claim.get("supporting_authority_ids", [])}),
            "support_types": sorted({claim.get("claim_type") for claim in supported if claim.get("claim_type")}),
            "rendered": bool(supported),
            "status": status,
            "reason": reason,
        })
    return {
        "schema_version": "ml-triage-required-claim-moves-v1",
        "machine_evaluable": True,
        "statuses": evaluations,
        "coverage": {
            "covered": sum(item["status"] == "COVERED" for item in evaluations),
            "not_covered": sum(item["status"] == "NOT_COVERED" for item in evaluations),
            "not_applicable": sum(item["status"] == "NOT_APPLICABLE" for item in evaluations),
            "total": len(evaluations),
        },
    }
