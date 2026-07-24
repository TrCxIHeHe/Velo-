import uuid
import pytest

from app.admin.repository import AdminAuditRepository, AdminRideRepository, AdminUserRepository
from app.admin.service import AdminService
from app.auth.repository import UserRepository
from app.core.exceptions import UserNotFoundError


@pytest.mark.asyncio
async def test_list_users_empty(db_session):
    svc = AdminService(
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
    )
    result = await svc.list_users()
    assert isinstance(result.items, list)
    assert isinstance(result.total, int)


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    svc = AdminService(
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
    )
    with pytest.raises(UserNotFoundError):
        await svc.get_user(uuid.uuid4())


@pytest.mark.asyncio
async def test_set_role(db_session):
    # Create a user first
    user_repo = UserRepository(db_session)
    user = await user_repo.create("uid-admin-test", "+910000099999")

    svc = AdminService(
        AdminUserRepository(db_session),
        AdminAuditRepository(db_session),
        AdminRideRepository(db_session),
    )
    updated = await svc.set_role(user.id, "ADMIN")
    assert updated.role == "ADMIN"
