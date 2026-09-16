import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.turin_retrieval_v316_project_identity_surface import TurinRetrievalV316ProjectIdentitySurface as V311


AUTHORITIES = [
    {"authority_type": "ref_fonds", "authority_id": "DEU", "code": "DEU", "label": "Design Education Unit"},
    {"authority_type": "ref_fonds", "authority_id": "DDR", "code": "DDR", "label": "Department of Design Research"},
    {"authority_type": "agent_employment", "authority_id": "ken", "label": "Ken Baynes"},
    {"authority_type": "agent_employment", "authority_id": "phil", "label": "Phil Roberts"},
    {"authority_type": "agent_employment", "authority_id": "ryott", "label": "Henrietta Ryott"},
    {"authority_type": "ddr_projects", "authority_id": "171", "label": "Designer-computer interaction"},
]


class V311TypedAnchorTests(unittest.TestCase):
    def setUp(self):
        self.selector = V311(AUTHORITIES)

    @staticmethod
    def row(asset, text, title=None, metadata=None, score=5):
        return {
            "chunk_id": f"{asset}-chunk",
            "document_id": asset,
            "canonical_asset_id": asset,
            "asset_pid": asset,
            "title": title or asset,
            "authority_data": metadata or {},
            "chunk_index": 0,
            "chunk_text": text,
            "passage_score": score,
            "passage_adequacy": "PASSAGE_STRONG",
            "facet_coverage": ["EVENT", "PERSON_A"],
            "source_signals": {},
            "authority_graph_signals": {},
            "lane_nominations": [],
        }

    def test_authority_resolution_is_type_safe(self):
        anchors = self.selector.analyze("Did Ken Baynes work with Phil Roberts in the Design Education Unit, Department of Design Research, on Job 171 between 1973-77?")
        types = {(item["raw_phrase"], item["resolved_anchor_type"]) for item in anchors}
        self.assertIn(("Design Education Unit", "INSTITUTION_OR_UNIT"), types)
        self.assertIn(("Department of Design Research", "INSTITUTION_OR_UNIT"), types)
        self.assertIn(("Ken Baynes", "PERSON"), types)
        self.assertIn(("Phil Roberts", "PERSON"), types)
        self.assertIn(("Job 171", "PROJECT"), types)
        self.assertIn(("1973-1977", "TEMPORAL"), types)
        self.assertNotIn(("Design Education Unit", "PERSON"), types)

    def test_exact_archival_asset_rejects_other_source(self):
        result = self.selector.build([self.row("778", "Alfonso Gomez", score=5), self.row("999", "Alfonso Gomez", score=9)], "Find documentary material naming Alfonso Gomez in archival asset 778.", ["PERSON_A"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "778")

    def test_numeric_authority_identifiers_are_not_phrase_anchors(self):
        anchors = self.selector.analyze("What can establish Henrietta Ryott's role in the DDR between 1973 and 1977?")
        phrases = {item["raw_phrase"] for item in anchors}
        self.assertNotIn("197", phrases)
        self.assertNotIn("1", phrases)
        self.assertIn("1973-1977", phrases)

    def test_persisted_project_title_is_a_typed_exact_anchor(self):
        authorities = AUTHORITIES + [{"authority_type": "ddr_projects", "authority_id": "dge", "label": "Design in General Education"}]
        result = V311(authorities).build([self.row("dge", "Programme record", "Design in General Education report"), self.row("other", "Programme record", "Other report", score=9)], "Can the records establish how Design in General Education was received?", ["CONCEPT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "dge")

    def test_project_id_and_title_are_alternative_identities(self):
        authorities = AUTHORITIES + [{"authority_type": "ddr_projects", "authority_id": "171", "label": "Designer-computer interaction in the early stages of design"}]
        result = V311(authorities).build([self.row("171", "Job 171 research record", "Job 171 report"), self.row("other", "Unrelated research record", "Other report", score=9)], "What connects Job 171, Designer-computer interaction in the early stages of design?", ["CONCEPT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "171")
        self.assertEqual(result["evidence_bundles"][0]["source"]["project_anchor"]["normalized_project_id"], "171")

    def test_exact_archive_metadata_title_fallback(self):
        result = self.selector.build([self.row("dge", "Project activity", "Archive item", {"project_title": "Design in General Education"}), self.row("other", "Project activity", "Other title", score=9)], "What records concern Design in General Education?", ["CONCEPT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "dge")

    def test_materialised_controlled_archive_title_is_project_identity(self):
        identities = [{"project_identity_id": "dge-box", "project_title": "Design in General Education", "project_authority_id": None, "source_path": "documents.authority_data.box_title"}]
        result = V311(AUTHORITIES, identities).build([self.row("dge", "Project activity", "Archive item", {"box_title": "Design in General Education"}), self.row("other", "Project activity", "Other title", score=9)], "What records concern Design in General Education?", ["CONCEPT"])
        source = result["evidence_bundles"][0]["source"]
        self.assertEqual(source["asset_pid"], "dge")
        self.assertIn("EXACT_MATERIALISED_PROJECT_TITLE", source["project_anchor"]["resolution_sources"])

    def test_person_pair_unit_allows_direct_separate_evidence(self):
        rows = [
            self.row("ken", "Ken Baynes worked in the Design Education Unit."),
            self.row("phil", "Phil Roberts taught for the Design Education Unit."),
        ]
        result = self.selector.build(rows, "What evidence connects Ken Baynes and Phil Roberts within the work of the Design Education Unit?", ["PERSON_A", "PERSON_B"])
        self.assertEqual(len(result["evidence_bundles"]), 2)
        self.assertTrue(all(bundle["source"]["required_anchor_satisfied"] for bundle in result["evidence_bundles"]))
        self.assertEqual(result["evidence_bundles"][0]["source"]["person_pair_state"], "NONE")

    def test_contemporary_event_source_outranks_retrospective(self):
        rows = [
            self.row("interview", "The DDR closure decision was explained later.", "Interview with a former staff member", score=9),
            self.row("senate", "The DDR closure decision was resolved by Senate.", "Senate memorandum", score=5),
        ]
        result = self.selector.build(rows, "Why was the DDR closure decision made?", ["EVENT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "senate")
        self.assertEqual(result["evidence_bundles"][0]["source"]["source_class"], "CONTEMPORARY_INSTITUTIONAL")

    def test_contemporary_event_action_outranks_retrospective_extra_term(self):
        rows = [
            self.row("interview", "The DDR closure decision was explained later.", "Interview with a former staff member", score=9),
            self.row("memo", "The DDR will close in August.", "Department memorandum", score=5),
        ]
        result = self.selector.build(rows, "Why was the DDR closure decision made?", ["EVENT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"], "memo")
        self.assertTrue(result["evidence_bundles"][0]["source"]["event_action_or_decision_satisfied"])

    def test_retrospective_event_source_remains_fallback(self):
        result = self.selector.build([self.row("interview", "The DDR closure decision was explained later.", "Interview with a former staff member")], "Why was the DDR closure decision made?", ["EVENT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["source_class"], "RETROSPECTIVE_INTERVIEW")

    def test_temporal_scope_metadata_never_becomes_claim(self):
        row = self.row("ryott", "Henrietta Ryott prepared typing material.", "DDR staffing file", {"year": "1975"})
        result = self.selector.build([row], "What can establish Henrietta Ryott's role in the DDR between 1973 and 1977?", ["PERSON_A"])
        profile = result["evidence_bundles"][0]["source"]
        temporal = next(item for item in profile["anchor_match_details"] if item["resolved_anchor_type"] == "TEMPORAL")
        self.assertEqual(temporal["match_scope"], "ARCHIVAL_TEMPORAL_CONTEXT")
        self.assertFalse(profile["documentary_anchor"]["metadata_is_documentary_evidence"])


if __name__ == "__main__":
    unittest.main()
