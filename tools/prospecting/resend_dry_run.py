#!/usr/bin/env python3
"""Imprime o dry-run Growth/Resend P0; nunca envia nem altera dados."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.growth.resend_p0 import build_dry_run  # noqa: E402


def main() -> int:
    with SessionLocal() as db:
        summary = build_dry_run(db)
    print(json.dumps(summary.as_dict(), ensure_ascii=False, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
