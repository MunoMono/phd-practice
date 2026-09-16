import unittest

from pydantic import ValidationError

from app.api.routes.viz import EmbeddingReadinessReviewRequest


def valid_review_payload(**overrides):
    payload = {
        "status": "approved",
        "corpus_release": "ddr-corpus-2026-09-08",
        "source_scope": "Approved text-bearing chunks with stable document and chunk IDs.",
        "exclusions": "Restricted, image-only, and extraction-failed sources are excluded.",
        "embedding_model": "example-embedding-model",
        "model_revision_or_checksum": "sha256:example",
        "vector_dimensions": 768,
        "runtime_and_license": "Local runtime; licence reviewed.",
        "normalisation_chunking_version": "normalisation-v1/chunking-v1",
        "capacity_retention_plan": "Capacity confirmed; versioned retention and rollback recorded.",
        "fts_separation_plan": "FTS remains the evidence-selection method; vectors only support visual exploration.",
        "analytical_question": "Which candidate comparisons merit source-based review?",
        "reviewed_by": "Researcher",
    }
    payload.update(overrides)
    return payload


class AtlasReadinessValidationTests(unittest.TestCase):
    def test_approved_review_requires_named_researcher(self):
        with self.assertRaisesRegex(ValidationError, "reviewing researcher"):
            EmbeddingReadinessReviewRequest(**valid_review_payload(reviewed_by=" "))

    def test_readiness_fields_must_be_substantive(self):
        with self.assertRaisesRegex(ValidationError, "must not be blank"):
            EmbeddingReadinessReviewRequest(**valid_review_payload(exclusions=""))

    def test_complete_approved_review_is_accepted(self):
        review = EmbeddingReadinessReviewRequest(**valid_review_payload())

        self.assertEqual(review.status, "approved")
        self.assertEqual(review.vector_dimensions, 768)