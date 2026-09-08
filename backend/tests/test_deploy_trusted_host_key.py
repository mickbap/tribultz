"""SEC-07: deploy confia somente em chave de host obtida previamente."""

from __future__ import annotations

import getpass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURE_SCRIPT = REPO_ROOT / ".github" / "scripts" / "configure-deploy-ssh.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-prod.yml"


def _run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def _keypair(directory: Path, name: str) -> Path:
    private_key = directory / name
    _run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key))
    return private_key


def _known_hosts_line(host: str, public_key: Path) -> str:
    kind, value, *_ = public_key.read_text(encoding="utf-8").strip().split()
    return f"{host} {kind} {value}"


def _configure(
    tmp_path: Path,
    *,
    host: str,
    private_key: str,
    trusted_reference: str | None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(SSH_DIR=str(tmp_path / "ssh"), SSH_HOST=host, SSH_KEY=private_key)
    if trusted_reference is None:
        env.pop("SSH_KNOWN_HOSTS", None)
    else:
        env["SSH_KNOWN_HOSTS"] = trusted_reference
    return subprocess.run(
        ["bash", str(CONFIGURE_SCRIPT)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_expected_reference_is_installed_without_logging_private_key(tmp_path: Path) -> None:
    private_key = _keypair(tmp_path, "client")
    host_key = _keypair(tmp_path, "host")
    private_material = private_key.read_text(encoding="utf-8")
    trusted = _known_hosts_line("deploy.example", host_key.with_suffix(".pub"))

    result = _configure(
        tmp_path,
        host="deploy.example",
        private_key=private_material,
        trusted_reference=trusted,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert private_material not in result.stdout
    assert private_material not in result.stderr
    assert (tmp_path / "ssh" / "known_hosts").read_text(encoding="utf-8").strip() == trusted
    assert (tmp_path / "ssh" / "id_ed25519").read_text(encoding="utf-8").rstrip("\n") == private_material.rstrip("\n")


def test_missing_trusted_reference_fails_closed(tmp_path: Path) -> None:
    private_key = _keypair(tmp_path, "client")

    result = _configure(
        tmp_path,
        host="deploy.example",
        private_key=private_key.read_text(encoding="utf-8"),
        trusted_reference=None,
    )

    assert result.returncode != 0
    assert "Referência confiável do host SSH ausente" in result.stderr
    assert not (tmp_path / "ssh" / "id_ed25519").exists()


def test_reference_for_another_host_fails_closed(tmp_path: Path) -> None:
    private_key = _keypair(tmp_path, "client")
    host_key = _keypair(tmp_path, "host")
    trusted = _known_hosts_line("different.example", host_key.with_suffix(".pub"))

    result = _configure(
        tmp_path,
        host="deploy.example",
        private_key=private_key.read_text(encoding="utf-8"),
        trusted_reference=trusted,
    )

    assert result.returncode != 0
    assert "não contém o host SSH solicitado" in result.stderr
    assert not (tmp_path / "ssh" / "id_ed25519").exists()


def test_workflow_never_discovers_or_falls_back_to_network_host_key() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    deploy_job = workflow.split("\n  deploy:\n", maxsplit=1)[1]

    assert "secrets.MAGALU_SSH_KNOWN_HOSTS" in deploy_job
    assert "configure-deploy-ssh.sh" in deploy_job
    assert "ssh-keyscan" not in deploy_job
    assert deploy_job.count("StrictHostKeyChecking=yes") == 2
    assert deploy_job.count("UserKnownHostsFile=") == 2
    assert deploy_job.count("GlobalKnownHostsFile=/dev/null") == 2
    assert deploy_job.index("configure-deploy-ssh.sh") < deploy_job.index("scp -o")


@pytest.mark.skipif(shutil.which("sshd") is None, reason="sshd não disponível")
def test_different_host_key_aborts_before_remote_command(tmp_path: Path) -> None:
    """Integração OpenSSH real: A conecta; B não executa o comando remoto."""
    client_key = _keypair(tmp_path, "client")
    host_a = _keypair(tmp_path, "host-a")
    host_b = _keypair(tmp_path, "host-b")
    authorized_keys = tmp_path / "authorized_keys"
    authorized_keys.write_text(client_key.with_suffix(".pub").read_text(encoding="utf-8"), encoding="utf-8")
    authorized_keys.chmod(0o600)
    marker = tmp_path / "remote-command-ran"

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    host_label = f"[127.0.0.1]:{port}"
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(_known_hosts_line(host_label, host_a.with_suffix(".pub")) + "\n", encoding="utf-8")

    def start_server(host_key: Path) -> subprocess.Popen[str]:
        config = tmp_path / "sshd_config"
        config.write_text(
            "\n".join(
                (
                    f"Port {port}",
                    "ListenAddress 127.0.0.1",
                    f"HostKey {host_key}",
                    f"PidFile {tmp_path / 'sshd.pid'}",
                    f"AuthorizedKeysFile {authorized_keys}",
                    "PasswordAuthentication no",
                    "KbdInteractiveAuthentication no",
                    "ChallengeResponseAuthentication no",
                    "UsePAM no",
                    "StrictModes no",
                    "LogLevel ERROR",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        checked = _run(str(shutil.which("sshd")), "-t", "-f", str(config), check=False)
        if checked.returncode != 0:
            pytest.skip(f"sshd local indisponível: {checked.stderr.strip()}")
        process = subprocess.Popen(
            [str(shutil.which("sshd")), "-D", "-e", "-f", str(config)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _, stderr = process.communicate()
                pytest.skip(f"sshd local não iniciou: {stderr.strip()}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return process
            except OSError:
                time.sleep(0.05)
        process.terminate()
        process.wait(timeout=2)
        pytest.fail("sshd local não ficou pronto")

    def ssh(command: str) -> subprocess.CompletedProcess[str]:
        return _run(
            "ssh",
            "-p",
            str(port),
            "-i",
            str(client_key),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            f"{getpass.getuser()}@127.0.0.1",
            command,
            check=False,
        )

    server = start_server(host_a)
    try:
        expected = ssh("printf SEC07_CONNECTED")
        assert expected.returncode == 0, expected.stdout + expected.stderr
        assert expected.stdout == "SEC07_CONNECTED"
    finally:
        server.terminate()
        server.wait(timeout=5)

    server = start_server(host_b)
    try:
        wrong = ssh(f"touch {marker}")
        assert wrong.returncode != 0
        assert not marker.exists()
        assert "REMOTE HOST IDENTIFICATION HAS CHANGED" in wrong.stderr
    finally:
        server.terminate()
        server.wait(timeout=5)
