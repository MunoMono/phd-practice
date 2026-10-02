from __future__ import annotations

import csv
from pathlib import Path


UAT_CSV_PATH = Path(__file__).resolve().parents[2] / "docs" / "ml_triage_dev" / "ml_triage_dev_UAT_50.csv"
REQUIRED_COLUMNS = {
    "uat_id",
    "research_family",
    "question",
    "expected_retrieval_mode",
    "expected_authority_types",
    "expected_source_presets",
    "required_claim_moves",
    "expected_evidential_status",
    "prohibited_overclaim",
    "expected_limit",
    "pass_criteria",
    "notes",
}


def load_ml_triage_uat_cases() -> list[dict[str, str]]:
    with UAT_CSV_PATH.open(newline="", encoding="utf-8-sig") as fixture_file:
        reader = csv.DictReader(fixture_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"ML triage UAT fixture is missing required columns: {sorted(missing)}")
        cases = list(reader)

    identifiers = [case["uat_id"] for case in cases]
    if len(cases) != 50:
        raise ValueError(f"ML triage UAT fixture must contain exactly 50 cases, found {len(cases)}")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("ML triage UAT fixture contains duplicate UAT IDs")
    return cases