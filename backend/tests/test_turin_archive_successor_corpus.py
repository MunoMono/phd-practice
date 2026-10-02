import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from build_turin_archive_successor_corpus import Q02_ASSET_PIDS, TARGETED_ASSET_PIDS, successor_corpus_version


class SuccessorCorpusTests(unittest.TestCase):
    def test_corpus_version_is_deterministic(self):
        rows = [
            {"asset_pid": "2", "asset_id": "b", "record_pid": "r", "attached_media_pid": "m"},
            {"asset_pid": "1", "asset_id": "a", "record_pid": "r", "attached_media_pid": "m"},
        ]
        self.assertEqual(successor_corpus_version(rows), successor_corpus_version(list(reversed(rows))))

    def test_corpus_version_changes_with_parent(self):
        rows = [{"asset_pid": "1", "asset_id": "a", "record_pid": "r", "attached_media_pid": "m"}]
        self.assertNotEqual(
            successor_corpus_version(rows, "corpus_parent_a"),
            successor_corpus_version(rows, "corpus_parent_b"),
        )

    def test_corpus_version_changes_with_clone_identity_strategy(self):
        rows = [{"asset_pid": "1", "asset_id": "a", "record_pid": "r", "attached_media_pid": "m"}]
        self.assertNotEqual(
            successor_corpus_version(rows, "corpus_parent", "successor_doc_"),
            successor_corpus_version(rows, "corpus_parent", "archive_successor_doc_"),
        )

    def test_q02_gate_contains_all_acceptance_assets(self):
        self.assertEqual(set(Q02_ASSET_PIDS), {"062054716175", "852120727979", "723660822664"})

    def test_targeted_release_contains_only_requested_materialisation_assets(self):
        self.assertEqual(set(TARGETED_ASSET_PIDS), {
            "098776258047", "482546702591", "492782087857", "665092576421", "723660822664",
        })