"""Celery task — descarte de documentos após 12 meses (Escopo 4.3, go-live de billing).

Retenção definida: 12 meses a partir do upload (Document.created_at).
Depois disso, o objeto no S3/MinIO e a linha em `documents` são apagados —
minimização de dado (LGPD art. 6º, III) sobre XMLs de terceiros que a
Tribultz processa mas não tem motivo de negócio para reter indefinidamente.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery
from app.database import SessionLocal
from app.models.documents import Document
from app.tools.s3_tool import delete_object

logger = logging.getLogger(__name__)

RETENTION_DAYS = 365


@celery.task(name="documents.purge_expired")
def purge_expired_documents():
    """Apaga documentos (S3 + linha no banco) com mais de 12 meses.

    Roda mensalmente via beat schedule. Falha ao apagar do S3 não impede
    seguir para o próximo documento — cada um é tratado independentemente
    e reportado no log, para não deixar um erro isolado travar a rotina
    inteira do mês.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        expired = db.execute(
            select(Document).where(Document.created_at < cutoff)
        ).scalars().all()

        deleted_count = 0
        error_count = 0
        for doc in expired:
            try:
                delete_object(str(doc.storage_key))
            except Exception:
                logger.exception(
                    "purge_expired_documents: falha ao apagar do S3, mantendo linha no banco | document_id=%s",
                    doc.id,
                )
                error_count += 1
                continue

            db.delete(doc)
            deleted_count += 1

        if deleted_count or error_count:
            db.commit()
            logger.info(
                "purge_expired_documents: %d apagados, %d com erro (mantidos p/ retry no próximo ciclo)",
                deleted_count, error_count,
            )
        else:
            logger.debug("purge_expired_documents: nenhum documento expirado")

    except Exception:
        db.rollback()
        logger.exception("purge_expired_documents failed")
        raise
    finally:
        db.close()
