import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.granite_service import GraniteService, ModelStatus


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": "fixture response", "done": True, "done_reason": "stop"}


class FakeAsyncClient:
    timeout = None

    def __init__(self, timeout):
        type(self).timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *_args, **_kwargs):
        return FakeResponse()


class GraniteServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_uses_600_second_read_and_wrapper_timeout(self):
        with patch.dict(os.environ, {"GRANITE_TIMEOUT_SECONDS": "600"}):
            service = GraniteService()
        service.model = {"runtime": "ollama"}
        service.tokenizer = {"runtime": "ollama"}
        service._status = ModelStatus.READY

        with patch("app.services.granite_service.httpx.AsyncClient", FakeAsyncClient):
            response = await service.generate_experiment("fixture prompt")

        self.assertEqual(service.timeout_seconds, 600)
        self.assertEqual(FakeAsyncClient.timeout.connect, 10.0)
        self.assertEqual(FakeAsyncClient.timeout.read, 600)
        self.assertEqual(FakeAsyncClient.timeout.write, 30.0)
        self.assertEqual(FakeAsyncClient.timeout.pool, 30.0)
        self.assertEqual(response["generation"]["granite_timeout_seconds"], 600)

    async def test_v13_capacity_and_timeout_are_preserved_in_ollama_metadata(self):
        with patch.dict(os.environ, {"GRANITE_TIMEOUT_SECONDS": "1200"}):
            service = GraniteService()
        service.model = {"runtime": "ollama"}
        service.tokenizer = {"runtime": "ollama"}
        service._status = ModelStatus.READY

        with patch("app.services.granite_service.httpx.AsyncClient", FakeAsyncClient):
            response = await service.generate_experiment("fixture prompt", max_tokens=1000)

        self.assertEqual(service.timeout_seconds, 1200)
        self.assertEqual(FakeAsyncClient.timeout.read, 1200)
        self.assertEqual(response["generation"]["max_tokens"], 1000)
        self.assertEqual(response["generation"]["granite_timeout_seconds"], 1200)

    async def test_v14_transport_accepts_1500_tokens_without_changing_timeout(self):
        with patch.dict(os.environ, {"GRANITE_TIMEOUT_SECONDS": "1200"}):
            service = GraniteService()
        service.model = {"runtime": "ollama"}
        service.tokenizer = {"runtime": "ollama"}
        service._status = ModelStatus.READY

        with patch("app.services.granite_service.httpx.AsyncClient", FakeAsyncClient):
            response = await service.generate_experiment("fixture prompt", max_tokens=1500)

        self.assertEqual(service.timeout_seconds, 1200)
        self.assertEqual(response["generation"]["max_tokens"], 1500)


if __name__ == "__main__":
    unittest.main()