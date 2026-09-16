"""Bounded, local semantic reranking of V3.2 documentary passage candidates."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import torch
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "artifacts" / "turin_v35_semantic_configuration.json"
CACHE_PATH = ROOT / "artifacts" / "turin_v35_passage_embedding_cache.json"


class TurinRetrievalV35SemanticReranker:
    """Embeds only the bounded V3.2 documentary candidate pool on the local host."""

    def __init__(self) -> None:
        self.configuration_bytes = CONFIG_PATH.read_bytes()
        self.configuration = json.loads(self.configuration_bytes)
        self.configuration_sha256 = hashlib.sha256(self.configuration_bytes).hexdigest()
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._model: SentenceTransformer | None = None
        self._cache = self._load_cache()
        self.performance = {"model_load_seconds": None, "question_embedding_latencies_ms": [], "passage_embedding_latencies_ms": [], "uncached_rerank_latencies_ms": [], "cached_rerank_latencies_ms": [], "peak_process_rss_bytes": 0}

    def _load_cache(self) -> dict[str, list[float]]:
        if not CACHE_PATH.exists():
            return {}
        payload = json.loads(CACHE_PATH.read_text())
        return payload.get(self.configuration_sha256, {})

    def _save_cache(self) -> None:
        payload = {self.configuration_sha256: self._cache}
        CACHE_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")

    def _model_instance(self) -> SentenceTransformer:
        if self._model is None:
            started = time.perf_counter()
            self._model = SentenceTransformer(self.configuration["embedding_model"], cache_folder=str(Path.home() / ".cache" / "huggingface"), device=self.device)
            self.performance["model_load_seconds"] = round(time.perf_counter() - started, 4)
        return self._model

    def rerank(self, question: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        pool = sorted(candidates, key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))[:self.configuration["candidate_cap"]]
        query_started = time.perf_counter()
        query = self._model_instance().encode(self.configuration["query_instruction"] + question, normalize_embeddings=True, convert_to_numpy=True)
        self.performance["question_embedding_latencies_ms"].append(round((time.perf_counter() - query_started) * 1000, 3))
        uncached = []
        vectors: list[np.ndarray] = []
        for candidate in pool:
            text_value = str(candidate.get("chunk_text") or "")
            key = f"{candidate['chunk_id']}:{hashlib.sha256(text_value.encode()).hexdigest()}"
            if key in self._cache:
                vectors.append(np.asarray(self._cache[key], dtype=np.float32))
                continue
            uncached.append((key, text_value))
            vectors.append(np.empty(self.configuration["embedding_dimension"], dtype=np.float32))
        if uncached:
            embedding_started = time.perf_counter()
            embedded = self._model_instance().encode([text_value for _, text_value in uncached], normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
            self.performance["passage_embedding_latencies_ms"].append(round((time.perf_counter() - embedding_started) * 1000 / len(uncached), 3))
            for (key, _), vector in zip(uncached, embedded):
                self._cache[key] = vector.tolist()
            self._save_cache()
        for index, candidate in enumerate(pool):
            text_value = str(candidate.get("chunk_text") or "")
            key = f"{candidate['chunk_id']}:{hashlib.sha256(text_value.encode()).hexdigest()}"
            vectors[index] = np.asarray(self._cache[key], dtype=np.float32)
        elapsed = (time.perf_counter() - query_started) * 1000
        self.performance["uncached_rerank_latencies_ms" if uncached else "cached_rerank_latencies_ms"].append(round(elapsed, 3))
        self.performance["peak_process_rss_bytes"] = max(self.performance["peak_process_rss_bytes"], psutil.Process().memory_info().rss)
        scored = [{**candidate, "question_embedding_version": self.configuration_sha256, "passage_embedding_version": self.configuration_sha256, "semantic_similarity": round(float(np.dot(query, vector)), 8)} for candidate, vector in zip(pool, vectors)]
        deterministic = sorted(scored, key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        semantic = sorted(scored, key=lambda item: (-item["semantic_similarity"], item.get("chunk_index", 0), str(item["chunk_id"])))
        deterministic_rank = {str(item["chunk_id"]): rank for rank, item in enumerate(deterministic, 1)}
        semantic_rank = {str(item["chunk_id"]): rank for rank, item in enumerate(semantic, 1)}
        rrf = sorted(scored, key=lambda item: (-(1 / (60 + deterministic_rank[str(item["chunk_id"])]) + 1 / (60 + semantic_rank[str(item["chunk_id"])])), item.get("chunk_index", 0), str(item["chunk_id"])))
        traces = []
        for candidate in scored:
            chunk_id = str(candidate["chunk_id"])
            traces.append({**candidate, "v32_rank": deterministic_rank[chunk_id], "semantic_rank": semantic_rank[chunk_id], "rrf_rank": next(rank for rank, item in enumerate(rrf, 1) if str(item["chunk_id"]) == chunk_id), "rrf_score": round(1 / (60 + deterministic_rank[chunk_id]) + 1 / (60 + semantic_rank[chunk_id]), 10)})
        return {"candidate_pool": sorted(traces, key=lambda item: item["v32_rank"]), "semantic_only": self._final(semantic), "rrf": self._final(rrf), "v32_deterministic": self._final(deterministic)}

    @staticmethod
    def _final(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected = []; used_assets: set[str] = set()
        for item in ranked:
            if item.get("passage_adequacy") == "PASSAGE_IRRELEVANT":
                continue
            asset = str(item.get("canonical_asset_id") or item.get("asset_id") or item["document_id"])
            if asset in used_assets:
                continue
            selected.append(item)
            used_assets.add(asset)
            if len(selected) == 5:
                break
        return selected
