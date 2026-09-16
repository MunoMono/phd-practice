"""Build a versioned BGE-M3 embedding set and immutable UMAP projection.

The runner only accepts a recorded approved readiness review and never updates
the legacy 384-dimensional document_chunks.embedding_vector column.
"""
import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime

import numpy as np
from sqlalchemy import text

from app.core.database import LocalSessionLocal

MODEL_NAME = "BAAI/bge-m3"
VECTOR_DIMENSIONS = 1024
NORMALISATION_CHUNKING_VERSION = "document_chunks-source-text-v1"
BATCH_SIZE = 4


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def load_approved_review(db):
    row = db.execute(text("""
        SELECT corpus_release, source_scope, embedding_model, model_revision_or_checksum,
               vector_dimensions, normalisation_chunking_version, reviewed_by
        FROM embedding_readiness_reviews
        WHERE status = 'approved'
        ORDER BY reviewed_at DESC, created_at DESC
        LIMIT 1
    """)).mappings().first()
    if not row:
        raise RuntimeError("No approved embedding readiness review exists")
    if row["embedding_model"] != MODEL_NAME:
        raise RuntimeError(f"Approved model is {row['embedding_model']}, not {MODEL_NAME}")
    if row["vector_dimensions"] != VECTOR_DIMENSIONS:
        raise RuntimeError("Approved vector dimensions do not match BGE-M3")
    return row


def load_scope(db):
    return db.execute(text("""
                SELECT dc.chunk_id, dc.document_id, dc.chunk_text
                FROM document_chunks dc
                JOIN documents d ON d.document_id = dc.document_id
                WHERE dc.chunk_id IS NOT NULL
                    AND d.pid IS NOT NULL
          AND NULLIF(BTRIM(chunk_text), '') IS NOT NULL
                ORDER BY dc.document_id, dc.chunk_index NULLS LAST, dc.chunk_id
    """)).mappings().all()


def load_exclusion_counts(db):
        return db.execute(text("""
                SELECT COUNT(*) AS excluded_orphaned_source_chunks
                FROM document_chunks dc
                WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE d.document_id = dc.document_id AND d.pid IS NOT NULL)
        """)).mappings().first()


def model_checksum(model) -> str:
    digest = hashlib.sha256()
    for name, parameter in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(parameter.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def build_embeddings(db, dry_run: bool) -> str:
    review = load_approved_review(db)
    rows = load_scope(db)
    exclusions = load_exclusion_counts(db)
    manifest = "\n".join(f"{row['chunk_id']}:{sha256(row['chunk_text'])}" for row in rows)
    manifest_hash = sha256(manifest)
    if dry_run:
        print(json.dumps({"eligible_chunks": len(rows), "excluded_orphaned_source_chunks": exclusions["excluded_orphaned_source_chunks"], "input_manifest_sha256": manifest_hash}, indent=2))
        return ""

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
    from huggingface_hub import HfApi
    revision = HfApi().model_info(MODEL_NAME).sha
    checksum = model_checksum(model)
    if review["model_revision_or_checksum"] != revision:
        raise RuntimeError("Approved model revision/checksum does not match the downloaded model")

    set_id = f"bge-m3-{manifest_hash[:12]}-{checksum[:12]}"
    existing = db.execute(text("SELECT status FROM semantic_embedding_sets WHERE embedding_set_id = :set_id"), {"set_id": set_id}).scalar()
    if existing == "completed":
        print(f"Embedding set already completed: {set_id}")
        return set_id
    if not existing:
        db.execute(text("""
            INSERT INTO semantic_embedding_sets (
                embedding_set_id, status, corpus_release, source_scope, model_name, model_revision,
                model_checksum_sha256, vector_dimensions, normalisation_chunking_version, input_manifest_sha256
            ) VALUES (:set_id, 'running', :corpus_release, :source_scope, :model_name, :revision,
                :checksum, :dimensions, :normalisation_version, :manifest_hash)
        """), {"set_id": set_id, "corpus_release": review["corpus_release"], "source_scope": review["source_scope"], "model_name": MODEL_NAME, "revision": revision, "checksum": checksum, "dimensions": VECTOR_DIMENSIONS, "normalisation_version": NORMALISATION_CHUNKING_VERSION, "manifest_hash": manifest_hash})
        db.commit()
    else:
        db.execute(text("""
            UPDATE semantic_embedding_sets
            SET status = 'running', failure_reason = NULL
            WHERE embedding_set_id = :set_id
        """), {"set_id": set_id})
        db.commit()

    persisted_rows = db.execute(text("""
        SELECT chunk_id, text_fingerprint_sha256
        FROM semantic_chunk_embeddings
        WHERE embedding_set_id = :set_id AND status = 'embedded'
    """), {"set_id": set_id}).mappings().all()
    persisted_fingerprints = {
        row["chunk_id"]: row["text_fingerprint_sha256"]
        for row in persisted_rows
    }
    pending_rows = [
        row for row in rows
        if persisted_fingerprints.get(row["chunk_id"]) != sha256(row["chunk_text"])
    ]
    print(f"Reusing {len(rows) - len(pending_rows)}/{len(rows)} persisted embeddings", flush=True)

    try:
        for start in range(0, len(pending_rows), BATCH_SIZE):
            batch = pending_rows[start:start + BATCH_SIZE]
            vectors = model.encode([row["chunk_text"] for row in batch], batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
            for row, vector in zip(batch, vectors):
                vector = np.asarray(vector, dtype=float)
                if vector.shape != (VECTOR_DIMENSIONS,) or not np.isfinite(vector).all():
                    db.execute(text("""INSERT INTO semantic_chunk_embeddings (embedding_set_id, chunk_id, document_id, text_fingerprint_sha256, status, failure_reason)
                        VALUES (:set_id, :chunk_id, :document_id, :fingerprint, 'failed', :failure)
                        ON CONFLICT (embedding_set_id, chunk_id) DO UPDATE SET status = EXCLUDED.status, failure_reason = EXCLUDED.failure_reason"""), {"set_id": set_id, "chunk_id": row["chunk_id"], "document_id": row["document_id"], "fingerprint": sha256(row["chunk_text"]), "failure": "Invalid vector dimensions or non-finite values"})
                    continue
                db.execute(text("""INSERT INTO semantic_chunk_embeddings (embedding_set_id, chunk_id, document_id, text_fingerprint_sha256, status, embedding)
                    VALUES (:set_id, :chunk_id, :document_id, :fingerprint, 'embedded', CAST(:embedding AS vector))
                    ON CONFLICT (embedding_set_id, chunk_id) DO UPDATE SET status = EXCLUDED.status, embedding = EXCLUDED.embedding, failure_reason = NULL"""), {"set_id": set_id, "chunk_id": row["chunk_id"], "document_id": row["document_id"], "fingerprint": sha256(row["chunk_text"]), "embedding": vector_literal(vector.tolist())})
            db.commit()
            print(f"Embedded {len(rows) - len(pending_rows) + min(start + BATCH_SIZE, len(pending_rows))}/{len(rows)} chunks", flush=True)
        status_counts = db.execute(text("""
            SELECT status, COUNT(*) AS count
            FROM semantic_chunk_embeddings
            WHERE embedding_set_id = :set_id
            GROUP BY status
        """), {"set_id": set_id}).mappings().all()
        counts_by_status = {row["status"]: row["count"] for row in status_counts}
        coverage = {"eligible": len(rows), "attempted": len(persisted_fingerprints) + len(pending_rows), "embedded": counts_by_status.get("embedded", 0), "failed": counts_by_status.get("failed", 0), "excluded": int(exclusions["excluded_orphaned_source_chunks"] or 0), "exclusion_reason": "Chunks without a PID-backed document registry record are excluded because Atlas points must reopen their source provenance."}
        db.execute(text("UPDATE semantic_embedding_sets SET status = 'completed', coverage_json = CAST(:coverage AS jsonb), completed_at = :completed_at WHERE embedding_set_id = :set_id"), {"set_id": set_id, "coverage": json.dumps(coverage), "completed_at": datetime.utcnow()})
        db.commit()
        return set_id
    except Exception as exc:
        db.rollback()
        db.execute(text("UPDATE semantic_embedding_sets SET status = 'failed', failure_reason = :reason WHERE embedding_set_id = :set_id"), {"set_id": set_id, "reason": str(exc)})
        db.commit()
        raise


def build_projection(db, embedding_set_id: str, dimensions: int):
    from umap import UMAP
    import umap

    rows = db.execute(text("""
        SELECT chunk_id, embedding::text AS embedding
        FROM semantic_chunk_embeddings
        WHERE embedding_set_id = :set_id AND status = 'embedded'
        ORDER BY chunk_id
    """), {"set_id": embedding_set_id}).mappings().all()
    if len(rows) < 3:
        raise RuntimeError("At least three valid embeddings are required for UMAP")
    ordering_hash = sha256("\n".join(row["chunk_id"] for row in rows))
    projection_id = f"umap-{embedding_set_id}-{dimensions}d-{ordering_hash[:12]}"
    if db.execute(text("SELECT status FROM semantic_atlas_projections WHERE projection_id = :projection_id"), {"projection_id": projection_id}).scalar() == "completed":
        print(f"Projection already completed: {projection_id}")
        return projection_id
    params = {"n_neighbors": min(15, len(rows) - 1), "n_components": dimensions, "metric": "cosine"}
    db.execute(text("""INSERT INTO semantic_atlas_projections (projection_id, embedding_set_id, status, algorithm, library_version, random_seed, parameters_json, input_count, input_ordering_sha256, numerical_tolerance)
        VALUES (:projection_id, :set_id, 'running', 'umap', :library_version, 42, CAST(:parameters AS jsonb), :input_count, :ordering_hash, 0.000001)
        ON CONFLICT (projection_id) DO UPDATE SET status = 'running', failure_reason = NULL"""), {"projection_id": projection_id, "set_id": embedding_set_id, "library_version": getattr(umap, "__version__", "unknown"), "parameters": json.dumps(params), "input_count": len(rows), "ordering_hash": ordering_hash})
    db.commit()
    try:
        vectors = np.array([json.loads(row["embedding"]) for row in rows], dtype=float)
        coordinates = UMAP(**params, random_state=42).fit_transform(vectors)
        for row, coordinate in zip(rows, coordinates):
            db.execute(text("""INSERT INTO semantic_atlas_projection_points (projection_id, chunk_id, x, y, z)
                VALUES (:projection_id, :chunk_id, :x, :y, :z)
                ON CONFLICT (projection_id, chunk_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y, z = EXCLUDED.z"""), {"projection_id": projection_id, "chunk_id": row["chunk_id"], "x": float(coordinate[0]), "y": float(coordinate[1]), "z": float(coordinate[2]) if dimensions == 3 else None})
        db.execute(text("UPDATE semantic_atlas_projections SET status = 'completed', completed_at = :completed_at WHERE projection_id = :projection_id"), {"projection_id": projection_id, "completed_at": datetime.utcnow()})
        db.commit()
        return projection_id
    except Exception as exc:
        db.rollback()
        db.execute(text("UPDATE semantic_atlas_projections SET status = 'failed', failure_reason = :reason WHERE projection_id = :projection_id"), {"projection_id": projection_id, "reason": str(exc)})
        db.commit()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--projection-only", action="store_true")
    parser.add_argument("--embedding-set-id")
    parser.add_argument("--dimensions", type=int, choices=(2, 3), default=2)
    args = parser.parse_args()
    db = LocalSessionLocal()
    try:
        set_id = args.embedding_set_id if args.projection_only else build_embeddings(db, args.dry_run)
        if set_id and not args.dry_run:
            projection_id = build_projection(db, set_id, args.dimensions)
            print(json.dumps({"embedding_set_id": set_id, "projection_id": projection_id}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()