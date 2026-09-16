#!/usr/bin/env python3
"""Create the local Turin authority graph snapshot from persisted data only."""

from __future__ import annotations

import json

from app.core.database import LocalSessionLocal
from app.services.turin_authority_graph_materializer import TurinAuthorityGraphMaterializer


if __name__ == "__main__":
    database = LocalSessionLocal()
    try:
        result = TurinAuthorityGraphMaterializer().materialize(database, "corpus_f40d78dbce52")
        database.commit()
        print(json.dumps(result, sort_keys=True))
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()