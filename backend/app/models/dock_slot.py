"""
Compatibility shim.

DockSlot was consolidated into app.models.dock alongside Dock and Vehicle
so all three ORM classes share the same module and relationship declarations.

Any code that does `from app.models.dock_slot import DockSlot`
continues to work via this re-export.
"""
from app.models.dock import DockSlot  # noqa: F401

__all__ = ["DockSlot"]
