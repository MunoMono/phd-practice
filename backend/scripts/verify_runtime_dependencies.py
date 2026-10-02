#!/usr/bin/env python3
"""Validate the backend's resolved GraphQL runtime during image builds."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    import strawberry  # noqa: F401
    from graphql.execution import ExecutionContext  # noqa: F401
    from app.main import app

    if app is None:
        raise RuntimeError("FastAPI application did not initialize")


if __name__ == "__main__":
    main()