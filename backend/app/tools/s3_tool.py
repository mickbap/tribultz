"""S3Tool – MinIO (dev) / AWS S3 (prod) compatible storage operations."""

import hashlib
from io import BytesIO
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings
from app.services.persistence import get_persistence_service


def _client():
    """Create a boto3 S3 client pointing at MinIO or AWS."""
    boto_config = BotoConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path" if settings.S3_FORCE_PATH_STYLE else "virtual"},
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=boto_config,
        region_name=settings.S3_REGION,
    )


# ── 1. Put Object ────────────────────────────────────────────
def put_object(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
    transaction_id: Optional[str] = None,
) -> dict:
    """
    Upload an object to S3/MinIO.
    Returns {bucket, key, checksum, size}.
    """
    bucket = bucket or settings.S3_BUCKET
    service = get_persistence_service()

    def _write() -> dict:
        client = _client()
        sha = hashlib.sha256(data).hexdigest()
        # Criptografia em repouso explícita (Escopo 4.3, go-live de billing) —
        # a doc oficial da Magalu Object Storage não confirma SSE por padrão
        # especificamente para Object Storage, então não dependemos do default
        # da infra. AES256 (SSE-S3) é suportado tanto por MinIO (dev) quanto
        # por provedores S3-compatíveis em produção.
        extra: dict = {"ContentType": content_type, "ServerSideEncryption": "AES256"}
        if metadata:
            extra["Metadata"] = metadata
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=BytesIO(data),
            ContentLength=len(data),
            **extra,
        )
        return {
            "bucket": bucket,
            "key": key,
            "checksum_sha256": sha,
            "size_bytes": len(data),
        }

    payload = {
        "bucket": bucket,
        "key": key,
        "content_type": content_type,
        "metadata": metadata or {},
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return service.run_idempotent(
        operation="s3_put_object",
        transaction_id=transaction_id,
        payload=payload,
        runner=_write,
    )


def put_immutable_object(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> dict:
    """Grava uma evidência uma única vez, com chave content-addressed.

    ``IfNoneMatch=*`` impede overwrite inclusive sob concorrência. Uma colisão
    de chave só é aceita quando tamanho e SHA-256 confirmam que o objeto já
    existente contém exatamente os mesmos bytes.
    """
    bucket = bucket or settings.S3_BUCKET
    sha = hashlib.sha256(data).hexdigest()
    object_metadata = {**(metadata or {}), "sha256": sha}
    client = _client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=BytesIO(data),
            ContentLength=len(data),
            ContentType=content_type,
            ServerSideEncryption="AES256",
            Metadata=object_metadata,
            IfNoneMatch="*",
        )
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status not in (409, 412) and code not in ("PreconditionFailed", "ConditionalRequestConflict"):
            raise
        existing = client.head_object(Bucket=bucket, Key=key)
        existing_sha = (existing.get("Metadata") or {}).get("sha256")
        if existing.get("ContentLength") != len(data) or existing_sha != sha:
            raise RuntimeError("immutable object key collision") from exc
    return {
        "bucket": bucket,
        "key": key,
        "checksum_sha256": sha,
        "size_bytes": len(data),
    }


# ── 2. Get Object URL ────────────────────────────────────────
def get_object_url(
    key: str,
    bucket: Optional[str] = None,
    expires_in: int = 3600,
) -> str:
    """Generate a pre-signed URL valid for `expires_in` seconds."""
    bucket = bucket or settings.S3_BUCKET
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


# ── 3. Delete Object ─────────────────────────────────────────
def delete_object(
    key: str,
    bucket: Optional[str] = None,
) -> None:
    """Delete an object from S3/MinIO — usado pelo job de retenção (Escopo 4.3)."""
    bucket = bucket or settings.S3_BUCKET
    client = _client()
    client.delete_object(Bucket=bucket, Key=key)


# ── 4. Checksum ──────────────────────────────────────────────
def checksum(
    key: str,
    bucket: Optional[str] = None,
) -> dict:
    """
    Download the object and compute its SHA-256.
    Returns {key, checksum_sha256, size_bytes}.
    """
    bucket = bucket or settings.S3_BUCKET
    client = _client()
    resp = client.get_object(Bucket=bucket, Key=key)
    body = resp["Body"].read()
    sha = hashlib.sha256(body).hexdigest()
    return {
        "key": key,
        "checksum_sha256": sha,
        "size_bytes": len(body),
    }
