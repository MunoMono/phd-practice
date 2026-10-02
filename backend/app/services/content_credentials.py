from __future__ import annotations

import html
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import settings


class ContentCredentialsUnavailable(RuntimeError):
    """Raised when research-grade Content Credentials have not been provisioned."""


def build_query_run_manifest(run: Any) -> dict[str, Any]:
    ingredients = []
    for chunk in run.chunks or []:
        metadata = chunk.source_metadata_json or {}
        ingredients.append({
            "title": metadata.get("title") or chunk.document_id or chunk.chunk_id,
            "relationship": "inputTo",
            "description": "Archived source passage retained for this research output.",
        })

    return {
        "claim_generator_info": [{"name": "Innovation Design research exporter", "version": "1.0"}],
        "format": "image/svg+xml",
        "title": f"Research retrieval trail {run.query_id}",
        "ingredients": ingredients,
        "assertions": [{
            "label": "c2pa.actions",
            "data": {"actions": [{
                "action": "c2pa.created",
                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                "description": "A research retrieval-trail memo generated from a retained query run.",
            }]},
        }],
    }


def build_query_run_svg(run: Any) -> str:
    lines = [
        "Research retrieval trail",
        f"Query ID: {run.query_id}",
        f"Created: {run.created_at.isoformat() if run.created_at else 'not retained'}",
        f"Model: {run.model or 'not retained'}",
        f"Retained source passages: {len(run.chunks or [])}",
        f"Query: {run.prompt}",
        f"Answer: {run.response or 'No answer was returned.'}",
        f"Caveats: {run.caveats or run.failure_reason or 'None recorded.'}",
    ]
    rows = "".join(
        f'<text x="36" y="{44 + index * 28}" font-family="sans-serif" font-size="16">{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    height = 72 + len(lines) * 28
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">{rows}</svg>'


def _load_research_signer() -> tuple[Any, Any]:
    if not settings.C2PA_SIGNING_ENABLED or settings.C2PA_SIGNING_MODE != "research_local":
        raise ContentCredentialsUnavailable("Research Content Credentials signing is not enabled.")

    certificate_path = Path(settings.C2PA_SIGNING_CERTIFICATE_PATH)
    key_path = Path(settings.C2PA_SIGNING_KEY_PATH)
    if not certificate_path.is_file() or not key_path.is_file():
        raise ContentCredentialsUnavailable("Research signing certificate or key is not installed.")

    try:
        import c2pa
    except ImportError as error:
        raise ContentCredentialsUnavailable("C2PA SDK is not installed.") from error

    certificate_chain = certificate_path.read_text(encoding="utf-8")
    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(),
        password=settings.C2PA_SIGNING_KEY_PASSPHRASE.encode() or None,
    )

    def sign(data: bytes) -> bytes:
        return private_key.sign(data, ec.ECDSA(hashes.SHA256()))

    return c2pa, c2pa.Signer.from_callback(sign, c2pa.C2paSigningAlg.ES256, certificate_chain)


def sign_query_run_svg(run: Any) -> tuple[bytes, dict[str, Any]]:
    c2pa, signer = _load_research_signer()
    with tempfile.TemporaryDirectory(prefix="c2pa-query-run-") as temporary_directory:
        source_path = Path(temporary_directory) / "source.svg"
        destination_path = Path(temporary_directory) / "research-retrieval-trail.svg"
        source_path.write_text(build_query_run_svg(run), encoding="utf-8")
        with c2pa.Context() as context, signer, c2pa.Builder(build_query_run_manifest(run), context) as builder:
            builder.sign_file(source_path, destination_path, signer)
            with destination_path.open("rb") as signed_file, c2pa.Reader("image/svg+xml", signed_file, context=context) as reader:
                validation = json.loads(reader.json())
        return destination_path.read_bytes(), validation


def signed_asset_record(asset: bytes, validation: dict[str, Any]) -> dict[str, Any]:
    manifests = validation.get("manifests") or {}
    active_manifest = validation.get("active_manifest") or {}
    manifest = active_manifest
    if not manifest and isinstance(manifests, dict) and manifests:
        manifest = next(iter(manifests.values()))
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":")) if manifest else ""
    return {
        "asset_sha256": hashlib.sha256(asset).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_json.encode("utf-8")).hexdigest() if manifest_json else None,
        "validation_state": validation.get("validation_state", "Unknown"),
        "validation_status_json": validation.get("validation_status") or [],
        "signer_subject": (manifest.get("signature_info") or {}).get("issuer") if isinstance(manifest, dict) else None,
    }