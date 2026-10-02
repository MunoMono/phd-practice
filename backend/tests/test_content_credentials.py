import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_credentials import build_query_run_manifest, build_query_run_svg, signed_asset_record


class ContentCredentialsTests(unittest.TestCase):
    def setUp(self):
        self.run = SimpleNamespace(
            query_id="query-c2pa",
            prompt="What does the evidence establish?",
            model="qwen3",
            response="A source-grounded response.",
            caveats="Interpret with the selected evidence.",
            failure_reason=None,
            created_at=None,
            chunks=[SimpleNamespace(
                chunk_id="chunk-1",
                document_id="document-1",
                source_metadata_json={"title": "Archive item"},
            )],
        )

    def test_manifest_records_ai_origin_and_retained_ingredients(self):
        manifest = build_query_run_manifest(self.run)

        self.assertEqual(manifest["format"], "image/svg+xml")
        self.assertEqual(manifest["ingredients"][0]["relationship"], "inputTo")
        action = manifest["assertions"][0]["data"]["actions"][0]
        self.assertEqual(action["action"], "c2pa.created")
        self.assertIn("trainedAlgorithmicMedia", action["digitalSourceType"])

    def test_svg_contains_the_identifying_research_context(self):
        svg = build_query_run_svg(self.run)

        self.assertIn("query-c2pa", svg)
        self.assertIn("Retained source passages: 1", svg)

    def test_signed_asset_record_retains_hashes_and_validator_result(self):
        record = signed_asset_record(b"signed asset", {
            "validation_state": "Valid",
            "validation_status": [{"code": "signingCredential.untrusted"}],
            "active_manifest": {"signature_info": {"issuer": "Innovation Design research signer"}},
        })

        self.assertEqual(record["validation_state"], "Valid")
        self.assertEqual(record["signer_subject"], "Innovation Design research signer")
        self.assertEqual(len(record["asset_sha256"]), 64)
        self.assertEqual(len(record["manifest_sha256"]), 64)