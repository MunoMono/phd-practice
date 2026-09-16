import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from build_turin_archive_successor_corpus import Q02_ASSET_PIDS, successor_corpus_version


class SuccessorCorpusTests(unittest.TestCase):
    def test_corpus_version_is_deterministic(self):
        rows = [
            {"asset_pid": "2", "asset_id": "b", "record_pid": "r", "attached_media_pid": "m"},
            {"asset_pid": "1", "asset_id": "a", "record_pid": "r", "attached_media_pid": "m"},
        ]
        self.assertEqual(successor_corpus_version(rows), successor_corpus_version(list(reversed(rows))))

    def test_q02_gate_contains_all_acceptance_assets(self):
        self.assertEqual(set(Q02_ASSET_PIDS), {"062054716175", "852120727979", "723660822664"})