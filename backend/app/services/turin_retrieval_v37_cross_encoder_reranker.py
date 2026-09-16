"""Bounded V3.7 joint question-passage relevance reranking."""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

import psutil
from sentence_transformers.cross_encoder import CrossEncoder


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "artifacts" / "turin_v37_cross_encoder_configuration.json"


class TurinRetrievalV37CrossEncoderReranker:
    """Scores only [original question, raw documentary chunk] pairs on the local Mac."""

    def __init__(self) -> None:
        configuration_bytes = CONFIG_PATH.read_bytes()
        self.configuration = json.loads(configuration_bytes)
        self.configuration_sha256 = hashlib.sha256(configuration_bytes).hexdigest()
        self.model: CrossEncoder | None = None
        self.performance = {"model_load_seconds": None, "pair_scoring_latencies_ms": [], "full_query_rerank_latencies_ms": [], "peak_process_rss_bytes": 0}

    def _model_instance(self) -> CrossEncoder:
        if self.model is None:
            started = time.perf_counter()
            self.model = CrossEncoder(self.configuration["reranker_model"], max_length=self.configuration["max_length"])
            self.model.model.to(self.configuration["device"])
            self.performance["model_load_seconds"] = round(time.perf_counter() - started, 4)
        return self.model

    def rerank(self, question: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        unique = {str(candidate["chunk_id"]): candidate for candidate in candidates}
        pool = sorted(unique.values(), key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        model = self._model_instance()
        token_diagnostics = [self._token_diagnostic(model, question, str(item.get("chunk_text") or "")) for item in pool]
        started = time.perf_counter()
        scores = model.predict([(question, str(item.get("chunk_text") or "")) for item in pool], batch_size=self.configuration["batch_size"], show_progress_bar=False)
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.performance["pair_scoring_latencies_ms"].append(round(elapsed_ms / max(len(pool), 1), 3))
        self.performance["full_query_rerank_latencies_ms"].append(round(elapsed_ms, 3))
        self.performance["peak_process_rss_bytes"] = max(self.performance["peak_process_rss_bytes"], psutil.Process().memory_info().rss)
        scored = [{**candidate, **diagnostic, "cross_encoder_raw_score": round(float(score), 8), "cross_encoder_configuration_sha256": self.configuration_sha256} for candidate, diagnostic, score in zip(pool, token_diagnostics, scores)]
        cross_encoder = sorted(scored, key=lambda item: (-item["cross_encoder_raw_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        deterministic_rank = {str(item["chunk_id"]): rank for rank, item in enumerate(pool, 1)}
        cross_rank = {str(item["chunk_id"]): rank for rank, item in enumerate(cross_encoder, 1)}
        rrf_k = self.configuration["optional_rrf_control"]["k"]
        rrf = sorted(scored, key=lambda item: (-(1 / (rrf_k + deterministic_rank[str(item["chunk_id"])]) + 1 / (rrf_k + cross_rank[str(item["chunk_id"])])), item.get("chunk_index", 0), str(item["chunk_id"])))
        rrf_rank = {str(item["chunk_id"]): rank for rank, item in enumerate(rrf, 1)}
        traces = [{**item, "v32_rank": deterministic_rank[str(item["chunk_id"])], "cross_encoder_rank": cross_rank[str(item["chunk_id"])], "rrf_rank": rrf_rank[str(item["chunk_id"])], "rrf_score": round(1 / (rrf_k + deterministic_rank[str(item["chunk_id"])]) + 1 / (rrf_k + cross_rank[str(item["chunk_id"])]), 10)} for item in scored]
        return {"candidate_count_before_deduplication": len(candidates), "candidate_count_after_deduplication": len(pool), "candidate_pool": sorted(traces, key=lambda item: item["v32_rank"]), "cross_encoder_final": self._final(cross_encoder), "rrf_final": self._final(rrf)}

    def _token_diagnostic(self, model: CrossEncoder, question: str, passage: str) -> dict[str, Any]:
        original_passage_token_count = len(model.tokenizer(passage, add_special_tokens=False)["input_ids"])
        pair_tokens = len(model.tokenizer(question, passage, add_special_tokens=True, truncation=False)["input_ids"])
        return {"original_passage_token_count": original_passage_token_count, "truncated": pair_tokens > self.configuration["max_length"]}

    @staticmethod
    def _final(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        used_assets: set[str] = set()
        for candidate in ranked:
            if candidate.get("passage_adequacy") == "PASSAGE_IRRELEVANT":
                continue
            asset = str(candidate.get("canonical_asset_id") or candidate.get("asset_id") or candidate["document_id"])
            if asset in used_assets:
                continue
            selected.append(candidate)
            used_assets.add(asset)
            if len(selected) == 5:
                break
        return selected

    def performance_summary(self) -> dict[str, Any]:
        return {key: statistics.median(value) if isinstance(value, list) and value else value for key, value in self.performance.items()}
