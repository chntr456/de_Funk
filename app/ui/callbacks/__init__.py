"""
Callback handlers for the notebook application.

Contains event handlers for user interactions like:
- Block editing (create, update, delete)
- Header editing
- Notebook creation
"""

from .block_callbacks import (
    handle_block_edit,
    handle_block_insert,
    handle_block_delete,
    handle_header_edit,
)

__all__ = [
    'handle_block_edit',
    'handle_block_insert',
    'handle_block_delete',
    'handle_header_edit',
]
