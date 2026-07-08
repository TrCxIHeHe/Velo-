"""Cross-dialect UUID column type.

WHY THIS FILE EXISTS
---------------------
Every model originally used `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`
directly. That type is correct and native on real PostgreSQL, but on SQLite
(which is what the whole test suite runs against — see tests/conftest.py)
it falls back to a plain CHAR(32) column with no explicit TEXT affinity
enforcement.

SQLite's storage engine is dynamically typed: an "empty" or ambiguous
affinity column will silently store a value as INTEGER/REAL instead of TEXT
if the text happens to look like a pure number. A UUID like
`11111111-1111-1111-1111-111111111111` has hex digits (after removing
hyphens) that are all numeric characters — no a-f letters — so on SQLite it
got silently stored as the number 1.111...e+31 instead of the string, and
came back corrupted on the next read. This is NOT a hypothetical: it
reproduced immediately in tests/dock/test_dock_router.py the first time a
randomly-generated UUID happened to be all-digits.

THE FIX
-------
A small TypeDecorator that:
  * On PostgreSQL: delegates to the native, fully-correct UUID type.
  * On every other backend (SQLite in tests): stores as CHAR(36) using the
    UUID's canonical hyphenated string form (`str(uuid_obj)`), which always
    contains at least one letter (a-f) or is unambiguously non-numeric
    in every UUID version we generate (uuid4), AND declares TEXT affinity
    explicitly via CHAR, so SQLite never attempts numeric coercion.

This is the standard, documented pattern for "give me a UUID column that
behaves identically on Postgres and SQLite" — see SQLAlchemy's own
"Backend-agnostic GUID Type" recipe in their docs.

USAGE
-----
Replace `from sqlalchemy.dialects.postgresql import UUID` +
`UUID(as_uuid=True)` in model files with:

    from app.types import GUID
    ...
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value)  # canonical hyphenated form — always non-numeric

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
