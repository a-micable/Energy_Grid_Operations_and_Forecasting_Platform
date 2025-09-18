from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.audit import AuditEntry
from gridmind.db.repositories.audit import AuditEntryRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuditEntryRepository(session)

    async def record(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor: str,
        *,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        reason: str | None = None,
        correlation_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            occurred_at=datetime.now(timezone.utc),
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            correlation_id=correlation_id or uuid4(),
            ip_address=ip_address,
        )
        await self._repo.add(entry)
        return entry
