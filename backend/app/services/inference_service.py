"""Provider-neutral inference service for the active Turin runtime."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import psutil

from app.services.metadata_roles import format_inference_source_block

logger = logging.getLogger(__name__)

OLLAMA_PROVIDERS = {"ollama", "remote_ollama"}


class InferenceTimeoutError(RuntimeError):
    def __init__(self, stage: str, timeout_seconds: int, metrics: Dict[str, Any]):
        super().__init__(f"Qwen {stage} exceeded the configured inference time limit.")
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        self.metrics = metrics


class ModelStatus(Enum):
    """Model loading status states."""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    READY = "ready"
    DISABLED = "disabled"
    ERROR = "error"


class DedicatedQwenProvider:
    """Configuration hook for a future private Qwen GPU endpoint."""

    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    def validate_configuration(self) -> None:
        if not self.endpoint or not self.model:
            raise RuntimeError(
                "Dedicated Qwen endpoint and model must be configured."
            )


class InferenceService:
    """Active Turin inference service backed by the configured provider."""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.provider = os.getenv("TURIN_INFERENCE_PROVIDER", "disabled").strip().lower()
        self.ollama_model_name = os.getenv("TURIN_MODEL", "qwen3:8b-q4_K_M")
        self.dedicated_qwen_provider = DedicatedQwenProvider(
            os.getenv("TURIN_DEDICATED_QWEN_ENDPOINT", ""),
            os.getenv("TURIN_DEDICATED_QWEN_MODEL", ""),
        )
        self.model_name = (
            self.dedicated_qwen_provider.model
            if self.provider == "dedicated_qwen"
            else (self.ollama_model_name if self.provider in OLLAMA_PROVIDERS else "inference_unavailable")
        )
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.device = "remote" if self.provider in {"dedicated_qwen", "remote_ollama"} else "cpu"
        self.final_synthesis_max_output_tokens = int(os.getenv("TURIN_QWEN_FINAL_SYNTHESIS_MAX_TOKENS", "768"))
        self.source_analysis_max_output_tokens = int(os.getenv("TURIN_QWEN_SOURCE_ANALYSIS_MAX_TOKENS", "1000"))
        self.cross_source_max_output_tokens = int(os.getenv("TURIN_QWEN_CROSS_SOURCE_MAX_TOKENS", "1000"))
        self.temperature = float(os.getenv("TURIN_QWEN_TEMPERATURE", "0.2"))
        self.qwen_num_ctx = int(os.getenv("TURIN_QWEN_NUM_CTX", "16384"))
        self.max_input_tokens = int(os.getenv("TURIN_MAX_INPUT_TOKENS", "12000"))
        self.timeout_seconds = int(os.getenv("TURIN_TIMEOUT_SECONDS", "600"))
        self.ollama_keep_alive = os.getenv("TURIN_OLLAMA_KEEP_ALIVE", "15m")
        self.load_timeout_seconds = int(os.getenv("OLLAMA_LOAD_TIMEOUT_SECONDS", "600"))
        self.load_retry_count = int(os.getenv("OLLAMA_LOAD_RETRY_COUNT", "3"))
        self.load_retry_delay_seconds = int(os.getenv("OLLAMA_LOAD_RETRY_DELAY_SECONDS", "5"))
        self._lock = asyncio.Lock()

        self._status = ModelStatus.NOT_LOADED
        self._error_message: Optional[str] = None
        
    def load_model(self) -> bool:
        """Validate the configured runtime without generating any inference."""
        try:
            self._status = ModelStatus.LOADING
            self._error_message = None

            if self.provider == "disabled":
                self._status = ModelStatus.DISABLED
                logger.info("Turin inference runtime is disabled")
                return False
            if self.provider == "dedicated_qwen":
                self.dedicated_qwen_provider.validate_configuration()
                self.model = {"runtime": self.provider, "model": self.model_name}
                self.tokenizer = {"runtime": self.provider}
                self._status = ModelStatus.READY
                logger.info("Dedicated Qwen Turin runtime configured model=%s", self.model_name)
                return True
            if self.provider not in OLLAMA_PROVIDERS:
                raise RuntimeError(f"Unsupported Turin inference provider: {self.provider}")

            logger.info("Validating %s Ollama runtime at %s", self.provider, self.ollama_base_url)
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
            self.model = {"runtime": self.provider, "model": self.model_name}
            self.tokenizer = {"runtime": self.provider}

            self._status = ModelStatus.READY
            logger.info("%s Turin runtime ready", self.provider)
            return True

        except Exception as e:
            self._status = ModelStatus.ERROR
            self._error_message = str(e)
            logger.exception(f"Failed to initialize active Turin runtime: {e}")
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

    def check_remote_runtime(self) -> bool:
        """Probe the private remote Ollama endpoint without loading or generating."""
        if self.provider != "remote_ollama":
            return self.get_load_status()["model_ready"]
        try:
            timeout = httpx.Timeout(connect=10.0, read=10.0, write=10.0, pool=10.0)
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.ollama_base_url}/api/tags")
                response.raise_for_status()
                installed = {model.get("name") for model in response.json().get("models", [])}
            if self.model_name not in installed:
                raise RuntimeError(f"Remote Ollama model is unavailable: {self.model_name}")
            return True
        except Exception as exc:
            self._status = ModelStatus.ERROR
            self._error_message = str(exc)
            self.model = None
            self.tokenizer = None
            logger.warning("Remote Ollama runtime probe failed: %s", exc)
            return False

    
    async def _generate_via_ollama(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        do_sample: Optional[bool] = None,
        response_format: Optional[str | Dict[str, Any]] = None,
        stage: str = "unspecified",
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate text via Ollama local HTTP API."""
        generation_max_tokens = min(max_tokens or self.final_synthesis_max_output_tokens, 1500)
        generation_temperature = self.temperature if temperature is None else temperature

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": self.ollama_keep_alive,
            "options": {
                "num_ctx": self.qwen_num_ctx,
                "num_predict": generation_max_tokens,
                "temperature": generation_temperature,
                "top_p": top_p if top_p is not None else 1.0,
                "seed": 0 if do_sample is False else None,
            },
        }
        if response_format:
            payload["format"] = response_format

        request_started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        timeout = httpx.Timeout(connect=10.0, read=timeout_seconds or self.timeout_seconds, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        request_ended_at = datetime.now(timezone.utc)
        data["request_started_at_utc"] = request_started_at.isoformat()
        data["request_ended_at_utc"] = request_ended_at.isoformat()
        data["request_elapsed_ms"] = elapsed_ms
        data["request_stage"] = stage
        data["request_think"] = False
        data["request_keep_alive"] = self.ollama_keep_alive
        logger.info(
            "Ollama call completed stage=%s model=%s think=false start=%s end=%s elapsed_ms=%s prompt_tokens=%s output_tokens=%s eval_duration_ns=%s load_duration_ns=%s prompt_eval_duration_ns=%s done_reason=%s",
            stage, self.model_name, data["request_started_at_utc"], data["request_ended_at_utc"], elapsed_ms,
            data.get("prompt_eval_count"), data.get("eval_count"), data.get("eval_duration"),
            data.get("load_duration"), data.get("prompt_eval_duration"), data.get("done_reason"),
        )

        generated = data.get("response", "")
        if not generated:
            raise RuntimeError("Empty response from Ollama /api/generate")
        return {"raw_response": generated.strip(), "generation": data}

    async def generate_experiment(
        self, prompt: str, max_tokens: int = 512, temperature: Optional[float] = None,
        top_p: float = 1.0, do_sample: bool = False, response_schema: Optional[Dict[str, Any]] = None,
        stage: str = "unspecified",
        timeout_seconds: Optional[int] = None,
        request_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate one bounded experiment response without rebuilding context."""
        if self.provider == "remote_ollama":
            if not self.check_remote_runtime():
                raise RuntimeError("Active Turin remote runtime is not ready.")
        elif not self.get_load_status()["model_ready"]:
            raise RuntimeError("Active Turin model is not ready.")
        if self.provider == "dedicated_qwen":
            raise RuntimeError("Dedicated Qwen transport is not implemented yet.")
        estimated_input_tokens = (len(prompt) + 3) // 4
        if estimated_input_tokens > self.max_input_tokens:
            raise RuntimeError(f"Experiment prompt exceeds active runtime input budget ({self.max_input_tokens} estimated tokens).")
        effective_timeout = timeout_seconds or self.timeout_seconds
        metrics = {
            "stage": stage,
            "provider": self.provider,
            "model": self.model_name,
            "think": False,
            "num_ctx": self.qwen_num_ctx,
            "num_predict": min(max_tokens, 1500),
            "temperature": self.temperature if temperature is None else temperature,
            "timeout_seconds": effective_timeout,
            "prompt_characters": len(prompt),
            "estimated_prompt_tokens": estimated_input_tokens,
            **(request_metrics or {}),
        }
        logger.info("Turin inference call starting %s", metrics)
        started = time.monotonic()
        try:
            async with self._lock:
                generation_result = await asyncio.wait_for(
                    self._generate_via_ollama(prompt, max_tokens, temperature, top_p, do_sample, response_schema, stage, effective_timeout),
                    timeout=effective_timeout,
                )
        except asyncio.TimeoutError as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            logger.error("Turin inference call timed out %s", {**metrics, "elapsed_ms": elapsed_ms})
            raise InferenceTimeoutError(stage, effective_timeout, metrics) from exc
        return {
            "raw_response": generation_result["raw_response"],
            "generation": {
                "temperature": self.temperature if temperature is None else temperature,
                "top_p": top_p,
                "max_tokens": min(max_tokens, 1500),
                "do_sample": do_sample,
                "runtime_timeout_seconds": self.timeout_seconds,
                "input_characters": len(prompt),
                "estimated_input_tokens": estimated_input_tokens,
                "num_ctx": self.qwen_num_ctx,
                "think": False,
                "stream": False,
                "keep_alive": self.ollama_keep_alive,
                "duration_seconds": time.monotonic() - started,
                **generation_result["generation"],
            },
        }

    async def generate_analysis(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate analysis using the active Turin model with retrieved context.
        
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
            raise RuntimeError("Active Turin model not loaded. Call /api/runtime/load-model first.")
        elif status_info["model_status"] == "loading":
            raise RuntimeError("Active Turin model is still loading. Check /api/runtime/load-status and retry.")
        elif status_info["model_status"] == "error":
            raise RuntimeError(f"Active Turin model load failed: {status_info.get('last_error', 'unknown error')}")
        
        if self.model is None:
            raise RuntimeError("Active Turin model not loaded.")
        if self.provider == "dedicated_qwen":
            raise RuntimeError("Dedicated Qwen transport is not implemented yet.")
        
        start_time = datetime.now()
        
        prompt = self._build_prompt(query, context_chunks)

        async with self._lock:
            logger.info(f"Generating response for query: {query[:100]}...")
            try:
                generated_text = await asyncio.wait_for(
                    self._generate_via_ollama(prompt, max_tokens, temperature),
                    timeout=self.timeout_seconds,
                )
                generated_text = generated_text["raw_response"]
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"Turin runtime inference timed out after {self.timeout_seconds}s"
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
                context_parts.append(format_inference_source_block(i, chunk))
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

        return prompt
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model and its status.
        
        Returns:
            Dict with model metadata and current loading status
        """
        status_info = self.get_load_status()
        
        if self.provider == "disabled":
            display_name = "Inference unavailable"
        elif self.provider == "dedicated_qwen":
            display_name = "Dedicated Qwen · Remote GPU"
        elif self.provider == "remote_ollama" and self.model_name == "qwen3:8b-q4_K_M":
            display_name = "Qwen3 8B · Q4_K_M · Remote Mac"
        else:
            display_name = "Qwen3 8B · Q4_K_M" if self.model_name == "qwen3:8b-q4_K_M" else self.model_name

        return {
            "model_name": self.model_name,
            "model": self.model_name,
            "display_name": display_name,
            "status": status_info["model_status"],
            "device": self.device,
            "loaded": self.model is not None,
            "model_status": status_info["model_status"],
            "context_window_tokens": self.qwen_num_ctx,
            "source_analysis_max_output_tokens": self.source_analysis_max_output_tokens,
            "cross_source_max_output_tokens": self.cross_source_max_output_tokens,
            "final_synthesis_max_output_tokens": self.final_synthesis_max_output_tokens,
            "max_input_tokens": self.max_input_tokens,
            "num_ctx": self.qwen_num_ctx,
            "temperature": self.temperature,
            "quantized": "none" if self.provider == "disabled" else ("dedicated_remote_runtime" if self.provider == "dedicated_qwen" else "q4_gguf_via_ollama"),
            "memory_usage_mb": status_info["memory_usage_mb"],
            "last_error": status_info["last_error"],
            "runtime": self.provider,
            "runtime_version": "turin-runtime-v2",
            "runtime_protocol": "turin-runtime-v2",
            "base_url": self.dedicated_qwen_provider.endpoint if self.provider == "dedicated_qwen" else (self.ollama_base_url if self.provider in OLLAMA_PROVIDERS else None),
        }

    def unload_model(self) -> None:
        """Reset service-side loaded state; Ollama process keeps model lifecycle."""
        self.model = None
        self.tokenizer = None
        self._status = ModelStatus.NOT_LOADED
        self._error_message = None


# Global instance
_inference_service: Optional[InferenceService] = None


def get_inference_service() -> InferenceService:
    """Get or create the active model-neutral Turin inference service."""
    global _inference_service
    if _inference_service is None:
        _inference_service = InferenceService()
    return _inference_service


async def initialize_inference_service():
    """Initialize the active Turin inference service on application startup."""
    logger.info("Initializing active Turin inference service...")
    service = get_inference_service()
    success = await asyncio.to_thread(service.load_model)
    if success:
        logger.info("Active Turin inference service ready")
    else:
        logger.warning("Active Turin inference service failed to initialize; inference will not be available")
    return success
