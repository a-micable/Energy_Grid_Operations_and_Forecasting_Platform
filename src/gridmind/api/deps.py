from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.session import get_session_factory
from gridmind.services.audit import AuditService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_audit_service(session: AsyncSession) -> AuditService:
    return AuditService(session)
