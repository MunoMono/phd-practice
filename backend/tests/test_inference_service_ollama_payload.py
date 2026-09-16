import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inference_service import InferenceService
from app.services.turin_evidence_pipeline_service import StagedEvidencePipeline


class FakeResponse:
    headers = {"x-request-id": "dedicated-control"}

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "id": "chatcmpl-diagnostic",
            "model": "future-qwen-model",
            "choices": [{
                "message": {"content": "{\"status\":\"diagnostic_ok\"}"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        }


class OllamaResponse(FakeResponse):
    def json(self):
        return {"response": "{}", "done": True, "done_reason": "stop"}


class DiagnosticOllamaResponse(FakeResponse):
    def json(self):
        return {
            "response": '{"status":"diagnostic_ok"}', "done": True,
            "done_reason": "stop", "prompt_eval_count": 4, "eval_count": 3,
        }


class DiagnosticSchema(BaseModel):
    status: str


class FakeAsyncClient:
    def __init__(self, response=None):
        self.payload = None
        self.response = response or FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    async def post(self, url, json, headers=None):
        self.url = url
        self.headers = headers
        self.payload = json
        return self.response


class FakeOllamaClient:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def get(self, _url):
        return FakeOllamaTagsResponse()


class FakeOllamaTagsResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"models": [{"name": "qwen3:8b-q4_K_M"}]}


class InferencePayloadTests(unittest.TestCase):
    def test_ollama_local_runtime_initializes_from_installed_model_tag(self):
        with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "ollama"}, clear=False), patch("app.services.inference_service.httpx.Client", FakeOllamaClient):
            service = InferenceService()
            self.assertTrue(service.load_model())
        self.assertEqual(service.model, {"runtime": "ollama", "model": "qwen3:8b-q4_K_M"})

    def test_remote_ollama_runtime_uses_private_endpoint(self):
        environment = {
            "TURIN_INFERENCE_PROVIDER": "remote_ollama",
            "OLLAMA_BASE_URL": "http://host.docker.internal:15434",
            "TURIN_MODEL": "qwen3:8b-q4_K_M",
            "TURIN_QWEN_NUM_CTX": "16384",
            "TURIN_QWEN_TEMPERATURE": "0.2",
        }
        with patch.dict("os.environ", environment, clear=False), patch("app.services.inference_service.httpx.Client", FakeOllamaClient):
            service = InferenceService()
            self.assertTrue(service.load_model())
        self.assertEqual(service.model, {"runtime": "remote_ollama", "model": "qwen3:8b-q4_K_M"})
        self.assertEqual(service.device, "remote")
        self.assertEqual(service.get_model_info()["base_url"], "http://host.docker.internal:15434")
        self.assertEqual(service.get_model_info()["display_name"], "Qwen3 8B · Q4_K_M · Remote Mac")
        with patch("app.services.inference_service.httpx.Client", FakeOllamaClient):
            self.assertTrue(service.check_remote_runtime())

    def test_ollama_evidence_generation_explicitly_disables_thinking(self):
        with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "ollama"}, clear=False):
            service = InferenceService()
        client = FakeAsyncClient(OllamaResponse())
        with patch("app.services.inference_service.httpx.AsyncClient", return_value=client):
            asyncio.run(service._generate_via_ollama("neutral fixture", max_tokens=1500, stage="source_analysis"))
        self.assertEqual(client.payload["model"], "qwen3:8b-q4_K_M")
        self.assertFalse(client.payload["think"])
        self.assertFalse(client.payload["stream"])
        self.assertEqual(client.payload["keep_alive"], "15m")

    def test_remote_ollama_staged_generation_needs_remote_health_not_local_model(self):
        environment = {
            "TURIN_INFERENCE_PROVIDER": "remote_ollama",
            "OLLAMA_BASE_URL": "http://host.docker.internal:15434",
            "TURIN_MODEL": "qwen3:8b-q4_K_M",
        }
        with patch.dict("os.environ", environment, clear=False):
            service = InferenceService()
        self.assertIsNone(service.model)
        client = FakeAsyncClient(DiagnosticOllamaResponse())
        raw_artifacts = []

        async def save_raw(stage, artifact):
            raw_artifacts.append((stage, artifact))

        with patch("app.services.inference_service.httpx.Client", FakeOllamaClient), patch(
            "app.services.inference_service.httpx.AsyncClient", return_value=client
        ):
            result, artifact = asyncio.run(
                StagedEvidencePipeline(service)._generate(
                    "source_analysis", "neutral fixture", DiagnosticSchema, 16,
                    on_raw_response=save_raw,
                )
            )
        self.assertEqual(result.status, "diagnostic_ok")
        self.assertEqual(artifact["generation"]["eval_count"], 3)
        self.assertEqual(raw_artifacts[0][0], "source_analysis")
        self.assertEqual(client.payload["model"], "qwen3:8b-q4_K_M")

    def test_local_provider_rejects_experiment_generation_when_unloaded(self):
        with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "ollama"}, clear=False):
            service = InferenceService()
        with self.assertRaisesRegex(RuntimeError, "Active Turin model is not ready"):
            asyncio.run(service.generate_experiment("neutral fixture"))

    def test_remote_ollama_rejects_experiment_generation_when_health_fails(self):
        with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "remote_ollama"}, clear=False):
            service = InferenceService()
        with patch.object(service, "check_remote_runtime", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Active Turin remote runtime is not ready"):
                asyncio.run(service.generate_experiment("neutral fixture"))

    def test_dedicated_qwen_configuration_hook_requires_no_transport_contract(self):
        environment = {
            "TURIN_INFERENCE_PROVIDER": "dedicated_qwen",
            "TURIN_DEDICATED_QWEN_ENDPOINT": "https://qwen.example",
            "TURIN_DEDICATED_QWEN_MODEL": "future-qwen-model",
        }
        with patch.dict("os.environ", environment, clear=False):
            service = InferenceService()
        self.assertTrue(service.load_model())
        self.assertEqual(service.model_name, "future-qwen-model")
        self.assertEqual(service.get_model_info()["base_url"], "https://qwen.example")

    def test_dedicated_qwen_requires_endpoint_and_model(self):
        with patch.dict("os.environ", {"TURIN_INFERENCE_PROVIDER": "dedicated_qwen"}, clear=True):
            self.assertFalse(InferenceService().load_model())

    def test_retired_digitalocean_providers_are_not_runtime_options(self):
        for provider in ("digitalocean_agent", "digitalocean_serverless"):
            with self.subTest(provider=provider), patch.dict(
                "os.environ", {"TURIN_INFERENCE_PROVIDER": provider}, clear=True
            ):
                self.assertFalse(InferenceService().load_model())

    def test_obsolete_digitalocean_environment_variables_are_ignored(self):
        environment = {
            "TURIN_INFERENCE_PROVIDER": "ollama",
            "TURIN_DO_AGENT_API_KEY": "retired",
            "TURIN_DO_INFERENCE_API_KEY": "retired",
        }
        with patch.dict("os.environ", environment, clear=True):
            service = InferenceService()
        self.assertEqual(service.provider, "ollama")
        self.assertFalse(hasattr(service, "do_agent_api_key"))
        self.assertFalse(hasattr(service, "do_inference_api_key"))


if __name__ == "__main__":
    unittest.main()
