"""Deterministic local authority-graph source nomination for Turin V3.1."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text


GRAPH_SNAPSHOT_VERSION = "turin-archive-authority-graph-v1"


def normalise(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _contains_phrase(question: str, phrase: str) -> bool:
    return bool(phrase and re.search(rf"(?:^|\s){re.escape(phrase)}(?:$|\s)", question))


class TurinRetrievalV31AuthorityGraph:
    """Resolves only explicit, persisted graph edges; it never infers a relationship."""

    @staticmethod
    def resolve(question: str, analysis: dict[str, Any], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_question = normalise(question)
        project_ids = {re.search(r"\d+", item).group(0) for item in analysis["terms"]["PROJECT"] if re.search(r"\d+", item)}
        resolutions: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for edge in edges:
            authority_type = str(edge["authority_type"])
            authority_id = str(edge["authority_id"])
            label = str(edge["authority_label"])
            normalized_label = normalise(label)
            trigger = normalise(str(edge.get("trigger_value_raw") or ""))
            method = None
            if authority_type == "ddr_projects" and authority_id in project_ids:
                method = "exact_project_identifier"
            elif authority_type == "agent_employment" and _contains_phrase(normalized_question, normalized_label):
                method = "exact_normalized_authority_label"
            elif authority_type == "archive_collection" and (_contains_phrase(normalized_question, normalized_label) or _contains_phrase(normalized_question, trigger)):
                method = "exact_collection_or_unit_label"
            if method and (authority_type, authority_id) not in seen:
                seen.add((authority_type, authority_id))
                resolutions.append({"question_term": label if method != "exact_project_identifier" else f"Job {authority_id}", "normalized_question_term": normalized_label if method != "exact_project_identifier" else authority_id, "authority_id": authority_id, "authority_type": authority_type, "authority_label": label, "resolution_method": method})
        return resolutions

    def nominate(self, db: Any, question: str, analysis: dict[str, Any], corpus_version: str, document_predicate: str) -> dict[str, Any]:
        rows = [dict(row) for row in db.execute(text("""
            SELECT r.relation_id, r.authority_type, r.authority_id, r.authority_label, r.relation_type,
                   r.document_id, r.archive_record_pid, r.attached_media_pid, r.asset_pid,
                   r.derivation_tier, r.derivation_method, r.trigger_field, r.trigger_value_raw,
                   r.trigger_value_normalized, r.authority_value_normalized, r.source_snapshot_version,
                   r.trigger_json_path, d.pid, d.title, d.filename, d.authority_data, d.archive_record_id,
                   d.asset_id, d.asset_id_or_asset_pid, d.source_uri, d.archive_metadata_source,
                   d.metadata_sync_status, d.corpus_version
            FROM turin_archive_authority_source_relations r
            JOIN documents d ON d.document_id = r.document_id
            WHERE r.snapshot_version = :snapshot_version
              AND """ + document_predicate + """
            ORDER BY r.relation_id
        """), {"snapshot_version": GRAPH_SNAPSHOT_VERSION, "corpus_version": corpus_version}).mappings().all()]
        resolutions = self.resolve(question, analysis, rows)
        resolved = {(item["authority_type"], item["authority_id"]): item for item in resolutions}
        edges = [{**edge, "resolution": resolved[(str(edge["authority_type"]), str(edge["authority_id"]))]} for edge in rows if (str(edge["authority_type"]), str(edge["authority_id"])) in resolved]
        return {"resolutions": resolutions, "edges": edges}