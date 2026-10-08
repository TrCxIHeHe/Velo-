"""QR decoding pipeline + debug-image storage for POST /docks/{id}/scan."""
import uuid

import pytest

from app.audit.repository import AuditLogRepository
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.dock_vision.service import QrDecodeError, decode_qr_with_strategy
from app.models.user import User
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService
from tests.dock.qr_frames import frame_with_qr, frame_without_qr, make_ride_jwt

pytestmark = pytest.mark.asyncio

DOCK = uuid.UUID("33333333-3333-3333-3333-333333333333")
TOKEN = make_ride_jwt(DOCK)


# ── Decoder (pure) ───────────────────────────────────────────────────────────

async def test_clearly_visible_qr_uses_fast_path():
    text, strategy = decode_qr_with_strategy(frame_with_qr(TOKEN, side=210))
    assert text == TOKEN
    assert strategy == "pyzbar-gray"


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(side=170, cx=215, cy=150),   # off-centre (bottom-right)
        dict(side=150, cx=100, cy=85),    # off-centre (top-left)
        dict(side=140),                   # smaller in frame
        dict(side=120, cx=230, cy=70),    # small AND off-centre
        dict(side=190, persp=0.04),       # slight perspective
    ],
    ids=["off-centre-br", "off-centre-tl", "smaller", "small-off-centre", "slight-perspective"],
)
async def test_position_size_and_perspective_variants(kwargs):
    text, _strategy = decode_qr_with_strategy(frame_with_qr(TOKEN, **kwargs))
    assert text == TOKEN


async def test_moderate_perspective_decodes_most_frames():
    """~8 % corner skew on a dense (≈330-char JWT) QR in a 320x240 frame.

    This is near the decoder's practical limit, so assert a rate over many
    random tokens rather than a single (flaky) frame.  Measured ≈ 29/30.
    """
    decoded = 0
    for seed in range(12):
        token = make_ride_jwt(DOCK)
        try:
            text, _ = decode_qr_with_strategy(frame_with_qr(token, side=190, persp=0.08, seed=seed))
            decoded += text == token
        except QrDecodeError:
            pass
    assert decoded >= 9


async def test_qr_with_non_token_content_still_decodes():
    """Decoding is independent of what the QR contains."""
    text, _ = decode_qr_with_strategy(frame_with_qr("hello-not-a-jwt", side=200))
    assert text == "hello-not-a-jwt"


async def test_frame_without_qr_raises():
    with pytest.raises(QrDecodeError):
        decode_qr_with_strategy(frame_without_qr())


async def test_garbage_bytes_raise_not_crash():
    with pytest.raises(QrDecodeError):
        decode_qr_with_strategy(b"\x00" * 4096)


# ── Scan endpoint + debug images ─────────────────────────────────────────────

async def _dock_user_and_service(db_session, redis_mock):
    dock_repo = DockRepository(db_session)
    dock_svc = DockService(dock_repo, VehicleRepository(db_session))
    dock = await dock_svc.create_dock(
        DockCreate(name="Scan Dock", location_lat=1.0, location_lng=1.0, total_slots=2)
    )
    slot = await dock_repo.find_free_slot(dock.id)
    await dock_svc.add_vehicle(
        VehicleCreate(qr_code=f"qr-{uuid.uuid4()}", battery_level=100, slot_id=slot.id)
    )
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, firebase_uid=f"uid-{user_id}", phone_number="+910000012345"))
    await db_session.flush()
    await WalletService(WalletRepository(db_session), AuditLogRepository(db_session)).top_up(
        user_id, 500.0
    )
    svc = RideService(
        RideRepository(db_session),
        dock_repo,
        VehicleRepository(db_session),
        WalletService(WalletRepository(db_session), AuditLogRepository(db_session)),
        AuditLogRepository(db_session),
        redis_client=redis_mock,
    )
    return dock.id, user_id, svc


async def _scan(client, dock_id, jpeg):
    return await client.post(
        f"/api/v1/docks/{dock_id}/scan", headers={"Content-Type": "image/jpeg"}, content=jpeg
    )


def _history(debug_dir, prefix):
    return sorted(p for p in debug_dir.glob(f"{prefix}_*.jpg"))


async def test_success_scan_saves_latest_and_success_history(
    client, db_session, redis_mock, debug_scan_dir
):
    dock_id, user_id, svc = await _dock_user_and_service(db_session, redis_mock)
    qr = await svc.request_ride_token(user_id, dock_id)
    jpeg = frame_with_qr(qr.ride_token)

    resp = await _scan(client, dock_id, jpeg)

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACTIVE"
    assert (debug_scan_dir / "latest.jpg").read_bytes() == jpeg
    hist = _history(debug_scan_dir, "success")
    assert len(hist) == 1 and hist[0].read_bytes() == jpeg
    assert not _history(debug_scan_dir, "failure")
    # Old behaviour is gone.
    assert not (debug_scan_dir / "last_success.jpg").exists()
    assert not (debug_scan_dir / "last_fail.jpg").exists()


async def test_latest_tracks_current_frame_and_history_is_never_overwritten(
    client, db_session, redis_mock, debug_scan_dir
):
    dock_id, _, _ = await _dock_user_and_service(db_session, redis_mock)
    frame1, frame2 = frame_without_qr(seed=1), frame_without_qr(seed=2)
    assert frame1 != frame2

    r1 = await _scan(client, dock_id, frame1)
    assert r1.json()["error"]["code"] == "DOCK_SCAN_QR_NOT_FOUND"
    assert (debug_scan_dir / "latest.jpg").read_bytes() == frame1
    first = _history(debug_scan_dir, "failure")
    assert len(first) == 1

    await _scan(client, dock_id, frame2)
    assert (debug_scan_dir / "latest.jpg").read_bytes() == frame2  # latest changed
    after = _history(debug_scan_dir, "failure")
    assert len(after) == 2                                          # one file per frame
    assert first[0] in after and first[0].read_bytes() == frame1    # first one intact


async def test_same_millisecond_frames_do_not_collide(
    client, db_session, redis_mock, debug_scan_dir, monkeypatch
):
    from datetime import datetime

    from app.dock_vision import router as vision_router

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 8, 12, 34, 56, 123000)

    monkeypatch.setattr(vision_router, "datetime", FixedDatetime)
    dock_id, _, _ = await _dock_user_and_service(db_session, redis_mock)
    a, b = frame_without_qr(seed=1), frame_without_qr(seed=2)
    await _scan(client, dock_id, a)
    await _scan(client, dock_id, b)

    names = sorted(p.name for p in _history(debug_scan_dir, "failure"))
    assert names == ["failure_20261008_123456_123.jpg", "failure_20261008_123456_123_1.jpg"]
    assert (debug_scan_dir / names[0]).read_bytes() == a


async def test_undersized_frame_is_still_saved(client, debug_scan_dir):
    tiny = b"\xff\xd8" * 100
    resp = await _scan(client, uuid.uuid4(), tiny)
    assert resp.status_code == 422
    assert (debug_scan_dir / "latest.jpg").read_bytes() == tiny
    assert len(_history(debug_scan_dir, "failure")) == 1


# ── Error-code semantics: undecodable ≠ decoded-but-rejected ─────────────────

async def test_no_qr_is_qr_not_found(client, debug_scan_dir):
    resp = await _scan(client, DOCK, frame_without_qr())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "DOCK_SCAN_QR_NOT_FOUND"


async def test_invalid_qr_content_is_token_invalid(client, debug_scan_dir):
    resp = await _scan(client, DOCK, frame_with_qr("definitely-not-a-jwt"))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "RIDE_TOKEN_INVALID"
    assert len(_history(debug_scan_dir, "failure")) == 1  # decoded but rejected → failure_


async def test_expired_jwt_in_qr_is_token_expired(client, debug_scan_dir):
    expired = make_ride_jwt(DOCK, ttl_seconds=-60)
    resp = await _scan(client, DOCK, frame_with_qr(expired))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "RIDE_TOKEN_EXPIRED"
    assert len(_history(debug_scan_dir, "failure")) == 1


async def test_qr_for_other_dock_is_dock_mismatch(client, db_session, redis_mock, debug_scan_dir):
    dock_id, user_id, svc = await _dock_user_and_service(db_session, redis_mock)
    qr = await svc.request_ride_token(user_id, dock_id)
    other_dock = uuid.uuid4()
    resp = await _scan(client, other_dock, frame_with_qr(qr.ride_token))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RIDE_DOCK_MISMATCH"


async def test_reused_qr_is_rejected(client, db_session, redis_mock, debug_scan_dir):
    dock_id, user_id, svc = await _dock_user_and_service(db_session, redis_mock)
    qr = await svc.request_ride_token(user_id, dock_id)
    jpeg = frame_with_qr(qr.ride_token)

    assert (await _scan(client, dock_id, jpeg)).status_code == 200
    second = await _scan(client, dock_id, jpeg)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "RIDE_TOKEN_REUSED"
    assert len(_history(debug_scan_dir, "success")) == 1
    assert len(_history(debug_scan_dir, "failure")) == 1
