"""
Consolidated Python Utility Package
====================================
A unified, standardised toolkit for AI and data-driven projects.

Modules
-------
- history   : Fetch & replay previous sessions (SQL + MongoDB)
- logging   : Structured, auditable logging
- config    : Centralised configuration management
- utils     : Shared helpers and type definitions
"""

from consolidated_utility.history import HistoryManager, HistoryEntry, SessionReplay
from consolidated_utility.logging import AuditLogger
from consolidated_utility.config import Settings, get_settings

__version__ = "1.0.0"
__all__ = [
    "HistoryManager",
    "HistoryEntry",
    "SessionReplay",
    "AuditLogger",
    "Settings",
    "get_settings",
]
