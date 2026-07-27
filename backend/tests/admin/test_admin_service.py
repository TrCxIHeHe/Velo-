import uuid
import pytest
from sqlalchemy import select

from app.admin.repository import (
    AdminAuditRepository,
    AdminRepository,
    AdminRideRepository,
    AdminUserRepository,
)
from app.admin.service import AdminService
from app.audit.repository import AuditLogRepository
from app.auth.repository import UserRepository
from app.core.exceptions import UserNotFoundError
from app.models.audit_log import AuditLog


def _make_service(db_session) -> AdminService:
    return AdminService(
        AdminRepository(db_session),
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
    )


@pytest.mark.asyncio
async def test_list_users_empty(db_session):
    svc = _make_service(db_session)
    result = await svc.list_users()
    assert isinstance(result.items, list)
    assert isinstance(result.total, int)


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    svc = _make_service(db_session)
    with pytest.raises(UserNotFoundError):
        await svc.get_user(uuid.uuid4())


@pytest.mark.asyncio
async def test_set_role(db_session):
    # Create a user first
    user_repo = UserRepository(db_session)
    user = await user_repo.create("uid-admin-test", "+910000099999")

    svc = _make_service(db_session)
    updated = await svc.set_role(user.id, "ADMIN")
    assert updated.role == "ADMIN"


@pytest.mark.asyncio
async def test_set_role_writes_audit_log_with_actor(db_session):
    user_repo = UserRepository(db_session)
    target = await user_repo.create("uid-audit-target", "+910000099998")
    actor_id = uuid.uuid4()

    svc = AdminService(
        AdminRepository(db_session),
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
        AuditLogRepository(db_session),
    )
    await svc.set_role(target.id, "ADMIN", actor_id=actor_id)

    logs = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_SET_USER_ROLE"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id == actor_id
    assert logs[0].resource_id == str(target.id)


@pytest.mark.asyncio
async def test_set_active_writes_audit_log_with_actor(db_session):
    user_repo = UserRepository(db_session)
    target = await user_repo.create("uid-audit-target-2", "+910000099997")
    actor_id = uuid.uuid4()

    svc = AdminService(
        AdminRepository(db_session),
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
        AuditLogRepository(db_session),
    )
    await svc.set_active(target.id, False, actor_id=actor_id)

    logs = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_SET_USER_ACTIVE"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id == actor_id
