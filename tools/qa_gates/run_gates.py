#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from dataclasses import dataclass
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

def load_fastapi_app(backend_root: Path):
    # Ensure backend/ is importable (package root is backend/)
    repo_root = Path(__file__).resolve().parents[3]
    for p in (backend_root, repo_root):
        s = str(p.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)

    # Most likely: backend/app/main.py exports `app`
    try:
        from app.main import app  # type: ignore
        return app
    except Exception:
        # Fallbacks (keep best-effort)
        try:
            from backend.app.main import app  # type: ignore
            return app
        except Exception as e:
            raise RuntimeError(f"Could not import FastAPI app (expected app.main:app). Error: {e}") from e

@dataclass
class SubGate:
    name: str
    ok: bool
    detail: str = ""

def http_contract_security_gates(backend_root: Path, strict: bool) -> tuple[bool, list[SubGate]]:
    subs: list[SubGate] = []
    ok_all = True

    # 1) Build TestClient
    try:
        app = load_fastapi_app(backend_root)
        from fastapi.testclient import TestClient  # type: ignore
        client = TestClient(app)
    except Exception as e:
        subs.append(SubGate("bootstrap TestClient(app)", False, str(e)))
        return (False if strict else False), subs

    # 2) 401 without token (chat)
    try:
        r = client.post("/api/v1/chat/message", json={"message": "hello"})
        g_ok = (r.status_code == 401)
        subs.append(SubGate("401 sem token em POST /api/v1/chat/message", g_ok, f"status={r.status_code} body={r.text[:400]}"))
        ok_all &= g_ok
    except Exception as e:
        subs.append(SubGate("401 sem token em POST /api/v1/chat/message", False, str(e)))
        ok_all = False

    # 3) 422 message > 4000
    try:
        long_msg = "a" * 4001
        r = client.post("/api/v1/chat/message", json={"message": long_msg})
        g_ok = (r.status_code == 422)
        subs.append(SubGate("422 message > 4000 em POST /api/v1/chat/message", g_ok, f"status={r.status_code} body={r.text[:400]}"))
        ok_all &= g_ok
    except Exception as e:
        subs.append(SubGate("422 message > 4000 em POST /api/v1/chat/message", False, str(e)))
        ok_all = False

    # 4) Contract/evidence validated by existing deterministic test module
    chat_tests = backend_root / "tests" / "api" / "test_chat.py"
    if chat_tests.exists():
        code, out = sh(["pytest", "-q", str(chat_tests.relative_to(backend_root))], cwd=backend_root)
        g_ok = (code == 0)
        subs.append(SubGate("Contrato/evidence via backend/tests/api/test_chat.py", g_ok, out[:800]))
        ok_all &= g_ok
    else:
        msg = "Missing backend/tests/api/test_chat.py (expected contract tests here)."
        subs.append(SubGate("Contrato/evidence via backend/tests/api/test_chat.py", False, msg))
        ok_all = False

    # 5) Jobs tenant-scope (anti-IDOR) — deterministic static check on query guards
    try:
        jobs_router = backend_root / "app" / "routers" / "jobs.py"
        txt = jobs_router.read_text(encoding="utf-8")
        # Require multiple occurrences of tenant guard in queries (from report lines 139/155/245 etc)
        must = [
            "AND tenant_id",
            "tenant_id",
            "WHERE id",
        ]
        g_ok = all(m in txt for m in must) and txt.count("tenant_id") >= 5
        detail = f"tenant_id occurrences={txt.count('tenant_id')}"
        subs.append(SubGate("Jobs tenant-scope guard (static scan routers/jobs.py)", g_ok, detail))
        ok_all &= g_ok
    except Exception as e:
        subs.append(SubGate("Jobs tenant-scope guard (static scan routers/jobs.py)", False, str(e)))
        ok_all = False

    # 6) Rate limit 429 — deterministic unit simulation (RateLimiter must raise 429 when exceeded)
    try:
        from app.services.rate_limit import RateLimiter  # type: ignore

        class FakeRedis:
            def __init__(self):
                self.store = {}
            def incr(self, key):
                self.store[key] = int(self.store.get(key, 0)) + 1
                return self.store[key]
            def expire(self, key, ttl):
                return True

        rl = None
        sig = None
        try:
            sig = inspect.signature(RateLimiter)  # type: ignore
        except Exception:
            sig = None

        # Instantiate best-effort
        try:
            rl = RateLimiter()  # type: ignore
        except Exception:
            # try with common kwargs if constructor requires them
            kwargs = {}
            if sig:
                for name in sig.parameters.keys():
                    if name in ("max_requests", "limit"):
                        kwargs[name] = 1
                    if name in ("window_seconds", "window", "period_seconds"):
                        kwargs[name] = 60
            rl = RateLimiter(**kwargs)  # type: ignore

        # Force low limit if attributes exist
        for attr in ("max_requests", "limit", "max_requests_per_window"):
            if hasattr(rl, attr):
                setattr(rl, attr, 1)

        # Attach fake redis if supported
        if hasattr(rl, "redis"):
            setattr(rl, "redis", FakeRedis())

        # Call twice; second must raise HTTPException(429)
        raised_429 = False
        for i in range(2):
            try:
                rl.check_or_raise("qa_rate_limit_key")  # type: ignore
            except Exception as ex:
                code = getattr(ex, "status_code", None)
                if code == 429:
                    raised_429 = True
                else:
                    raise
        g_ok = raised_429
        subs.append(SubGate("RateLimiter raises 429 when exceeded (unit)", g_ok, "raised_429=%s" % raised_429))
        ok_all &= g_ok

    except Exception as e:
        subs.append(SubGate("RateLimiter raises 429 when exceeded (unit)", False, str(e)))
        ok_all = False

    # Strict mode: must be fully validated (no PENDING)
    if strict:
        return ok_all, subs
    return ok_all, subs

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "ci"], default="local")
    args = ap.parse_args()

    strict = (args.mode == "ci")

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

    # Gate: pyright
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

    # Gate: contract + security (HTTP) — now wired (no PENDING)
    content.append(section("Gate: contract + security (HTTP)"))
    http_ok, subs = http_contract_security_gates(backend_root, strict=strict)
    overall_ok &= http_ok
    content.append(gate_line("HTTP contract/security probes (wired)", http_ok))
    for sg in subs:
        content.append(gate_line(f"{sg.name}", sg.ok))
        if sg.detail and not sg.ok:
            content.append("\n```text\n" + sg.detail[:1200] + "\n```\n")
        elif sg.detail and sg.ok:
            content.append(f"\n```text\n{sg.detail[:400]}\n```\n")

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
        content.append("**Status:** ✅ *PASS* — all required gates green.\n")
        content.append("- Recommendation: **GO**.\n")
    else:
        content.append("**Status:** ❌ *FAIL* — one or more required gates failing.\n")
        content.append("- Recommendation: **NO-GO**.\n")

    REPORT.write_text("\n".join(content), encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0 if overall_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())