import unittest
from unittest.mock import patch

from pydantic import ValidationError
from fastapi import HTTPException

from app.api.routes import viz
from app.api.routes.viz import AtlasCoverageMissingnessRequest


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class MappingResult:
    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value


class RepresentedSourceDatabase:
    def execute(self, *_args, **_kwargs):
        if not hasattr(self, "calls"):
            self.calls = 0
        self.calls += 1
        if self.calls == 1:
            return MappingResult({"document_id": "document-1", "pid": "pid-1", "title": "Known source"})
        return ScalarResult(True)

    def close(self):
        pass


class AtlasCoverageMissingnessRequestTests(unittest.TestCase):
    def test_requires_a_durable_source_identifier(self):
        with self.assertRaises(ValidationError):
            AtlasCoverageMissingnessRequest()

    def test_accepts_a_known_document_and_projection_identifier(self):
        request = AtlasCoverageMissingnessRequest(document_id="document-1", projection_id="atlas-1")
        self.assertEqual(request.document_id, "document-1")
        self.assertEqual(request.projection_id, "atlas-1")

    def test_represented_source_is_rejected_as_a_computational_coverage_gap(self):
        with patch.object(viz, "LocalSessionLocal", return_value=RepresentedSourceDatabase()), patch.object(viz, "_get_completed_semantic_atlas_projection", return_value={"projection_id": "atlas-1"}):
            with self.assertRaises(HTTPException) as context:
                import asyncio
                asyncio.run(viz.create_atlas_coverage_missingness(AtlasCoverageMissingnessRequest(document_id="document-1")))
        self.assertEqual(context.exception.status_code, 409)