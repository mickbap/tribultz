from __future__ import annotations

import argparse
import json
from uuid import uuid4

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No side effects; return fake job ids.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-id", required=True)
    args = parser.parse_args()

    # MVP: no “intelligence” here. Service classifies intent.
    # This entrypoint exists mainly for local/dev wiring & parity with executor.

    if args.dry_run:
        job_id = str(uuid4())
        out = {
            "response_markdown": f"✅ Validation started.\n\nJob: `{job_id}`",
            "evidence": [
                {"type": "job", "job_id": job_id, "href": f"/jobs/{job_id}", "label": "Validation job"}
            ],
        }
        print(json.dumps(out))
        return 0

    raise SystemExit("Wire real crew execution + tools; for now use --dry-run.")

if __name__ == "__main__":
    raise SystemExit(main())
