from app.services.persistence.postgres_provider import PostgresPersistenceStore
from app.services.persistence.redis_provider import RedisStateStore
from app.services.persistence.service import CrewPersistenceService

_persistence_service: CrewPersistenceService | None = None


def get_persistence_service() -> CrewPersistenceService:
    global _persistence_service
    if _persistence_service is None:
        redis_store = RedisStateStore()
        postgres_store = PostgresPersistenceStore()
        _persistence_service = CrewPersistenceService(
            state_store=redis_store,
            fiscal_context_store=postgres_store,
            fast_idempotency_store=redis_store,
            durable_idempotency_store=postgres_store,
        )
    return _persistence_service


__all__ = ["CrewPersistenceService", "get_persistence_service"]
