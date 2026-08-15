"""Granite service backed by a local quantized GGUF runtime (Ollama)."""

import asyncio
import logging
import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import psutil

from app.services.metadata_roles import format_granite_source_block

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model loading status states."""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


class GraniteService:
    """Low-resource Granite inference service via local Ollama HTTP API."""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        # Quantized Granite-compatible runtime model tag.
        self.model_name = os.getenv("OLLAMA_MODEL", "granite3.1-dense:2b-instruct-q4_K_M")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.device = "cpu"
        self.max_new_tokens = int(os.getenv("GRANITE_MAX_TOKENS", "384"))
        self.temperature = float(os.getenv("GRANITE_TEMPERATURE", "0.2"))
        self.max_input_chars = int(os.getenv("GRANITE_MAX_INPUT_CHARS", "6000"))
        self.timeout_seconds = int(os.getenv("GRANITE_TIMEOUT_SECONDS", "180"))
        self.load_timeout_seconds = int(os.getenv("OLLAMA_LOAD_TIMEOUT_SECONDS", "600"))
        self.load_retry_count = int(os.getenv("OLLAMA_LOAD_RETRY_COUNT", "3"))
        self.load_retry_delay_seconds = int(os.getenv("OLLAMA_LOAD_RETRY_DELAY_SECONDS", "5"))
        self._lock = asyncio.Lock()

        self._status = ModelStatus.NOT_LOADED
        self._error_message: Optional[str] = None
        
    def load_model(self) -> bool:
        """Validate local Ollama runtime and ensure model is available."""
        try:
            self._status = ModelStatus.LOADING
            self._error_message = None

            logger.info(f"Validating Ollama runtime at {self.ollama_base_url}")
            logger.info(f"Target model tag: {self.model_name}")
            load_timeout = httpx.Timeout(connect=10.0, read=self.load_timeout_seconds, write=self.load_timeout_seconds, pool=30.0)
            with httpx.Client(timeout=load_timeout) as client:
                health = client.get(f"{self.ollama_base_url}/api/tags")
                health.raise_for_status()
                tags = health.json().get("models", [])
                installed = {m.get("name") for m in tags if m.get("name")}

                if self.model_name not in installed:
                    logger.info(f"Model not present locally, pulling: {self.model_name}")
                    for attempt in range(1, self.load_retry_count + 1):
                        try:
                            pull_resp = client.post(
                                f"{self.ollama_base_url}/api/pull",
                                json={"name": self.model_name, "stream": False},
                            )
                            pull_resp.raise_for_status()
                            break
                        except Exception:
                            if attempt == self.load_retry_count:
                                raise
                            logger.warning(
                                "Ollama model pull attempt %s/%s failed; retrying in %ss",
                                attempt,
                                self.load_retry_count,
                                self.load_retry_delay_seconds,
                            )
                            time.sleep(self.load_retry_delay_seconds)
                    logger.info(f"Model pull completed: {self.model_name}")

            # Keep compatibility with existing route checks.
            self.model = {"runtime": "ollama", "model": self.model_name}
            self.tokenizer = {"runtime": "ollama"}

            self._status = ModelStatus.READY
            logger.info("Ollama Granite runtime ready")
            return True

        except Exception as e:
            self._status = ModelStatus.ERROR
            self._error_message = str(e)
            logger.exception(f"Failed to initialize Ollama Granite runtime: {e}")
            return False

    def get_load_status(self) -> Dict[str, Any]:
        """
        Get current model load status, memory usage, and any error.
        
        Returns:
            Dict with model_status, last_error, memory_usage_mb
        """
        status = self._status.value
        error = self._error_message

        # Get memory usage (safe to call outside lock)
        try:
            memory_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        except Exception as e:
            logger.warning(f"Could not read memory usage: {e}")
            memory_mb = None

        return {
            "model_status": status,
            "model_ready": status == "ready",
            "last_error": error,
            "model_loaded": self.model is not None and self.tokenizer is not None,
            "memory_usage_mb": round(memory_mb, 1) if memory_mb else None
        }

    
    async def _generate_via_ollama(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        do_sample: Optional[bool] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """Generate text via Ollama local HTTP API."""
        generation_max_tokens = min(max_tokens or self.max_new_tokens, 512)
        generation_temperature = self.temperature if temperature is None else temperature

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": generation_max_tokens,
                "temperature": generation_temperature,
                "top_p": top_p if top_p is not None else 1.0,
                "seed": 0 if do_sample is False else None,
            },
        }
        if response_format:
            payload["format"] = response_format

        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        generated = data.get("response", "")
        if not generated:
            raise RuntimeError("Empty response from Ollama /api/generate")
        return generated.strip()

    async def generate_experiment(
        self, prompt: str, max_tokens: int = 512, temperature: float = 0.0,
        top_p: float = 1.0, do_sample: bool = False,
    ) -> Dict[str, Any]:
        """Generate one bounded local experiment response without rebuilding context."""
        if not self.get_load_status()["model_ready"]:
            raise RuntimeError("Granite model is not ready.")
        if len(prompt) > self.max_input_chars:
            raise RuntimeError(f"Experiment prompt exceeds Granite input budget ({self.max_input_chars} chars).")
        started = time.monotonic()
        async with self._lock:
            raw_response = await asyncio.wait_for(
                self._generate_via_ollama(prompt, max_tokens, temperature, top_p, do_sample),
                timeout=self.timeout_seconds,
            )
        return {
            "raw_response": raw_response,
            "generation": {"temperature": temperature, "top_p": top_p, "max_tokens": min(max_tokens, 512), "do_sample": do_sample, "input_characters": len(prompt), "duration_seconds": time.monotonic() - started},
        }

    async def generate_analysis(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate analysis using Granite model with retrieved context.
        
        Args:
            query: Research question or analytical query
            context_chunks: List of retrieved document chunks with metadata
            max_tokens: Maximum tokens to generate (default from config)
            temperature: Sampling temperature (default from config)
            
        Returns:
            Dict containing analysis text, metadata, and timing info
            
        Raises:
            RuntimeError if model not loaded or loading in progress
        """
        status_info = self.get_load_status()
        
        if status_info["model_status"] == "not_loaded":
            raise RuntimeError("Granite model not loaded. Call /api/granite/load-model to load it.")
        elif status_info["model_status"] == "loading":
            raise RuntimeError("Granite model is still loading. Check /api/granite/load-status and retry.")
        elif status_info["model_status"] == "error":
            raise RuntimeError(f"Granite model load failed: {status_info.get('last_error', 'unknown error')}")
        
        if self.model is None:
            raise RuntimeError("Granite model not loaded.")
        
        start_time = datetime.now()
        
        prompt = self._build_prompt(query, context_chunks)

        async with self._lock:
            logger.info(f"Generating response for query: {query[:100]}...")
            try:
                generated_text = await asyncio.wait_for(
                    self._generate_via_ollama(
                        prompt,
                        max_tokens,
                        temperature,
                    ),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"Granite inference timed out after {self.timeout_seconds}s"
                ) from exc
        
        end_time = datetime.now()
        inference_time = (end_time - start_time).total_seconds()
        
        logger.info(f"✓ Generated {len(generated_text)} chars in {inference_time:.2f}s")
        
        return {
            "analysis": generated_text,
            "query": query,
            "num_context_chunks": len(context_chunks),
            "inference_time_seconds": inference_time,
            "model": self.model_name,
            "timestamp": end_time.isoformat(),
            "context_chunk_ids": [chunk.get("id") for chunk in context_chunks]
        }
    
    def _build_prompt(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        Build prompt with research query and retrieved context chunks.
        
        Args:
            query: User's research question
            context_chunks: Retrieved document chunks with citations
            
        Returns:
            Formatted prompt string
        """
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            if chunk.get('provenance') or chunk.get('catalogue_metadata'):
                context_parts.append(format_granite_source_block(i, chunk))
                continue

            text = chunk.get("text", "")
            citation = chunk.get("citation", f"Source {i}")
            context_parts.append(f"[{i}] {text}\n   Citation: {citation}")
        
        context_text = "\n\n".join(context_parts)
        
        prompt = f"""You are an archival research analyst specialising in design history. Answer the question below using only the sources provided.

    Research scope: Royal College of Art Department of Design Research (DDR), 1965–1985.

Rules:
- Write 150–250 words maximum.
- Be specific: quote or paraphrase exact details from the sources rather than restating generic themes.
- Use short paragraphs or bullet points.
- Where sources differ or contradict each other, name the tension explicitly.
- Cite inline with [1], [2], etc. only when the source directly supports the claim. Do not invent citations.
- Treat any ARCHIVE / CATALOGUE METADATA block as descriptive catalogue context about the object, not as quoted source-document language.
- Distinguish clearly between catalogue description, source-document evidence, and your own inference.
- Do not open with "Based on the sources" or any similar preamble. Start with substance.
- If the sources do not contain enough information to answer, say so in one sentence.

SOURCES:
{context_text}

QUESTION: {query}

ANSWER:
"""

        if len(prompt) > self.max_input_chars:
            return prompt[:self.max_input_chars]

        return prompt
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model and its status.
        
        Returns:
            Dict with model metadata and current loading status
        """
        status_info = self.get_load_status()
        
        return {
            "model_name": self.model_name,
            "device": self.device,
            "loaded": self.model is not None,
            "model_status": status_info["model_status"],
            "max_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "quantized": "q4_gguf_via_ollama",
            "memory_usage_mb": status_info["memory_usage_mb"],
            "last_error": status_info["last_error"],
            "runtime": "ollama",
            "base_url": self.ollama_base_url,
        }

    def unload_model(self) -> None:
        """Reset service-side loaded state; Ollama process keeps model lifecycle."""
        self.model = None
        self.tokenizer = None
        self._status = ModelStatus.NOT_LOADED
        self._error_message = None


# Global instance
_granite_service: Optional[GraniteService] = None


def get_granite_service() -> GraniteService:
    """Get or create the global Granite service instance."""
    global _granite_service
    if _granite_service is None:
        _granite_service = GraniteService()
    return _granite_service


async def initialize_granite():
    """Initialize Granite service on application startup."""
    logger.info("Initializing Granite service...")
    service = get_granite_service()
    success = await asyncio.to_thread(service.load_model)
    if success:
        logger.info("✓ Granite service ready")
    else:
        logger.warning("⚠ Granite service failed to initialize - inference will not be available")
    return success
