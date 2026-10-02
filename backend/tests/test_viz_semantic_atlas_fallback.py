import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from app.api.routes.viz import AlignedUmapRunRequest, ProjectionFidelityRequest, SemanticNeighbourhoodRequest, _build_evidence_surface_scope, _can_revise_visual_annotation, _get_completed_semantic_atlas_projection, _semantic_point_payload


class SemanticAtlasFallbackTests(unittest.TestCase):
    def test_semantic_point_exposes_explicit_provenance_and_representation_states(self):
        point = _semantic_point_payload(SimpleNamespace(
            chunk_id="chunk-1", document_id="document-1", pid="asset-1", title="A source",
            year=1978, file_type="pdf", chunk_type="body", citation=None, key_concepts=[],
            chunk_text="Bounded source excerpt", source_page=4, source_section="Methods",
            similarity=0.92, x=1.0, y=2.0,
            authority_data={"archive_record_pid": "record-1", "record_public_uri": "https://archive.example/record-1"},
            archive_record_id=None,
        ))

        self.assertEqual(point["evidence_surface"]["representation_state"], "represented_in_completed_embedding_set")
        self.assertEqual(point["missingness"]["status"], "not_recorded")
        self.assertEqual(point["archive_authority_context"]["availability"], "available")
        self.assertEqual(point["archive_authority_context"]["classification"], "archive linkage metadata, not documentary evidence")
        self.assertEqual(point["database_authority_context"], [])
        self.assertEqual(point["annotation_summary"]["status"], "not_available")

    def test_neighbourhood_display_k_uses_frozen_bounds_and_step(self):
        self.assertEqual(SemanticNeighbourhoodRequest(focal_chunk_id="chunk-1").size, 10)
        self.assertEqual(SemanticNeighbourhoodRequest(focal_chunk_id="chunk-1", size=50).size, 50)

        with self.assertRaises(ValidationError):
            SemanticNeighbourhoodRequest(focal_chunk_id="chunk-1", size=7)

    def test_projection_fidelity_requires_bounded_focal_set_and_diagnostic_size(self):
        request = ProjectionFidelityRequest(focal_chunk_ids=["chunk-1"])
        self.assertEqual(request.neighbourhood_size, 10)

        with self.assertRaises(ValidationError):
            ProjectionFidelityRequest(focal_chunk_ids=[], neighbourhood_size=10)

        with self.assertRaises(ValidationError):
            ProjectionFidelityRequest(focal_chunk_ids=["chunk-1"], neighbourhood_size=1)

    def test_aligned_runs_require_explicit_consecutive_relations_with_slice_membership(self):
        request = AlignedUmapRunRequest(
            baseline_projection_id="projection-1", baseline_embedding_set_id="embedding-1", corpus_snapshot_id="corpus-1",
            dimensions=2, parameters={"alignment_regularisation": 0.1}, method_version="aligned-umap-v1",
            slices=[
                {"slice_id": "slice-a", "slice_order": 0, "period_provenance": {"source": "DDR period authority"}, "membership_query": {"year_to": 1969}, "membership_point_ids": ["chunk-1"]},
                {"slice_id": "slice-b", "slice_order": 1, "period_provenance": {"source": "DDR period authority"}, "membership_query": {"year_from": 1970}, "membership_point_ids": ["chunk-2"]},
            ],
            relations=[{"from_slice_id": "slice-a", "to_slice_id": "slice-b", "source_point_id": "chunk-1", "target_point_id": "chunk-2", "relation_type": "stable_pid", "authority_provenance": {"authority": "PID mapping"}}],
        )
        self.assertEqual(request.slices[0].membership_point_ids, ["chunk-1"])

        with self.assertRaises(ValidationError):
            AlignedUmapRunRequest(
                baseline_projection_id="projection-1", baseline_embedding_set_id="embedding-1", corpus_snapshot_id="corpus-1",
                dimensions=2, parameters={}, method_version="aligned-umap-v1",
                slices=request.slices,
                relations=[{"from_slice_id": "slice-a", "to_slice_id": "slice-b", "source_point_id": "missing-chunk", "target_point_id": "chunk-2", "relation_type": "stable_pid", "authority_provenance": {"authority": "PID mapping"}}],
            )

    def test_annotation_revision_allows_owner_or_reviewer_and_preserves_legacy_records(self):
        owner_bound = SimpleNamespace(owner_id="auth0|owner")
        self.assertTrue(_can_revise_visual_annotation(owner_bound, {"user_id": "auth0|owner", "permissions": []}))
        self.assertTrue(_can_revise_visual_annotation(owner_bound, {"user_id": "auth0|reviewer", "permissions": ["annotations:review"]}))
        self.assertFalse(_can_revise_visual_annotation(owner_bound, {"user_id": "auth0|other", "permissions": []}))
        self.assertFalse(_can_revise_visual_annotation(owner_bound, None))
        self.assertTrue(_can_revise_visual_annotation(SimpleNamespace(owner_id=None), None))

    def test_missing_semantic_atlas_projection_rolls_back_before_fallback(self):
        database = Mock()
        database.execute.side_effect = RuntimeError("semantic atlas schema is unavailable")

        self.assertIsNone(_get_completed_semantic_atlas_projection(database))

        database.rollback.assert_called_once_with()

    def test_evidence_scope_exposes_active_fts_corpus_when_embeddings_are_absent(self):
        scope = _build_evidence_surface_scope(
            "chunks",
            0,
            0,
            0,
            {
                "total_documents": 625,
                "documents_with_extracted_text": 53,
                "documents_with_embeddings": 0,
                "embedded_chunks": 0,
                "documents_represented_by_chunks": 0,
                "active_corpus_version": "corpus_turin_successor_d6c6858b23d0",
                "active_fts_chunks": 15114,
                "active_fts_documents": 123,
            },
        )

        self.assertEqual(scope["active_corpus_version"], "corpus_turin_successor_d6c6858b23d0")
        self.assertEqual(scope["active_fts_chunks"], 15114)
        self.assertEqual(scope["active_fts_documents"], 123)
        self.assertEqual(scope["eligible_count"], 0)
        self.assertEqual(scope["represented_count"], 0)
        self.assertEqual(scope["rendered_count"], 0)
        self.assertEqual(scope["visible_count"], 0)
        self.assertIn("no rendered subset", scope["rendering_policy"])