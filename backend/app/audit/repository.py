import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        payload: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id, action=action, entity_type=entity_type,
            entity_id=entity_id, payload=payload,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
