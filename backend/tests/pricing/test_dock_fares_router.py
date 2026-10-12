"""Admin CRUD for /admin/dock-fares: authorization, validation, uniqueness."""
import uuid

from sqlalchemy import select

from app.models import AuditLog

URL = "/api/v1/admin/dock-fares"


async def test_requires_authentication(client):
    assert (await client.get(URL)).status_code == 401
    assert (await client.post(URL, json={})).status_code == 401


async def test_regular_user_is_forbidden(client, world):
    a, b = await world.dock("A"), await world.dock("B")
    body = {"origin_dock_id": str(a), "destination_dock_id": str(b), "amount": "20.00"}
    assert (await client.post(URL, json=body, headers=world.headers)).status_code == 403
    assert (await client.get(URL, headers=world.headers)).status_code == 403


async def test_admin_creates_lists_and_updates(client, world, admin_headers, db_session):
    a, b = await world.dock("A"), await world.dock("B")
    created = await client.post(
        URL, headers=admin_headers,
        json={"origin_dock_id": str(a), "destination_dock_id": str(b), "amount": "20.50"},
    )
    assert created.status_code == 201, created.text
    fare = created.json()["data"]
    assert fare["amount"] == 20.5 and fare["currency"] == "INR" and fare["is_active"] is True
    assert fare["created_at"].endswith("Z")

    # reverse direction is a separate, independently priced row
    rev = await client.post(
        URL, headers=admin_headers,
        json={"origin_dock_id": str(b), "destination_dock_id": str(a), "amount": "31"},
    )
    assert rev.status_code == 201 and rev.json()["data"]["amount"] == 31.0

    listed = (await client.get(URL, headers=admin_headers)).json()["data"]
    assert {(f["origin_dock_id"], f["amount"]) for f in listed} == {(str(a), 20.5), (str(b), 31.0)}
    only_ab = (await client.get(f"{URL}?origin_dock_id={a}", headers=admin_headers)).json()["data"]
    assert len(only_ab) == 1

    upd = await client.patch(
        f"{URL}/{fare['id']}", headers=admin_headers, json={"amount": "22.00", "is_active": False}
    )
    assert upd.status_code == 200
    assert upd.json()["data"]["amount"] == 22.0 and upd.json()["data"]["is_active"] is False

    actions = {r.action for r in (await db_session.execute(select(AuditLog))).scalars()}
    assert {"DOCK_FARE_CREATED", "DOCK_FARE_UPDATED"} <= actions


async def test_duplicate_directed_pair_is_rejected(client, world, admin_headers):
    a, b = await world.dock("A"), await world.dock("B")
    body = {"origin_dock_id": str(a), "destination_dock_id": str(b), "amount": "20"}
    assert (await client.post(URL, json=body, headers=admin_headers)).status_code == 201
    dup = await client.post(URL, json=body, headers=admin_headers)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "FARE_ALREADY_EXISTS"


async def test_validation(client, world, admin_headers):
    a, b = await world.dock("A"), await world.dock("B")
    post = lambda **kw: client.post(
        URL, headers=admin_headers,
        json={"origin_dock_id": str(a), "destination_dock_id": str(b), **kw},
    )
    assert (await post(amount="0")).status_code == 422
    assert (await post(amount="-5")).status_code == 422
    assert (await post(amount="12.345")).status_code == 422       # no silent rounding
    assert (await post(amount="20", currency="RUPEES")).status_code == 422

    same = await client.post(
        URL, headers=admin_headers,
        json={"origin_dock_id": str(a), "destination_dock_id": str(a), "amount": "20"},
    )
    assert same.status_code == 400 and same.json()["error"]["code"] == "FARE_INVALID_PAIR"

    ghost = await client.post(
        URL, headers=admin_headers,
        json={"origin_dock_id": str(a), "destination_dock_id": str(uuid.uuid4()), "amount": "20"},
    )
    assert ghost.status_code == 404 and ghost.json()["error"]["code"] == "DOCK_NOT_FOUND"


async def test_update_unknown_fare_is_404(client, admin_headers):
    r = await client.patch(f"{URL}/{uuid.uuid4()}", headers=admin_headers, json={"amount": "9"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "FARE_NOT_FOUND"
