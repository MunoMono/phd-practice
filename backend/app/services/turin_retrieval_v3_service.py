"""Read-only multi-lane, coverage-aware retrieval for the frozen Turin corpus."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.retrieval_validation_service import RetrievalValidationService
from app.services.turin_retrieval_v3_coverage import TurinRetrievalV3Coverage
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v31_authority_graph import TurinRetrievalV31AuthorityGraph
from app.services.turin_retrieval_v34_slots import TurinRetrievalV34Slots


CORPUS_VERSION = "corpus_f40d78dbce52"
METADATA_SNAPSHOT = "turin-archive-metadata-v1"
LANE_LIMIT = 30
SOURCE_LIMIT = 80
PASSAGE_LIMIT = 150

SOURCE_NOMINATION_CORPUS_PREDICATE = """
    d.corpus_version = :corpus_version
    AND d.use_for_ml = 1
    AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
    AND EXISTS (
        SELECT 1
        FROM document_chunks nomination_chunk
        WHERE nomination_chunk.document_id = d.document_id
          AND nomination_chunk.corpus_version = d.corpus_version
    )
"""

DOCUMENTARY_CHUNK_CORPUS_PREDICATE = """
    dc.corpus_version = :corpus_version
    AND d.corpus_version = :corpus_version
    AND d.use_for_ml = 1
    AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
"""


class TurinRetrievalV3Service:
    """Model-neutral diagnostic service. It never creates a run or calls inference."""

    def __init__(self, use_authority_graph: bool = True, passage_version: str = "v3.1", selection_version: str = "v3.2") -> None:
        self.analyzer = TurinRetrievalV3QuestionAnalyzer()
        self.ranker = TurinRetrievalV3Ranker()
        self.coverage = TurinRetrievalV3Coverage()
        self.mapper = RetrievalValidationService()
        self.authority_graph = TurinRetrievalV31AuthorityGraph()
        self.use_authority_graph = use_authority_graph
        self.passage_version = passage_version
        self.selection_version = selection_version
        self.last_passage_candidates: list[dict[str, Any]] = []

    @staticmethod
    def _query(terms: list[str]) -> str:
        return " OR ".join(f'"{term}"' if " " in term else term for term in terms[:12])

    def _text_lane(self, db: Any, lane: str, terms: list[str], corpus_version: str) -> list[dict[str, Any]]:
        query = self._query(terms)
        if not query:
            return []
        rows = db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type, dc.search_tsv::text AS search_tsv,
                   NULLIF(to_jsonb(dc)->>'source_page', '')::integer AS source_page,
                   to_jsonb(dc)->>'source_section' AS source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                   ts_rank(dc.search_tsv, websearch_to_tsquery('english', :query)) AS score
            FROM document_chunks dc JOIN documents d USING(document_id)
                        WHERE dc.search_tsv @@ websearch_to_tsquery('english', :query)
                            AND """ + DOCUMENTARY_CHUNK_CORPUS_PREDICATE + """
            ORDER BY score DESC, dc.chunk_id ASC LIMIT :limit
        """), {"query": query, "corpus_version": corpus_version, "limit": LANE_LIMIT}).mappings().all()
        return [{**dict(row), "lane": lane, "lane_score": float(row["score"] or 0)} for row in rows]

    def _metadata_lane(self, db: Any, terms: list[str], corpus_version: str) -> list[dict[str, Any]]:
        query = self._query(terms)
        if not query:
            return []
        rows = db.execute(text("""
            SELECT d.document_id, d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version,
                   ts_rank(to_tsvector('simple', concat_ws(' ', d.title, d.authority_data->>'caption', d.authority_data->>'record_title', d.authority_data->>'keywords', d.authority_data->>'master_label')), websearch_to_tsquery('simple', :query)) AS score
            FROM documents d
            WHERE to_tsvector('simple', concat_ws(' ', d.title, d.authority_data->>'caption', d.authority_data->>'record_title', d.authority_data->>'keywords', d.authority_data->>'master_label')) @@ websearch_to_tsquery('simple', :query)
              AND """ + SOURCE_NOMINATION_CORPUS_PREDICATE + """
            ORDER BY score DESC, d.document_id ASC LIMIT :limit
        """), {"query": query, "corpus_version": corpus_version, "limit": LANE_LIMIT}).mappings().all()
        return [{**dict(row), "lane": "archival_metadata", "lane_score": float(row["score"] or 0)} for row in rows]

    def _source_rows(self, db: Any, document_id: str, corpus_version: str) -> list[dict[str, Any]]:
        return [dict(row) for row in db.execute(text("""
            SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.chunk_type, dc.search_tsv::text AS search_tsv,
                   NULLIF(to_jsonb(dc)->>'source_page', '')::integer AS source_page,
                   to_jsonb(dc)->>'source_section' AS source_section, dc.chunk_metadata,
                   d.pid, d.title, d.filename, d.authority_id, d.authority_data, d.archive_record_id,
                   d.archive_record_pid, d.asset_id, d.asset_pid, d.asset_id_or_asset_pid, d.source_uri,
                   d.archive_metadata_source, d.metadata_sync_status, d.corpus_version
            FROM document_chunks dc JOIN documents d USING(document_id)
                        WHERE dc.document_id = :document_id
                            AND """ + DOCUMENTARY_CHUNK_CORPUS_PREDICATE + """
            ORDER BY dc.chunk_index, dc.chunk_id LIMIT :limit
        """), {"document_id": document_id, "corpus_version": corpus_version, "limit": PASSAGE_LIMIT}).mappings().all()]

    def _graph_lane(self, db: Any, question: str, analysis: dict[str, Any], corpus_version: str) -> dict[str, Any]:
        nominated = self.authority_graph.nominate(db, question, analysis, corpus_version, SOURCE_NOMINATION_CORPUS_PREDICATE)
        rows = []
        for edge in nominated["edges"]:
            relation_type = edge["relation_type"]
            component = {"authority_person_match": int(relation_type == "PERSON_ASSOCIATED_WITH_SOURCE"), "authority_project_match": int(relation_type == "PROJECT_SOURCE"), "source_collection_match": int(relation_type == "SOURCE_COLLECTION")}
            rows.append({**edge, "lane": "authority_graph", "lane_score": sum(component.values()) * 0.5, "authority_graph_component": component})
        return {"rows": rows, "resolutions": nominated["resolutions"]}

    def retrieve(self, db: Any, question: str, selected_top_k: int = 5, corpus_version: str = CORPUS_VERSION) -> dict[str, Any]:
        analysis = self.analyzer.analyze(question).as_dict()
        lane_rows: dict[str, list[dict[str, Any]]] = {}
        for lane, terms in analysis["lane_queries"].items():
            lane_rows[lane] = self._metadata_lane(db, terms, corpus_version) if lane == "archival_metadata" else self._text_lane(db, lane, terms, corpus_version)
        graph = self._graph_lane(db, question, analysis, corpus_version) if self.use_authority_graph else {"rows": [], "resolutions": []}
        if self.use_authority_graph:
            lane_rows["authority_graph"] = graph["rows"]
        sources: dict[str, dict[str, Any]] = {}
        for lane, rows in lane_rows.items():
            for row in rows:
                identity = ExploratoryRetrievalService.canonical_asset_identity(row)
                source = sources.setdefault(identity, {**row, "canonical_asset_id": identity, "lane_nominations": [], "authority_graph_signals": {"authority_person_match": 0, "authority_project_match": 0, "source_collection_match": 0, "authority_edge_count": 0, "authority_relation_types": [], "authority_ids": [], "authority_labels": [], "edges": []}, "source_signals": {"best_text_score": 0.0, "entity_score": 0.0, "phrase_proximity_score": 0.0, "metadata_nomination_score": 0.0, "authority_graph_score": 0.0, "source_type_relevance": 0.0, "temporal_relevance": 0.0}})
                source["lane_nominations"].append({"lane": lane, "score": row["lane_score"]})
                if lane == "archival_metadata": source["source_signals"]["metadata_nomination_score"] = max(source["source_signals"]["metadata_nomination_score"], row["lane_score"])
                if lane == "authority_graph":
                    signals = source["authority_graph_signals"]
                    for key, value in row["authority_graph_component"].items(): signals[key] = max(signals[key], value)
                    signals["authority_edge_count"] += 1
                    signals["authority_relation_types"] = sorted(set(signals["authority_relation_types"] + [row["relation_type"]]))
                    signals["authority_ids"] = sorted(set(signals["authority_ids"] + [row["authority_id"]]))
                    signals["authority_labels"] = sorted(set(signals["authority_labels"] + [row["authority_label"]]))
                    signals["edges"].append({key: row[key] for key in ("relation_id", "authority_type", "authority_id", "authority_label", "relation_type", "derivation_tier", "derivation_method", "trigger_field", "trigger_value_raw", "trigger_value_normalized", "authority_value_normalized", "source_snapshot_version", "trigger_json_path", "resolution")})
                    source["source_signals"]["authority_graph_score"] = min(1.0, sum(signals[key] for key in ("authority_person_match", "authority_project_match", "source_collection_match")) * 0.5)
                else: source["source_signals"]["best_text_score"] = max(source["source_signals"]["best_text_score"], row["lane_score"])
                if lane == "entity": source["source_signals"]["entity_score"] = max(source["source_signals"]["entity_score"], row["lane_score"])
                if lane == "relation_phrase": source["source_signals"]["phrase_proximity_score"] = max(source["source_signals"]["phrase_proximity_score"], row["lane_score"])
                if lane == "temporal_event": source["source_signals"]["temporal_relevance"] = max(source["source_signals"]["temporal_relevance"], row["lane_score"])
        ranked_sources = sorted(sources.values(), key=lambda item: (-sum(signal for signal in item["source_signals"].values()), item["document_id"]))[:SOURCE_LIMIT]
        passages: list[dict[str, Any]] = []
        for source in ranked_sources:
            source_type = str((source.get("authority_data") or {}).get("source_type") or (source.get("authority_data") or {}).get("document_type") or "unclassified")
            candidates = [self.ranker.score_passage({**row, "canonical_asset_id": source["canonical_asset_id"], "source_type": source_type, "lane_nominations": source["lane_nominations"], "source_signals": source["source_signals"], "authority_graph_signals": source["authority_graph_signals"]}, analysis, v32=self.passage_version == "v3.2") for row in self._source_rows(db, source["document_id"], corpus_version)]
            if candidates:
                passages.extend(sorted(candidates, key=lambda item: (-item["passage_score"], item["chunk_index"], str(item["chunk_id"])))[:3])
        self.last_passage_candidates = passages
        if self.selection_version == "v3.4":
            passages = TurinRetrievalV34Slots.annotate(passages, analysis)
        final = self.coverage.select(passages, analysis["required_facets"], selected_top_k, self.selection_version, analysis)
        results = []
        for item in final:
            mapped = self.mapper._result_from_row({**item, "score": item["passage_score"]}, item["rank"])
            ExploratoryRetrievalService._apply_snapshot_identity(mapped, item)
            results.append({**mapped, "canonical_asset_id": item["canonical_asset_id"], "lane_nominations": item["lane_nominations"], "source_signals": item["source_signals"], "authority_graph_signals": item["authority_graph_signals"], "passage_score": item["passage_score"], "passage_score_components": item["passage_score_components"], "global_score_components": item["global_score_components"], "passage_adequacy": item["passage_adequacy"], "facet_coverage": item["facet_coverage"], "selection_reason": item["selection_reason"], "passage_evidence_channel": item["passage_evidence_channel"], "metadata_is_documentary_evidence": False})
        for result, item in zip(results, final):
            result["filled_slots"] = item.get("filled_slots", [])
        adequacy = self.coverage.adequacy(results, analysis)
        return {"question_analysis": analysis, "retrieval_template": analysis["template"], "lane_queries": analysis["lane_queries"], "authority_resolutions": graph["resolutions"], "lane_candidate_counts": {lane: len(rows) for lane, rows in lane_rows.items()}, "canonical_source_ranking": [{"canonical_asset_id": item["canonical_asset_id"], "document_id": item["document_id"], "lane_nominations": item["lane_nominations"], "source_signals": item["source_signals"], "authority_graph_signals": item["authority_graph_signals"]} for item in ranked_sources], "passage_ranking": [{"chunk_id": item["chunk_id"], "document_id": item["document_id"], "passage_score": item["passage_score"], "passage_score_components": item["passage_score_components"], "facet_coverage": item["facet_coverage"]} for item in passages], "final_five": results, "retrieval_adequacy": adequacy, "retrieval": {"strategy": "turin-retrieval-v3.2" if self.passage_version == "v3.2" else ("turin-retrieval-v3.1" if self.use_authority_graph else "turin-retrieval-v3"), "corpus_version": corpus_version, "metadata_snapshot_version": METADATA_SNAPSHOT, "raw_lane_candidates": sum(len(rows) for rows in lane_rows.values()), "unique_canonical_assets": len(sources), "unique_archive_records": len({item.get("archive_record_pid") for item in sources.values() if item.get("archive_record_pid")}), "source_type_distribution": dict(defaultdict(int, {str(item.get("source_type") or "unclassified"): 1 for item in final}))}, "results": results, "diagnostics": {"result_count": len(results), "candidate_count": len(sources), "graph_nominated_sources": sum(bool(item["authority_graph_signals"]["authority_edge_count"]) for item in sources.values()), "graph_only_nominated_sources": sum(bool(item["authority_graph_signals"]["authority_edge_count"]) and len(item["lane_nominations"]) == item["authority_graph_signals"]["authority_edge_count"] for item in sources.values()), "graph_nominated_documentary_not_found": sum(bool(item["authority_graph_signals"]["authority_edge_count"]) and item["document_id"] not in {passage["document_id"] for passage in passages} for item in sources.values()), "diagnostic_state": adequacy["status"], "metadata_documentary_leakage": 0}}