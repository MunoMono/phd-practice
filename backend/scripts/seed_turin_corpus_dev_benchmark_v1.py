#!/usr/bin/env python3
"""Persist the frozen non-formal Turin corpus-development benchmark."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal


def main() -> None:
    payload = json.loads((BACKEND_ROOT / "fixtures" / "turin-corpus-dev-benchmark-v1.json").read_text())
    db = LocalSessionLocal()
    try:
        existing = db.execute(text("SELECT benchmark_json FROM turin_corpus_dev_benchmarks WHERE benchmark_version=:version"), {"version": payload["benchmark_version"]}).scalar_one_or_none()
        if existing is not None:
            if dict(existing) != payload:
                raise RuntimeError("Existing benchmark version differs from the frozen fixture.")
            print(payload["benchmark_version"])
            return
        db.execute(text("INSERT INTO turin_corpus_dev_benchmarks (benchmark_version, benchmark_json) VALUES (:version, CAST(:payload AS jsonb))"), {"version": payload["benchmark_version"], "payload": json.dumps(payload)})
        db.commit()
        print(payload["benchmark_version"])
    finally:
        db.close()


if __name__ == "__main__":
    main()