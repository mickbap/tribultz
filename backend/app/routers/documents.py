"""Documents router — presigned upload/download flow with S3/MinIO.

Endpoints
---------
POST  /api/v1/documents/upload-url   Issue #122 — presigned PUT URL (5 min TTL)
POST  /api/v1/documents/confirm      Issue #124 — confirm upload + index + extract XML
GET   /api/v1/documents              Issue #125 — list documents (tenant-scoped)
GET   /api/v1/documents/{id}/download Issue #125 — presigned GET URL (15 min TTL)
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.documents import Document
from app.config import settings
from app.tools import s3_tool

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# ── Constants ──────────────────────────────────────────────────────────────────

UPLOAD_TTL_SECONDS = 300    # 5 minutes
DOWNLOAD_TTL_SECONDS = 900  # 15 minutes
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024  # política pública existente: 2 MB por arquivo
S3_READ_CHUNK_BYTES = 64 * 1024

ALLOWED_DOC_TYPES = {"nfe", "nfse", "cte", "other"}
ALLOWED_CONTENT_TYPES = {
    "application/xml",
    "text/xml",
    "application/pdf",
    "application/octet-stream",
}

logger = logging.getLogger(__name__)

# ── Schemas ────────────────────────────────────────────────────────────────────


class UploadUrlRequest(BaseModel):
    doc_type: Literal["nfe", "nfse", "cte", "other"]
    original_filename: Optional[str] = None
    content_type: str = "application/xml"

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {sorted(ALLOWED_CONTENT_TYPES)}")
        return v


class UploadUrlResponse(BaseModel):
    document_id: UUID
    upload_url: str
    storage_key: str
    expires_at: datetime


class ConfirmRequest(BaseModel):
    document_id: UUID
    file_size: Optional[int] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doc_type: str
    original_filename: Optional[str]
    storage_key: str
    file_size: Optional[int]
    content_type: Optional[str]
    status: str
    uploaded_at: Optional[datetime]
    created_at: datetime
    fiscal_metadata: dict[str, Any]


class DownloadResponse(BaseModel):
    download_url: str
    expires_at: datetime


# ── Helpers ────────────────────────────────────────────────────────────────────


class StoredObjectMissing(Exception):
    """The document row exists, but its object does not."""


class StoredObjectUnavailable(Exception):
    """S3 could not provide authoritative evidence for the object."""


class StoredObjectTooLarge(Exception):
    """The authoritative object exceeds the accepted upload size."""


class StoredObjectInvalid(Exception):
    """S3 evidence is inconsistent with the upload contract."""


@dataclass(frozen=True)
class StoredObjectEvidence:
    content: bytes
    size_bytes: int
    checksum_sha256: str
    content_type: str
    etag: str | None


def _read_body_limited(body: Any, max_bytes: int) -> bytes:
    """Read at most ``max_bytes + 1`` bytes and abort as soon as the cap is exceeded."""
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            remaining = max_bytes + 1 - total
            chunk = body.read(min(S3_READ_CHUNK_BYTES, remaining))
            if not isinstance(chunk, bytes):
                raise StoredObjectUnavailable("S3 retornou stream inválido.")
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise StoredObjectTooLarge
            chunks.append(chunk)
    except (StoredObjectTooLarge, StoredObjectUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001
        raise StoredObjectUnavailable("Falha durante leitura do objeto no S3.") from exc
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()
    return b"".join(chunks)


def _s3_error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return None
    error = response.get("Error")
    if not isinstance(error, dict):
        return None
    code = error.get("Code")
    return str(code) if code is not None else None


def _load_authoritative_object(
    storage_key: str,
    expected_content_type: str | None,
) -> StoredObjectEvidence:
    """Fetch and validate the stored object; client-declared size is never authoritative."""
    try:
        client = s3_tool._client()
        obj = client.get_object(Bucket=settings.S3_BUCKET, Key=storage_key)
    except Exception as exc:  # noqa: BLE001
        if _s3_error_code(exc) in {"NoSuchKey", "NotFound", "404"}:
            raise StoredObjectMissing from exc
        raise StoredObjectUnavailable("Não foi possível consultar o objeto no S3.") from exc

    body = obj.get("Body")
    authoritative_size = obj.get("ContentLength")
    authoritative_type = obj.get("ContentType")
    if (
        body is None
        or isinstance(authoritative_size, bool)
        or not isinstance(authoritative_size, int)
        or authoritative_size < 0
        or not isinstance(authoritative_type, str)
    ):
        close = getattr(body, "close", None)
        if callable(close):
            close()
        raise StoredObjectUnavailable("S3 não retornou metadados autoritativos válidos.")
    if authoritative_size > MAX_DOCUMENT_BYTES:
        close = getattr(body, "close", None)
        if callable(close):
            close()
        raise StoredObjectTooLarge
    if authoritative_type not in ALLOWED_CONTENT_TYPES:
        close = getattr(body, "close", None)
        if callable(close):
            close()
        raise StoredObjectInvalid("Tipo de conteúdo armazenado não permitido.")
    if expected_content_type and authoritative_type != expected_content_type:
        close = getattr(body, "close", None)
        if callable(close):
            close()
        raise StoredObjectInvalid("Tipo de conteúdo armazenado diverge do upload autorizado.")

    content = _read_body_limited(body, MAX_DOCUMENT_BYTES)
    if len(content) != authoritative_size:
        raise StoredObjectInvalid("Tamanho do stream diverge do metadado autoritativo do S3.")
    raw_etag = obj.get("ETag")
    etag = raw_etag.strip('"') if isinstance(raw_etag, str) else None
    return StoredObjectEvidence(
        content=content,
        size_bytes=authoritative_size,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        content_type=authoritative_type,
        etag=etag,
    )


def _storage_evidence(evidence: StoredObjectEvidence) -> dict[str, Any]:
    return {
        "checksum_sha256": evidence.checksum_sha256,
        "size_bytes": evidence.size_bytes,
        "content_type": evidence.content_type,
        "etag": evidence.etag,
    }


def _assert_same_confirmed_content(doc: Document, evidence: StoredObjectEvidence) -> bool:
    """Return False for legacy rows without a snapshot; reject a known-content overwrite."""
    metadata = doc.fiscal_metadata if isinstance(doc.fiscal_metadata, dict) else {}
    stored = metadata.get("storage_evidence")
    if not isinstance(stored, dict):
        return False
    if (
        stored.get("checksum_sha256") != evidence.checksum_sha256
        or stored.get("size_bytes") != evidence.size_bytes
        or stored.get("content_type") != evidence.content_type
    ):
        raise StoredObjectInvalid("Objeto confirmado foi sobrescrito com conteúdo diferente.")
    return True

def _generate_storage_key(tenant_id: UUID, doc_type: str, original_filename: Optional[str]) -> str:
    """Build a deterministic, collision-safe S3 key."""
    uid = str(_uuid.uuid4())
    ext = ""
    if original_filename:
        # extract extension safely
        parts = original_filename.rsplit(".", 1)
        if len(parts) == 2 and re.match(r"^[a-zA-Z0-9]{1,8}$", parts[1]):
            ext = f".{parts[1].lower()}"
    return f"documents/{tenant_id}/{doc_type}/{uid}{ext}"


def _generate_presigned_put(storage_key: str, content_type: str, ttl: int) -> str:
    """Generate a presigned PUT URL via boto3."""
    import boto3
    from botocore.config import Config as BotoConfig

    boto_cfg = BotoConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path" if settings.S3_FORCE_PATH_STYLE else "virtual"},
    )
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=boto_cfg,
        region_name=settings.S3_REGION,
    )
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=ttl,
    )


def _extract_xml_metadata(content: bytes) -> dict[str, Any]:
    """
    Extract key fiscal fields from already validated, size-bounded content.
    Returns empty dict on any error (non-blocking).
    """
    try:
        import xml.etree.ElementTree as ET
        meta: dict[str, Any] = {}

        # Parse XML — namespace-agnostic extraction
        try:
            root = ET.fromstring(content)

            def find_text(tag: str) -> Optional[str]:
                """Find first element matching local-name anywhere in tree."""
                for el in root.iter():
                    local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                    if local == tag and el.text:
                        return el.text.strip()
                return None

            for field in ("chNFe", "chCTe", "chNFSe"):
                val = find_text(field)
                if val:
                    meta["chave_acesso"] = val
                    break

            for field in ("CNPJ", "cnpj"):
                val = find_text(field)
                if val and len(val) >= 14:
                    meta["cnpj_emitente"] = val
                    break

            for field in ("vNF", "vNFe", "vLiq", "vServ"):
                val = find_text(field)
                if val:
                    meta["valor_total"] = val
                    break

            ncm = find_text("NCM")
            if ncm:
                meta["ncm"] = ncm

        except ET.ParseError:
            pass  # Not valid XML — store raw size only

        return meta
    except Exception:  # noqa: BLE001
        return {}


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar URL de upload (presigned PUT)",
    description=(
        "Cria um registro de documento com status `pending_upload` e retorna "
        "uma URL presigned S3 (TTL 5 min) para que o cliente faça o PUT diretamente."
    ),
)
def get_upload_url(
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadUrlResponse:
    storage_key = _generate_storage_key(
        current_user.tenant_id,  # type: ignore[arg-type]
        payload.doc_type,
        payload.original_filename,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=UPLOAD_TTL_SECONDS)

    try:
        upload_url = _generate_presigned_put(storage_key, payload.content_type, UPLOAD_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Não foi possível gerar URL de upload: {exc}",
        ) from exc

    doc = Document(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        doc_type=payload.doc_type,
        original_filename=payload.original_filename,
        storage_key=storage_key,
        content_type=payload.content_type,
        status="pending_upload",
        expires_at=expires_at,
        fiscal_metadata={},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return UploadUrlResponse(
        document_id=doc.id,  # type: ignore[arg-type]
        upload_url=upload_url,
        storage_key=storage_key,
        expires_at=expires_at,
    )


@router.post(
    "/confirm",
    response_model=DocumentResponse,
    summary="Confirmar upload e indexar documento",
    description=(
        "Após o cliente fazer PUT direto no S3, chame este endpoint para marcar o "
        "documento como `confirmed`, registrar tamanho e extrair metadados do XML."
    ),
)
def confirm_upload(
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    doc: Document | None = db.execute(
        select(Document).where(
            Document.id == payload.document_id,
            Document.tenant_id == current_user.tenant_id,
        ).with_for_update()
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    if doc.status == "error":  # type: ignore[truthy-function]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Documento em estado de erro — abra um novo upload.",
        )

    try:
        evidence = _load_authoritative_object(
            doc.storage_key,  # type: ignore[arg-type]
            doc.content_type,  # type: ignore[arg-type]
        )
    except StoredObjectMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload não encontrado no armazenamento.",
        ) from exc
    except StoredObjectTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {MAX_DOCUMENT_BYTES // 1024 // 1024} MB.",
        ) from exc
    except StoredObjectInvalid as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StoredObjectUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível validar o upload no armazenamento.",
        ) from exc

    if doc.status == "confirmed":  # type: ignore[truthy-function]
        try:
            if _assert_same_confirmed_content(doc, evidence):
                return doc  # idempotente para o mesmo conteúdo comprovado
        except StoredObjectInvalid as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        # Compatibilidade: primeira reconfirmação de linha antiga registra o snapshot.
        existing: dict[str, Any] = dict(doc.fiscal_metadata or {})  # type: ignore[arg-type]
        existing["storage_evidence"] = _storage_evidence(evidence)
        doc.fiscal_metadata = existing  # type: ignore[assignment]
        doc.file_size = evidence.size_bytes  # type: ignore[assignment]
        db.commit()
        db.refresh(doc)
        return doc

    # Extração é opcional e ocorre somente depois da validação obrigatória.
    try:
        extracted = _extract_xml_metadata(evidence.content)
    except Exception:  # noqa: BLE001
        logger.warning("Falha na extração opcional do documento %s", doc.id, exc_info=True)
        extracted = {}
    extracted["storage_evidence"] = _storage_evidence(evidence)

    doc.status = "confirmed"  # type: ignore[assignment]
    doc.uploaded_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    doc.file_size = evidence.size_bytes  # type: ignore[assignment]
    doc.fiscal_metadata = extracted  # type: ignore[assignment]
    db.commit()
    db.refresh(doc)
    return doc


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="Listar documentos do tenant",
    description="Retorna documentos do tenant autenticado, com filtros opcionais por tipo e status.",
)
def list_documents(
    doc_type: Optional[str] = Query(None, description="Filtrar por tipo: nfe, nfse, cte, other"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.tenant_id == current_user.tenant_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if doc_type:
        if doc_type not in ALLOWED_DOC_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"doc_type inválido. Use: {sorted(ALLOWED_DOC_TYPES)}",
            )
        stmt = stmt.where(Document.doc_type == doc_type)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)

    return list(db.scalars(stmt).all())


@router.get(
    "/{document_id}/download",
    response_model=DownloadResponse,
    summary="Gerar URL de download (presigned GET)",
    description="Retorna URL presigned S3 (TTL 15 min) para download do documento.",
)
def get_download_url(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadResponse:
    doc: Document | None = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    if doc.status not in ("uploaded", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Documento ainda não está disponível para download (status: {doc.status}).",
        )

    try:
        download_url = s3_tool.get_object_url(
            key=doc.storage_key,  # type: ignore[arg-type]
            bucket=settings.S3_BUCKET,
            expires_in=DOWNLOAD_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Não foi possível gerar URL de download: {exc}",
        ) from exc

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_TTL_SECONDS)
    return DownloadResponse(download_url=download_url, expires_at=expires_at)
