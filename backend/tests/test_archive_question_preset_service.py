import unittest

from app.services.archive_question_preset_service import matching_archive_question_preset


class ArchiveQuestionPresetTests(unittest.TestCase):
    def test_teaching_question_uses_controlled_teaching_preset(self):
        preset = matching_archive_question_preset(
            "How did DDR teaching connect scientific method and modelling to design practice?"
        )

        self.assertIsNotNone(preset)
        self.assertEqual(preset.preset_id, "ddr_teaching_learning_practice")
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.archive_question_preset_service import matching_archive_question_preset


class ArchiveQuestionPresetTests(unittest.TestCase):
    def test_teaching_and_learning_question_uses_controlled_record_scope(self):
        preset = matching_archive_question_preset(
            "What are the key takeaways from the teaching and learning documents in the archive?"
        )
        self.assertIsNotNone(preset)
        self.assertEqual(preset.preset_id, "ddr_teaching_learning_practice")
        self.assertEqual(preset.record_pid, "989478384551")

    def test_unrelated_question_does_not_use_teaching_preset(self):
        self.assertIsNone(matching_archive_question_preset("Why did the Department of Design Research close?"))

    def test_hospital_bedstead_question_uses_its_controlled_source_family(self):
        preset = matching_archive_question_preset(
            "What does the general purpose hospital bedstead final report show about ergonomics and testing?"
        )
        self.assertIsNotNone(preset)
        self.assertEqual(preset.preset_id, "general_purpose_hospital_bedstead")
        self.assertEqual(preset.record_pid, "232731654562")

    def test_langdon_teaching_question_uses_teaching_ephemera(self):
        preset = matching_archive_question_preset(
            "What do Richard Langdon's surviving teaching records show about his curriculum?"
        )
        self.assertIsNotNone(preset)
        self.assertEqual(preset.preset_id, "richard_langdon_teaching_ephemera")
        self.assertEqual(preset.record_pid, "475236004017")
