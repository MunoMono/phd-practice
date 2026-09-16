import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inference_service import InferenceService, ModelStatus


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": '{"answer":"fixture"}', "done": True, "done_reason": "stop"}


class FakeAsyncClient:
    request = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, _url, json):
        type(self).request = json
        return FakeResponse()


class InferenceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_runtime_uses_exact_qwen_model_without_fallback(self):
        with patch.dict(os.environ, {"TURIN_INFERENCE_PROVIDER": "ollama", "TURIN_MODEL": "qwen3:8b-q4_K_M", "TURIN_TIMEOUT_SECONDS": "600", "TURIN_QWEN_NUM_CTX": "16384", "TURIN_MAX_INPUT_TOKENS": "12000", "TURIN_QWEN_SOURCE_ANALYSIS_MAX_TOKENS": "1000", "TURIN_QWEN_CROSS_SOURCE_MAX_TOKENS": "1000", "TURIN_QWEN_FINAL_SYNTHESIS_MAX_TOKENS": "768", "TURIN_QWEN_TEMPERATURE": "0.2"}, clear=False):
            service = InferenceService()
        service.model = {"runtime": "ollama"}
        service.tokenizer = {"runtime": "ollama"}
        service._status = ModelStatus.READY

        with patch("app.services.inference_service.httpx.AsyncClient", FakeAsyncClient):
            response = await service.generate_experiment("fixture prompt", max_tokens=service.final_synthesis_max_output_tokens, response_schema={"type": "object"})

        self.assertEqual(service.model_name, "qwen3:8b-q4_K_M")
        self.assertEqual(FakeAsyncClient.request["model"], "qwen3:8b-q4_K_M")
        self.assertFalse(FakeAsyncClient.request["think"])
        self.assertEqual(FakeAsyncClient.request["options"]["num_ctx"], 16384)
        self.assertEqual(FakeAsyncClient.request["options"]["num_predict"], 768)
        self.assertEqual(response["generation"]["num_ctx"], 16384)
        self.assertTrue(response["generation"]["done"])
        self.assertEqual(response["generation"]["done_reason"], "stop")

    def test_model_info_exposes_unambiguous_stage_aware_settings(self):
        with patch.dict(os.environ, {"TURIN_INFERENCE_PROVIDER": "ollama", "TURIN_MODEL": "qwen3:8b-q4_K_M", "TURIN_QWEN_NUM_CTX": "16384", "TURIN_QWEN_SOURCE_ANALYSIS_MAX_TOKENS": "1000", "TURIN_QWEN_CROSS_SOURCE_MAX_TOKENS": "1000", "TURIN_QWEN_FINAL_SYNTHESIS_MAX_TOKENS": "768", "TURIN_QWEN_TEMPERATURE": "0.2"}, clear=False):
            info = InferenceService().get_model_info()
        self.assertEqual(info["model"], "qwen3:8b-q4_K_M")
        self.assertEqual(info["context_window_tokens"], 16384)
        self.assertEqual(info["source_analysis_max_output_tokens"], 1000)
        self.assertEqual(info["cross_source_max_output_tokens"], 1000)
        self.assertEqual(info["final_synthesis_max_output_tokens"], 768)
        self.assertEqual(info["temperature"], 0.2)
        self.assertNotIn("max_tokens", info)

    def test_unavailable_runtime_reports_clear_status(self):
        service = InferenceService()
        self.assertFalse(service.get_load_status()["model_ready"])
        self.assertEqual(service.get_load_status()["model_status"], "not_loaded")

    def test_disabled_runtime_reports_inference_unavailable(self):
        with patch.dict(os.environ, {"TURIN_INFERENCE_PROVIDER": "disabled"}, clear=True):
            service = InferenceService()
            self.assertFalse(service.load_model())
        self.assertEqual(service.get_load_status()["model_status"], "disabled")
        self.assertEqual(service.get_model_info()["display_name"], "Inference unavailable")


if __name__ == "__main__":
    unittest.main()
