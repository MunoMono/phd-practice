"""Immutable claim snapshots for mutable researcher review states."""

from __future__ import annotations

from typing import Any

from app.models.research_outputs import Claim, ClaimRevision


def record_claim_revision(db: Any, claim: Claim, reason: str) -> ClaimRevision:
    previous = db.query(ClaimRevision).filter(
        ClaimRevision.claim_id == claim.claim_id,
    ).order_by(ClaimRevision.revision.desc()).first()
    revision = (previous.revision if previous else 0) + 1
    snapshot = {
        "claim_id": claim.claim_id,
        "claim_text": claim.claim_text,
        "support_level": claim.support_level,
        "caveats": claim.caveats,
        "reviewer_status": claim.reviewer_status,
    }
    record = ClaimRevision(
        claim_id=claim.claim_id,
        revision=revision,
        reason=reason,
        snapshot_json=snapshot,
    )
    db.add(record)
    return record