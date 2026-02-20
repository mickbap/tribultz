#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path("reports/qa_gates_report.md")

def sh(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None)
        out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
        return p.returncode, out.strip()
    except FileNotFoundError as e:
        return 127, f"Command not found: {cmd[0]} ({e})"

def section(title: str) -> str:
    return f"\n## {title}\n"

def gate_line(name: str, ok: bool) -> str:
    return f"- {'✅' if ok else '❌'} **{name}**\n"

def detect_backend_root() -> Path:
    b = Path("backend")
    return b if b.exists() else Path(".")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "ci"], default="local")
    args = ap.parse_args()

    Path("reports").mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    backend_root = detect_backend_root()

    content: list[str] = [f"# QA Gates Report — Tribultz (Sprint 4)\n\n**Generated:** {ts}\n\n"]

    overall_ok = True

    # Gate: ruff
    content.append(section("Gate: ruff"))
    code, out = sh(["ruff", "check", "."], cwd=backend_root)
    ok = (code == 0)
    overall_ok &= ok
    content.append(gate_line("ruff check .", ok))
    if not ok:
        content.append("\n**Output:**\n```text\n" + out[:8000] + "\n```\n")

    # Gate: pyright (pinned via npx)
    content.append(section("Gate: pyright"))
    code, out = sh(["npx", "--yes", "pyright@1.1.386"], cwd=backend_root)
    ok = (code == 0)
    overall_ok &= ok
    content.append(gate_line("npx pyright@1.1.386", ok))
    if not ok:
        content.append("\n**Output:**\n```text\n" + out[:8000] + "\n```\n")

    # Gate: pytest
    content.append(section("Gate: pytest"))
    code, out = sh(["pytest", "-q"], cwd=backend_root)
    ok = (code == 0)
    overall_ok &= ok
    content.append(gate_line("pytest -q", ok))
    if not ok:
        content.append("\n**Output:**\n```text\n" + out[:8000] + "\n```\n")

    # Gate: contract + security (HTTP) — still pending wiring
    content.append(section("Gate: contract + security (HTTP)"))
    content.append(textwrap.dedent("""
    - ⚠️ **PENDING (needs wiring):** HTTP contract/security probes require:
      - BASE_URL (ex: http://localhost:8000)
      - AUTH_TOKEN (tenant A)
      - AUTH_TOKEN_TENANT_B (tenant B)
      - JOB_ID_TENANT_A (fixture)
      - rate limit policy enabled (login/chat)
    """).strip() + "\n")

    # Gate: frontend build (best-effort local)
    content.append(section("Gate: frontend build"))
    ok_front = True
    msg = "No frontend detected."
    if Path("package-lock.json").exists():
        code, out = sh(["npm", "ci"])
        ok_front &= (code == 0)
        if ok_front:
            code2, out2 = sh(["npm", "run", "build"])
            ok_front &= (code2 == 0)
            msg = (out + "\n" + out2).strip()
        else:
            msg = out
    elif Path("frontend/package-lock.json").exists():
        code, out = sh(["npm", "ci"], cwd=Path("frontend"))
        ok_front &= (code == 0)
        if ok_front:
            code2, out2 = sh(["npm", "run", "build"], cwd=Path("frontend"))
            ok_front &= (code2 == 0)
            msg = (out + "\n" + out2).strip()
        else:
            msg = out
    content.append(gate_line("frontend build (best-effort local)", ok_front))
    if not ok_front:
        content.append("\n**Output:**\n```text\n" + msg[:8000] + "\n```\n")

    # Verdict
    content.append(section("Verdict"))
    if overall_ok:
        content.append("**Status:** ⚠️ *PARTIAL* — core gates OK, HTTP contract/security pending wiring.\n")
        content.append("- Recommendation: **NO-GO** until HTTP gates are wired and passing deterministically.\n")
    else:
        content.append("**Status:** ❌ *FAIL* — core gates failing.\n")
        content.append("- Recommendation: **NO-GO**.\n")

    REPORT.write_text("\n".join(content), encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())