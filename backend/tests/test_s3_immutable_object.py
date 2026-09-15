"""Contrato de escrita imutável usado pela evidência CBS v2."""

from __future__ import annotations

import hashlib

import pytest
from botocore.exceptions import ClientError

from app.tools import s3_tool


def test_put_immutable_usa_precondition_e_sse(monkeypatch):
    calls = []

    class FakeClient:
        def put_object(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(s3_tool, "_client", lambda: FakeClient())
    result = s3_tool.put_immutable_object("evidence/key", b"raw")
    assert calls[0]["IfNoneMatch"] == "*"
    assert calls[0]["ServerSideEncryption"] == "AES256"
    assert calls[0]["Metadata"]["sha256"] == hashlib.sha256(b"raw").hexdigest()
    assert result["size_bytes"] == 3


def test_preexisting_so_e_aceito_se_fingerprint_confere(monkeypatch):
    sha = hashlib.sha256(b"raw").hexdigest()

    class FakeClient:
        def put_object(self, **kwargs):  # noqa: ARG002
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )

        def head_object(self, **kwargs):  # noqa: ARG002
            return {"ContentLength": 3, "Metadata": {"sha256": sha}}

    monkeypatch.setattr(s3_tool, "_client", lambda: FakeClient())
    assert s3_tool.put_immutable_object("evidence/key", b"raw")["checksum_sha256"] == sha


def test_colisao_de_chave_falha_fechada(monkeypatch):
    class FakeClient:
        def put_object(self, **kwargs):  # noqa: ARG002
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )

        def head_object(self, **kwargs):  # noqa: ARG002
            return {"ContentLength": 999, "Metadata": {"sha256": "outro"}}

    monkeypatch.setattr(s3_tool, "_client", lambda: FakeClient())
    with pytest.raises(RuntimeError, match="collision"):
        s3_tool.put_immutable_object("evidence/key", b"raw")
