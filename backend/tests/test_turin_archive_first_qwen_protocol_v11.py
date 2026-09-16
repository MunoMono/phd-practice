import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_archive_first_qwen_protocol_v11 import parse_and_validate


class ArchiveFirstQwenProtocolV11Tests(unittest.TestCase):
    def setUp(self):
        self.sources = {"S1", "S2"}

    def test_accepts_empty_arrays_and_a_cited_limit(self):
        parsed, result = parse_and_validate('{"direct":[],"inferences":[],"contested":[],"limits":[{"claim":"The supplied evidence does not establish outcomes.","source_ids":["S1","S2"]}]}', self.sources)
        self.assertIsNotNone(parsed)
        self.assertTrue(result["valid"])

    def test_flags_q12_style_missectioned_limit(self):
        _, result = parse_and_validate('{"direct":[{"claim":"There is no direct evidence of a role.","source_ids":["S1"]}],"inferences":[],"contested":[],"limits":[]}', self.sources)
        self.assertIn("MISSECTIONED_LIMIT", result["flags"])

    def test_flags_invalid_source_ids(self):
        _, result = parse_and_validate('{"direct":[],"inferences":[{"claim":"Inference: relation.","source_ids":["S9"]}],"contested":[],"limits":[]}', self.sources)
        self.assertIn("INVALID_SOURCE_ID", result["flags"])

    def test_rejects_truncated_json(self):
        _, result = parse_and_validate('{"direct":[', self.sources)
        self.assertIn("INVALID_JSON", result["flags"])

    def test_rejects_extra_keys(self):
        _, result = parse_and_validate('{"direct":[],"inferences":[],"contested":[],"limits":[],"extra":true}', self.sources)
        self.assertIn("SCHEMA_SHAPE_DEVIATION", result["flags"])

    def test_flags_uncited_claim(self):
        _, result = parse_and_validate('{"direct":[{"claim":"A claim.","source_ids":[]}],"inferences":[],"contested":[],"limits":[]}', self.sources)
        self.assertIn("UNCITED_CLAIM", result["flags"])


if __name__ == "__main__":
    unittest.main()