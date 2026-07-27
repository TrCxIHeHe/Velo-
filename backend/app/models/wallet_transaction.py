"""
Compatibility shim.

WalletTransaction was moved into app.models.wallet alongside the Wallet model
so both ORM classes share the same module and relationship declarations.

Any code that does `from app.models.wallet_transaction import WalletTransaction`
continues to work via this re-export.
"""
from app.models.wallet import WalletTransaction  # noqa: F401

__all__ = ["WalletTransaction"]
