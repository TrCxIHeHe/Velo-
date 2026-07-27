"""
Compatibility shim.

Vehicle was consolidated into app.models.dock alongside Dock and DockSlot
so all three ORM classes share the same module and relationship declarations.

Any code that does `from app.models.vehicle import Vehicle`
continues to work via this re-export.
"""
from app.models.dock import Vehicle  # noqa: F401

__all__ = ["Vehicle"]
