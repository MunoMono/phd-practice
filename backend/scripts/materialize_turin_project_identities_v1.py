"""Append-only materialisation of exact controlled archive project titles."""
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.database import LocalSessionLocal

SNAPSHOT_VERSION = "turin-project-identity-v1"
SOURCE_PATH = "documents.authority_data.box_title"


def normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def main() -> None:
    db = LocalSessionLocal()
    try:
        rows = db.execute(text("""
            SELECT archive_record_pid, asset_pid, authority_data->>'box_title' AS project_title
            FROM documents
            WHERE authority_data->>'box_title' IS NOT NULL
              AND btrim(authority_data->>'box_title') <> ''
            ORDER BY archive_record_pid, asset_pid
        """)).mappings().all()
        identities = {}
        for row in rows:
            title = str(row["project_title"])
            normalized = normalise(title)
            identity_key = f"archive-box:{row['archive_record_pid']}:{normalized}"
            identities.setdefault(identity_key, {"project_identity_id": hashlib.sha256(identity_key.encode()).hexdigest(), "project_authority_id": None, "project_job_id": None, "project_title": title, "normalized_project_title": normalized, "source_of_truth": "ARCHIVE_METADATA", "source_path": SOURCE_PATH, "archive_record_pid": row["archive_record_pid"], "attached_media_pid": None, "asset_pid": None, "snapshot_version": SNAPSHOT_VERSION})
        for identity in identities.values():
            db.execute(text("""
                INSERT INTO turin_project_identities (
                    project_identity_id, project_authority_id, project_job_id, project_title,
                    normalized_project_title, source_of_truth, source_path, archive_record_pid,
                    attached_media_pid, asset_pid, snapshot_version
                ) VALUES (
                    :project_identity_id, :project_authority_id, :project_job_id, :project_title,
                    :normalized_project_title, :source_of_truth, :source_path, :archive_record_pid,
                    :attached_media_pid, :asset_pid, :snapshot_version
                ) ON CONFLICT (project_identity_id) DO NOTHING
            """), identity)
        db.commit()
        print(json.dumps({"snapshot_version": SNAPSHOT_VERSION, "materialised": len(identities)}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
