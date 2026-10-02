import csv
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "docs" / "ml_triage_dev_v2" / "clean_ml_triage_dev_UAT_50_v2.csv"
PRODUCTION_ROOTS = (REPO_ROOT / "backend" / "app", REPO_ROOT / "frontend" / "src")
PRODUCTION_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md", ".txt"}
FORMAL_EXPERIMENT_REGISTRY = REPO_ROOT / "backend" / "app" / "services" / "turin_question_register.py"


def normalise(value: str) -> str:
    return " ".join(value.split()).casefold()


class MLTriageAntiOverfittingTests(unittest.TestCase):
    def test_production_does_not_embed_evaluation_data(self):
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as source:
            cases = list(csv.DictReader(source))
        questions = [(case["uat_id"], normalise(case["question"])) for case in cases]
        answer_fragments = []
        for case in cases:
            fragments = re.split(r"(?<=[.!?])\s+|;\s*", case.get("actual_answer") or "")
            answer_fragments.extend(
                (case["uat_id"], normalise(fragment))
                for fragment in fragments
                if len(normalise(fragment)) >= 180
            )

        violations = []
        for root in PRODUCTION_ROOTS:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in PRODUCTION_SUFFIXES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                normalised_text = normalise(text)
                if re.search(r"MLT-(?:DOC|AUTH|HYB|LIM)-\d+", text):
                    violations.append(f"{path.relative_to(REPO_ROOT)} embeds a UAT identifier")
                for forbidden_name in ("graham_newman_subjective_comments", "uat_pass_fail"):
                    if forbidden_name in text:
                        violations.append(f"{path.relative_to(REPO_ROOT)} uses {forbidden_name}")
                if path != FORMAL_EXPERIMENT_REGISTRY:
                    violations.extend(
                        f"{path.relative_to(REPO_ROOT)} embeds the full question for {case_id}"
                        for case_id, question in questions
                        if question and question in normalised_text
                    )
                violations.extend(
                    f"{path.relative_to(REPO_ROOT)} copies answer prose from {case_id}"
                    for case_id, fragment in answer_fragments
                    if fragment in normalised_text
                )

        self.assertEqual(violations, [], "\n".join(violations))


if __name__ == "__main__":
    unittest.main()