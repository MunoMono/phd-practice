import re
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PROMPT_REGISTER = BACKEND_ROOT.parent / "docs" / "experiment" / "prompt-register.md"
QUESTION_ROW = re.compile(r"^\| ([A-Z]{2}\d) \| ([a-z_]+) \| (.+) \| pending researcher approval \|$")


class TurinQuestionRegisterTests(unittest.TestCase):
    def test_markdown_register_matches_runtime_question_register_exactly(self):
        rows = {}
        for line in PROMPT_REGISTER.read_text(encoding="utf-8").splitlines():
            match = QUESTION_ROW.match(line)
            if match:
                question_id, research_case, question = match.groups()
                rows[question_id] = (research_case, question)

        self.assertEqual(len(rows), 12)
        self.assertEqual(rows, TURIN_QUESTION_REGISTER)


if __name__ == "__main__":
    unittest.main()