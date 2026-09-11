import unittest

from pydantic import ValidationError

from types import SimpleNamespace

from app.api.routes.cross_read import CrossReadMappingUpdateRequest, CrossReadMissingnessNominationRequest, CrossReadPassageCreateRequest, build_mapping_payload, build_missingness_nomination_values


class CrossReadPassageValidationTests(unittest.TestCase):
    def test_empty_passage_text_is_rejected(self):
        with self.assertRaises(ValidationError):
            CrossReadPassageCreateRequest(passage_text="")

    def test_whitespace_only_passage_text_is_rejected(self):
        with self.assertRaises(ValidationError):
            CrossReadPassageCreateRequest(passage_text=" \n\t ")

    def test_nonblank_passage_text_is_accepted_without_rewriting_it(self):
        passage = CrossReadPassageCreateRequest(passage_text="  Researcher draft text  ")

        self.assertEqual(passage.passage_text, "  Researcher draft text  ")

    def test_oral_history_requires_speaker_and_durable_source_reference(self):
        with self.assertRaisesRegex(ValidationError, "speaker or source"):
            CrossReadPassageCreateRequest(
                passage_text="Remembered account.",
                source_type="oral_history",
                source_reference="Interview transcript: 01:12:03",
            )
        with self.assertRaisesRegex(ValidationError, "durable source reference"):
            CrossReadPassageCreateRequest(
                passage_text="Remembered account.",
                source_type="oral_history",
                speaker_or_source="Named speaker",
            )

    def test_attributable_interview_passage_accepts_governed_provenance(self):
        passage = CrossReadPassageCreateRequest(
            passage_text="Recorded interview passage.",
            source_type="interview",
            speaker_or_source="Named speaker",
            source_reference="Oral history transcript, page 3",
            source_date="2013-05-01",
            access_status="restricted",
            ingestion_method="imported",
        )

        self.assertEqual(passage.access_status, "restricted")
        self.assertEqual(passage.ingestion_method, "imported")

    def test_unreviewed_is_a_valid_candidate_mapping_state(self):
        mapping = CrossReadMappingUpdateRequest(relation_type="unreviewed")

        self.assertEqual(mapping.relation_type, "unreviewed")

    def test_researcher_relation_annotations_use_the_connected_uat_vocabulary(self):
        for relation_type in ("convergence", "contradiction", "complication", "contextual_relation", "no_documentary_trace"):
            mapping = CrossReadMappingUpdateRequest(relation_type=relation_type)
            self.assertEqual(mapping.relation_type, relation_type)

    def test_zero_result_probe_stays_unreviewed_until_researcher_annotation(self):
        mapping = build_mapping_payload(None, "unreviewed", None, "query-test")

        self.assertEqual(mapping["relation_type"], "unreviewed")
        self.assertEqual(mapping["confidence_or_status"], "candidate_no_result")

    def test_missingness_nomination_requires_explicit_confirmation_and_note(self):
        with self.assertRaises(ValidationError):
            CrossReadMissingnessNominationRequest(confirmed=True, reviewer_note=" ")

        nomination = CrossReadMissingnessNominationRequest(confirmed=True, reviewer_note="Reviewed retrieval scope.")

        self.assertTrue(nomination.confirmed)

    def test_no_trace_nomination_preserves_mapping_provenance_and_scope(self):
        mapping = SimpleNamespace(
            mapping_id="map-test",
            passage_id="pass-test",
            query_id="query-test",
            document_id="doc-test",
            chunk_id="chunk-test",
        )

        values = build_missingness_nomination_values(mapping, "Reviewed the current retrieval scope.")

        self.assertEqual(values["source_document_ids_json"], ["doc-test"])
        self.assertEqual(values["source_chunk_ids_json"], ["chunk-test"])
        self.assertEqual(values["cross_read_mapping_id"], "map-test")
        self.assertIn("not historical absence", values["evidence"])
        self.assertIn("search additional digitised sources", values["follow_up_action"])