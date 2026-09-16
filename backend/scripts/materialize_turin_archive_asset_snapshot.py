"""Load a persisted DDR Archive metadata export into the archive-first nomination surface."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import text

from app.core.database import LocalSessionLocal
from app.services.corpus_inventory_service import CorpusInventoryService


SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def _asset_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_pid": row.get("record_pid") or row.get("archive_record_pid"),
        "attached_media_pid": row.get("attached_media_pid") or row.get("pid"),
        "asset_pid": row.get("asset_pid"),
        "asset_id": row.get("asset_id") or row.get("asset_id_or_asset_pid"),
        "label": row.get("label") or row.get("title") or row.get("caption"),
        "display_date": row.get("display_date") or row.get("date_text"),
        "normalized_date": row.get("normalized_date"),
        "use_for_ml": row.get("use_for_ml"),
        "ml_pages": row.get("ml_pages"),
        "source_type": row.get("source_type") or row.get("document_type"),
        "record_title": row.get("record_title"),
        "attached_media_title": row.get("attached_media_title") or row.get("title"),
        "keywords": _list(row.get("keywords")),
        "people": _list(row.get("people") or row.get("creators") or row.get("creator")),
        "projects": _list(row.get("projects") or row.get("project_title")),
        "box_title": row.get("box_title"),
        "collection_title": row.get("collection_title") or row.get("parent_collection"),
        "exact_project_title": row.get("exact_project_title") or row.get("project_title"),
        "exact_job_id": row.get("exact_job_id") or row.get("job_id"),
        "controlled_aliases": _list(row.get("controlled_aliases")),
        "preset_groups": _list(row.get("preset_groups") or row.get("presets")),
        "source_snapshot_provenance": row.get("source_snapshot_provenance") or {},
    }


def load_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        payload = payload.get("records") or payload.get("items") or []
    rows = list(payload)
    if rows and isinstance(rows[0], Mapping) and "attached_media" in rows[0]:
        rows = CorpusInventoryService().flatten_records_pdf_sources(rows, include_non_ml=True)
    return [_asset_payload(row) for row in rows if row.get("asset_pid")]


def materialize(input_path: Path, snapshot_version: str, replace: bool) -> int:
    rows = load_rows(json.loads(input_path.read_text(encoding="utf-8")))
    db = LocalSessionLocal()
    try:
        if replace:
            db.execute(text("DELETE FROM turin_archive_asset_snapshots WHERE source_snapshot_version = :snapshot_version"), {"snapshot_version": snapshot_version})
        for row in rows:
            db.execute(text("""
                INSERT INTO turin_archive_asset_snapshots (
                    source_snapshot_version, record_pid, attached_media_pid, asset_pid, asset_id,
                    label, display_date, normalized_date, use_for_ml, ml_pages, source_type,
                    record_title, attached_media_title, keywords, people, projects, box_title,
                    collection_title, exact_project_title, exact_job_id, controlled_aliases, preset_groups, source_snapshot_provenance
                ) VALUES (
                    :snapshot_version, :record_pid, :attached_media_pid, :asset_pid, :asset_id,
                    :label, :display_date, :normalized_date, :use_for_ml, :ml_pages, :source_type,
                    :record_title, :attached_media_title, CAST(:keywords AS jsonb), CAST(:people AS jsonb),
                    CAST(:projects AS jsonb), :box_title, :collection_title, :exact_project_title,
                    :exact_job_id, CAST(:controlled_aliases AS jsonb), CAST(:preset_groups AS jsonb), CAST(:source_snapshot_provenance AS jsonb)
                ) ON CONFLICT (source_snapshot_version, asset_pid, asset_id) DO UPDATE SET
                    record_pid = EXCLUDED.record_pid, attached_media_pid = EXCLUDED.attached_media_pid,
                    label = EXCLUDED.label, display_date = EXCLUDED.display_date,
                    normalized_date = EXCLUDED.normalized_date, use_for_ml = EXCLUDED.use_for_ml,
                    ml_pages = EXCLUDED.ml_pages, source_type = EXCLUDED.source_type,
                    record_title = EXCLUDED.record_title, attached_media_title = EXCLUDED.attached_media_title,
                    keywords = EXCLUDED.keywords, people = EXCLUDED.people, projects = EXCLUDED.projects,
                    box_title = EXCLUDED.box_title, collection_title = EXCLUDED.collection_title,
                    exact_project_title = EXCLUDED.exact_project_title, exact_job_id = EXCLUDED.exact_job_id,
                        controlled_aliases = EXCLUDED.controlled_aliases, preset_groups = EXCLUDED.preset_groups,
                        source_snapshot_provenance = EXCLUDED.source_snapshot_provenance
                    """), {"snapshot_version": snapshot_version, **row, **{key: json.dumps(row[key]) for key in ("keywords", "people", "projects", "controlled_aliases", "preset_groups", "source_snapshot_provenance")}})
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def export_persisted_snapshot(output_path: Path) -> int:
    """Fetch once through the established client; interrogation never calls this path."""
    rows = CorpusInventoryService().flatten_complete_archive_pdf_sources(include_non_ml=True)
    provenance = {
        "archive_endpoint": "https://api.ddrarchive.org/graphql",
        "graphql_operation": "records_v1(status) identity enumeration -> record_v1(id) detail traversal",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_version": SNAPSHOT_VERSION,
    }
    for row in rows:
        row["source_snapshot_provenance"] = provenance
    output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, nargs="?", help="Persisted records_v1 or flattened archive-asset JSON export")
    parser.add_argument("--export", type=Path, help="Write a new persisted flattened snapshot using the established Archive client")
    parser.add_argument("--snapshot-version", default=SNAPSHOT_VERSION)
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    if arguments.export:
        print(json.dumps({"assets_exported": export_persisted_snapshot(arguments.export), "output": str(arguments.export)}))
    elif arguments.input:
        print(json.dumps({"assets_materialized": materialize(arguments.input, arguments.snapshot_version, arguments.replace), "snapshot_version": arguments.snapshot_version}))
    else:
        parser.error("provide INPUT to materialize or --export OUTPUT to create a persisted snapshot")