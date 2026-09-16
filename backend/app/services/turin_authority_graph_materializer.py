"""Materialise only exact, auditable authority-to-source relations."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import text


SNAPSHOT_VERSION = "turin-archive-authority-graph-v1"
METADATA_SNAPSHOT_VERSION = "turin-archive-metadata-v1"
MATERIALISER_VERSION = "turin-authority-graph-materializer-v1"


def _normalise(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def _values(metadata: dict[str, Any]) -> list[tuple[str, str, str]]:
    values: list[tuple[str, str, str]] = []
    for field in ("creator_agent_label", "creators", "keywords", "subjects"):
        value = metadata.get(field)
        for item in value if isinstance(value, list) else [value]:
            raw = item.get("label", "") if isinstance(item, dict) else str(item or "")
            values.append((field, str(raw), _normalise(raw)))
    return values


class TurinAuthorityGraphMaterializer:
    """Creates a new graph snapshot; it never updates document metadata or historic runs."""

    @staticmethod
    def build_relations(documents: list[dict[str, Any]], authorities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        people = [item for item in authorities if item["authority_type"] == "agent_employment"]
        projects = [item for item in authorities if item["authority_type"] == "ddr_projects"]
        relations: list[dict[str, Any]] = []
        for document in documents:
            metadata = dict(document.get("authority_data") or {})
            source_values = _values(metadata)
            for authority in people:
                label = _normalise(authority["label"])
                match = next(((field, raw, normalized) for field, raw, normalized in source_values if label and label == normalized), None)
                if match:
                    field, raw, normalized = match
                    relations.append({**document, **authority, "relation_type": "PERSON_ASSOCIATED_WITH_SOURCE", "derivation_method": "exact_controlled_metadata", "derivation_tier": "TIER_3_EXACT_CONTROLLED_METADATA", "trigger_field": field, "trigger_value_raw": raw, "trigger_value_normalized": normalized, "authority_value_normalized": label, "trigger_json_path": f"attached_media.{field}", "source_of_relation": "record_v1.attached_media.creator_or_keyword"})
            for authority in projects:
                identifier = str(authority["authority_id"])
                match = None
                for field in ("title", "record_title", "caption", "box_title"):
                    raw = metadata.get(field) or document.get(field)
                    if raw and re.search(rf"\b(?:job|project)\s*{re.escape(identifier)}\b", str(raw), re.IGNORECASE):
                        match = (field, str(raw))
                        break
                if match:
                    field, raw = match
                    relations.append({**document, **authority, "relation_type": "PROJECT_SOURCE", "derivation_method": "exact_controlled_identifier", "derivation_tier": "TIER_2_EXACT_CONTROLLED_IDENTIFIER", "trigger_field": field, "trigger_value_raw": raw, "trigger_value_normalized": _normalise(raw), "authority_value_normalized": _normalise(identifier), "trigger_json_path": f"attached_media.{field}", "source_of_relation": "record_v1.title_or_record_title"})
            collection = metadata.get("parent_collection") or metadata.get("record_title") or metadata.get("box_title")
            if collection and str(collection).strip():
                field = "parent_collection" if metadata.get("parent_collection") else ("record_title" if metadata.get("record_title") else "box_title")
                relations.append({**document, "authority_type": "archive_collection", "authority_id": _normalise(collection), "authority_label": str(collection), "relation_type": "SOURCE_COLLECTION", "derivation_method": "exact_archive_metadata", "derivation_tier": "TIER_3_EXACT_CONTROLLED_METADATA", "trigger_field": field, "trigger_value_raw": str(collection), "trigger_value_normalized": _normalise(collection), "authority_value_normalized": _normalise(collection), "trigger_json_path": f"attached_media.{field}", "source_of_relation": "record_v1.attached_media.parent_collection_or_record_title"})
        return relations

    def materialize(self, db: Any, corpus_version: str) -> dict[str, Any]:
        documents = [dict(row) for row in db.execute(text("""SELECT document_id,pid,archive_record_pid,asset_pid,asset_id,title,authority_data FROM documents WHERE corpus_version=:corpus_version"""), {"corpus_version": corpus_version}).mappings().all()]
        authorities = [dict(row) for row in db.execute(text("""SELECT authority_type,authority_id,label FROM database_authorities""")).mappings().all()]
        relations = self.build_relations(documents, authorities)
        db.execute(text("""INSERT INTO turin_archive_authority_graph_snapshots(snapshot_version,corpus_version,metadata_snapshot_version,materialiser_version) VALUES (:snapshot,:corpus,:metadata,:materialiser) ON CONFLICT (snapshot_version) DO UPDATE SET corpus_version=EXCLUDED.corpus_version,metadata_snapshot_version=EXCLUDED.metadata_snapshot_version,materialiser_version=EXCLUDED.materialiser_version"""), {"snapshot": SNAPSHOT_VERSION, "corpus": corpus_version, "metadata": METADATA_SNAPSHOT_VERSION, "materialiser": MATERIALISER_VERSION})
        for relation in relations:
            digest = hashlib.sha256("|".join(str(relation.get(key) or "") for key in ("authority_type", "authority_id", "relation_type", "document_id", "derivation_method")).encode()).hexdigest()[:20]
            db.execute(text("""INSERT INTO turin_archive_authority_source_relations(relation_id,snapshot_version,authority_type,authority_id,authority_label,relation_type,archive_record_pid,attached_media_pid,asset_pid,asset_id,document_id,derivation_method,source_of_relation,derivation_tier,trigger_field,trigger_value_raw,trigger_value_normalized,authority_value_normalized,source_snapshot_version,trigger_json_path,source_record_pid,source_attached_media_pid,source_asset_pid) VALUES (:id,:snapshot,:type,:authority_id,:label,:relation_type,:record,:media,:asset_pid,:asset_id,:document,:method,:source,:tier,:field,:raw,:normalized,:authority_normalized,:source_snapshot,:path,:source_record,:source_media,:source_asset) ON CONFLICT (relation_id) DO UPDATE SET derivation_tier=EXCLUDED.derivation_tier,trigger_field=EXCLUDED.trigger_field,trigger_value_raw=EXCLUDED.trigger_value_raw,trigger_value_normalized=EXCLUDED.trigger_value_normalized,authority_value_normalized=EXCLUDED.authority_value_normalized,source_snapshot_version=EXCLUDED.source_snapshot_version,trigger_json_path=EXCLUDED.trigger_json_path,source_record_pid=EXCLUDED.source_record_pid,source_attached_media_pid=EXCLUDED.source_attached_media_pid,source_asset_pid=EXCLUDED.source_asset_pid"""), {"id": f"tagv1-{digest}", "snapshot": SNAPSHOT_VERSION, "type": relation["authority_type"], "authority_id": relation["authority_id"], "label": relation["authority_label"] if "authority_label" in relation else relation["label"], "relation_type": relation["relation_type"], "record": relation.get("archive_record_pid"), "media": relation.get("pid"), "asset_pid": relation.get("asset_pid"), "asset_id": relation.get("asset_id"), "document": relation["document_id"], "method": relation["derivation_method"], "source": relation["source_of_relation"], "tier": relation["derivation_tier"], "field": relation["trigger_field"], "raw": relation["trigger_value_raw"], "normalized": relation["trigger_value_normalized"], "authority_normalized": relation["authority_value_normalized"], "source_snapshot": METADATA_SNAPSHOT_VERSION, "path": relation["trigger_json_path"], "source_record": relation.get("archive_record_pid"), "source_media": relation.get("pid"), "source_asset": relation.get("asset_pid")})
        return {"snapshot_version": SNAPSHOT_VERSION, "documents": len(documents), "relations": len(relations)}