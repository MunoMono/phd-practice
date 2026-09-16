"""V3.6 semantic-only reranking over the complete V3.2 top-three source union."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "artifacts" / "turin_v36_semantic_configuration.json"
CACHE_PATH = ROOT / "artifacts" / "turin_v36_passage_embedding_cache.json"


class TurinRetrievalV36SemanticReranker:
    """Local documentary-only semantic scorer; it never generates or nominates passages."""

    def __init__(self) -> None:
        self.configuration_bytes = CONFIG_PATH.read_bytes()
        self.configuration = json.loads(self.configuration_bytes)
        self.configuration_sha256 = hashlib.sha256(self.configuration_bytes).hexdigest()
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._model: SentenceTransformer | None = None
        self.cache = self._load_cache()
        self.performance = {"model_load_seconds": None, "question_embedding_latencies_ms": [], "passage_embedding_latencies_ms": [], "rerank_latencies_ms": []}

    def _load_cache(self) -> dict[str, list[float]]:
        if not CACHE_PATH.exists():
            return {}
        return json.loads(CACHE_PATH.read_text()).get(self.configuration_sha256, {})

    def _save_cache(self) -> None:
        CACHE_PATH.write_text(json.dumps({self.configuration_sha256: self.cache}, separators=(",", ":")) + "\n")

    def _model_instance(self) -> SentenceTransformer:
        if self._model is None:
            started = time.perf_counter()
            self._model = SentenceTransformer(self.configuration["embedding_model"], cache_folder=str(Path.home() / ".cache" / "huggingface"), device=self.device)
            self.performance["model_load_seconds"] = round(time.perf_counter() - started, 4)
        return self._model

    def rerank(self, question: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        unique = {str(item["chunk_id"]): item for item in candidates}
        pool = sorted(unique.values(), key=lambda item: (-item["passage_score"], item.get("chunk_index", 0), str(item["chunk_id"])))
        started = time.perf_counter()
        query_started = time.perf_counter()
        query = self._model_instance().encode(self.configuration["query_instruction"] + question, normalize_embeddings=True, convert_to_numpy=True)
        self.performance["question_embedding_latencies_ms"].append(round((time.perf_counter() - query_started) * 1000, 3))
        keys = [f"{item['chunk_id']}:{hashlib.sha256(str(item.get('chunk_text') or '').encode()).hexdigest()}" for item in pool]
        missing = [(key, str(item.get("chunk_text") or "")) for key, item in zip(keys, pool) if key not in self.cache]
        if missing:
            embedding_started = time.perf_counter()
            vectors = self._model_instance().encode([text_value for _, text_value in missing], normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
            self.performance["passage_embedding_latencies_ms"].append(round((time.perf_counter() - embedding_started) * 1000 / len(missing), 3))
            self.cache.update({key: vector.tolist() for (key, _), vector in zip(missing, vectors)})
            self._save_cache()
        scored = [{**item, "question_embedding_version": self.configuration_sha256, "passage_embedding_version": self.configuration_sha256, "semantic_similarity": round(float(np.dot(query, np.asarray(self.cache[key], dtype=np.float32))), 8)} for item, key in zip(pool, keys)]
        semantic = sorted(scored, key=lambda item: (-item["semantic_similarity"], item.get("chunk_index", 0), str(item["chunk_id"])))
        semantic_ranks = {str(item["chunk_id"]): rank for rank, item in enumerate(semantic, 1)}
        deterministic_ranks = {str(item["chunk_id"]): rank for rank, item in enumerate(pool, 1)}
        self.performance["rerank_latencies_ms"].append(round((time.perf_counter() - started) * 1000, 3))
        return {"candidate_count_before_deduplication": len(candidates), "candidate_count_after_deduplication": len(pool), "candidate_pool": [{**item, "v32_rank": deterministic_ranks[str(item["chunk_id"])], "semantic_rank": semantic_ranks[str(item["chunk_id"])]} for item in pool], "final": self._final(semantic)}

    @staticmethod
    def _final(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        used_assets: set[str] = set()
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
