import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.audit.repository import AuditLogRepository
from app.models.audit_log import AuditLog
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


@pytest.mark.asyncio
async def test_top_up_writes_audit_log(db_session):
    svc = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    user_id = uuid.uuid4()
    await svc.top_up(user_id, 100.0)

    logs = (await db_session.execute(select(AuditLog).where(AuditLog.action == "WALLET_TOPUP"))).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id == user_id
    assert logs[0].resource_type == "wallet"


@pytest.mark.asyncio
async def test_debit_for_ride_writes_audit_log(db_session):
    svc = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    user_id = uuid.uuid4()
    await svc.top_up(user_id, 100.0)
    ride_id = uuid.uuid4()
    await svc.debit_for_ride(user_id, 30.0, ride_id)

    logs = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "WALLET_DEBIT_RIDE_FARE"))
    ).scalars().all()
    assert len(logs) == 1
    assert str(ride_id) in logs[0].meta


@pytest.mark.asyncio
async def test_admin_adjust_writes_audit_log_with_actor(db_session):
    svc = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    target_user = uuid.uuid4()
    admin_user = uuid.uuid4()
    await svc.admin_adjust(target_user, 50.0, "manual credit", None, actor_id=admin_user)

    logs = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "WALLET_ADMIN_ADJUST"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id == admin_user
    assert str(target_user) in logs[0].meta


@pytest.mark.asyncio
async def test_wallet_service_works_without_audit_repo(db_session):
    """audit_repo is optional — service-layer callers that don't pass one
    (existing test suite, internal helpers) must not break."""
    svc = WalletService(WalletRepository(db_session))
    wallet = await svc.top_up(uuid.uuid4(), 20.0)
    assert wallet.balance == 20.0


@pytest.mark.asyncio
async def test_wallet_transaction_amount_check_constraint_at_db_level(db_session):
    """Defense in depth: even bypassing the service-layer amount<=0 check,
    the DB itself must reject a non-positive wallet_transactions.amount."""
    repo = WalletRepository(db_session)
    wallet = await repo.create(uuid.uuid4())
    with pytest.raises(IntegrityError):
        await repo.create_transaction(wallet.id, "CREDIT", "TOPUP", -5.0, 10.0)
