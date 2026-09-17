"""Append-only event records for research-output provenance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.research_outputs import ProvenanceEvent
from app.services.provenance_integrity import provenance_event_digest


def record_provenance_event(
    db: Any,
    event_type: str,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
    actor: str = "system",
) -> ProvenanceEvent:
    previous = db.query(ProvenanceEvent).filter(
        ProvenanceEvent.subject_type == subject_type,
        ProvenanceEvent.subject_id == subject_id,
    ).order_by(ProvenanceEvent.created_at.desc()).first()
    created_at = datetime.utcnow()
    values = {
        "event_id": f"prov-{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "actor": actor,
        "previous_event_sha256": previous.event_sha256 if previous else None,
        "payload_json": payload,
        "created_at": created_at.isoformat(),
    }
    event = ProvenanceEvent(
        **values,
        event_sha256=provenance_event_digest(values),
        created_at=created_at,
    )
    db.add(event)
    return event