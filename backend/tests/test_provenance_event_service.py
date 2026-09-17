import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.provenance_integrity import provenance_event_digest


class ProvenanceEventIntegrityTests(unittest.TestCase):
    def test_event_digest_binds_predecessor_and_payload(self):
        event = {
            "event_id": "prov-1", "event_type": "query_run.recorded",
            "subject_type": "query_run", "subject_id": "query-1", "actor": "system",
            "previous_event_sha256": None, "payload_json": {"provenance_sha256": "a" * 64},
            "created_at": "2026-09-17T00:00:00",
        }
        successor = {**event, "previous_event_sha256": "b" * 64}
        changed_payload = {**event, "payload_json": {"provenance_sha256": "c" * 64}}
        self.assertNotEqual(provenance_event_digest(event), provenance_event_digest(successor))
        self.assertNotEqual(provenance_event_digest(event), provenance_event_digest(changed_payload))