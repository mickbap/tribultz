"""SEC-06: o deploy deve construir exatamente o SHA aprovado pelos gates."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "infra" / "scripts" / "deploy.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-prod.yml"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _scenario(tmp_path: Path) -> tuple[Path, str, str]:
    remote = tmp_path / "remote.git"
    author = tmp_path / "author"
    deployed = tmp_path / "deployed"

    _git(tmp_path, "init", "--bare", str(remote))
    author.mkdir()
    _git(author, "init")
    _git(author, "config", "user.email", "sec06@example.com")
    _git(author, "config", "user.name", "SEC-06 test")
    (author / "version.txt").write_text("A\n", encoding="utf-8")
    _git(author, "add", "version.txt")
    _git(author, "commit", "-m", "commit A")
    _git(author, "branch", "-M", "main")
    _git(author, "remote", "add", "origin", str(remote))
    _git(author, "push", "-u", "origin", "main")
    sha_a = _git(author, "rev-parse", "HEAD")

    _git(tmp_path, "clone", "--branch", "main", str(remote), str(deployed))

    (author / "version.txt").write_text("B\n", encoding="utf-8")
    _git(author, "add", "version.txt")
    _git(author, "commit", "-m", "commit B")
    _git(author, "push", "origin", "main")
    sha_b = _git(author, "rev-parse", "HEAD")
    assert sha_a != sha_b
    return deployed, sha_a, sha_b


def _source_only(
    deployed: Path, run_sha: str, validated_sha: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        TRIBULTZ_DEPLOY_DIR=str(deployed),
        TRIBULTZ_DEPLOY_LOG_FILE=str(deployed.parent / "deploy.log"),
        TRIBULTZ_DEPLOY_SOURCE_ONLY="true",
    )
    return subprocess.run(
        [
            "bash",
            str(DEPLOY_SCRIPT),
            "--sha",
            run_sha,
            "--validated-sha",
            validated_sha,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_corrida_a_b_mantem_fonte_no_sha_a(tmp_path: Path) -> None:
    deployed, sha_a, sha_b = _scenario(tmp_path)

    result = _source_only(deployed, sha_a, sha_a)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(deployed, "rev-parse", "HEAD") == sha_a
    assert (deployed / "version.txt").read_text(encoding="utf-8") == "A\n"
    assert f"DEPLOY_RECORD BUILD_SHA={sha_a}" in result.stdout
    assert sha_b != _git(deployed, "rev-parse", "HEAD")


def test_divergencia_run_validated_aborta_antes_do_build(tmp_path: Path) -> None:
    deployed, sha_a, sha_b = _scenario(tmp_path)

    result = _source_only(deployed, sha_a, sha_b)

    assert result.returncode != 0
    assert "diverge de VALIDATED_SHA" in result.stderr
    assert "DEPLOY_RECORD BUILD_SHA=" not in result.stdout


def test_workflow_exige_gates_e_propaga_sha_exato() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    deploy_job = workflow.split("\n  deploy:\n", maxsplit=1)[1]

    assert "target_sha:" in workflow
    assert "backend-gates" in workflow
    assert "frontend-build" in workflow
    assert "commits/${RUN_SHA}/check-runs" in workflow
    assert "needs: validate" in workflow
    assert "ref: ${{ github.sha }}" in deploy_job
    assert "--sha '$RUN_SHA' --validated-sha '$VALIDATED_SHA'" in workflow
    assert 'REMOTE_SCRIPT="/tmp/tribultz-deploy-${RUN_SHA}.sh"' in deploy_job
    assert "scp -o StrictHostKeyChecking=yes" in deploy_job
    assert "< infra/scripts/deploy.sh" not in deploy_job
    assert "RUN_SHA" in workflow
    assert "VALIDATED_SHA" in workflow
    assert "BUILD_SHA" in workflow
    assert "DEPLOYED_SHA" in workflow
