"""
Block editing callback handlers.

Handles notebook block operations:
- Edit: Update existing block content
- Insert: Add new blocks
- Delete: Remove blocks
- Header Edit: Update header text
"""

import streamlit as st
import re
from pathlib import Path
from typing import Tuple, Any, Optional


def _get_active_notebook() -> Optional[Tuple[str, str, Any]]:
    """Get the currently active notebook from session state."""
    active_tab = st.session_state.get('active_tab')
    if not active_tab:
        return None

    open_tabs = st.session_state.get('open_tabs', [])
    for tab in open_tabs:
        if tab[0] == active_tab:
            return tab

    return None


def _resolve_notebook_path(notebook_path: str, repo_root: Path) -> Path:
    """Resolve notebook path to absolute path."""
    path = Path(notebook_path)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _reload_notebook(notebook_path: str, notebook_id: str, notebook_manager) -> None:
    """Reload notebook and update session state."""
    updated_config = notebook_manager.load_notebook(notebook_path)

    # Update the tab with new config
    for i, (tab_id, tab_path, tab_config) in enumerate(st.session_state.open_tabs):
        if tab_id == notebook_id:
            st.session_state.open_tabs[i] = (tab_id, tab_path, updated_config)
            break


def handle_block_edit(
    block_index: int,
    new_content: str,
    repo_root: Path,
    notebook_manager
) -> bool:
    """
    Handle block edit from the renderer.

    Uses content-based find/replace to save changes.
    Handles whitespace normalization for robust matching.

    Args:
        block_index: Index of the block (unused, kept for interface compatibility)
        new_content: New content for the block
        repo_root: Path to repository root
        notebook_manager: NotebookManager instance

    Returns:
        True if successful, False otherwise
    """
    active_notebook = _get_active_notebook()
    if not active_notebook:
        st.error("No active notebook")
        return False

    notebook_id, notebook_path, notebook_config = active_notebook

    # Get original content from session state
    original_content = st.session_state.get('_content_to_replace', '')
    if not original_content:
        st.error("No original content found for replacement")
        return False

    try:
        path = _resolve_notebook_path(notebook_path, repo_root)

        # Read current file content
        with open(path, 'r') as f:
            file_content = f.read()

        # Try exact match first
        if original_content in file_content:
            updated_content = file_content.replace(original_content, new_content, 1)
        else:
            # Try normalized matching (handle whitespace differences)
            found = False

            # Try to find the content by matching the first header line
            original_lines = original_content.strip().split('\n')
            if original_lines and original_lines[0].strip().startswith('#'):
                header_line = original_lines[0].strip()

                # Find the header in the file
                file_lines = file_content.split('\n')
                for i, line in enumerate(file_lines):
                    if line.strip() == header_line:
                        # Found the header, find extent of this section
                        header_level = len(header_line) - len(header_line.lstrip('#'))
                        section_start = i
                        section_end = len(file_lines)

                        for j in range(i + 1, len(file_lines)):
                            next_line = file_lines[j].strip()
                            if next_line.startswith('#'):
                                next_level = len(next_line) - len(next_line.lstrip('#'))
                                if next_level <= header_level:
                                    section_end = j
                                    break

                        # Replace this section with new content
                        new_lines = file_lines[:section_start] + new_content.split('\n') + file_lines[section_end:]
                        updated_content = '\n'.join(new_lines)
                        found = True
                        break

                if not found:
                    st.error(f"Could not find section '{header_line}' in file")
                    return False
            else:
                st.error("Could not find original content in file (no header match)")
                return False

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Clear session state
        if '_content_to_replace' in st.session_state:
            del st.session_state['_content_to_replace']
        if '_new_content' in st.session_state:
            del st.session_state['_new_content']

        # Reload the notebook
        _reload_notebook(str(notebook_path), notebook_id, notebook_manager)
        st.success("Section saved!")
        return True

    except Exception as e:
        st.error(f"Error saving block: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False


def handle_block_insert(
    after_index: int,
    block_type: str,
    content: str,
    repo_root: Path,
    notebook_manager
) -> bool:
    """
    Handle block insert from the renderer.

    Args:
        after_index: Index after which to insert (-1 for start, 999 for end)
        block_type: Type of block ('markdown', 'exhibit', 'collapsible')
        content: Content for the new block
        repo_root: Path to repository root
        notebook_manager: NotebookManager instance

    Returns:
        True if successful, False otherwise
    """
    active_notebook = _get_active_notebook()
    if not active_notebook:
        st.error("No active notebook")
        return False

    notebook_id, notebook_path, notebook_config = active_notebook

    try:
        path = _resolve_notebook_path(notebook_path, repo_root)

        # Read current file content
        with open(path, 'r') as f:
            file_content = f.read()

        # Append new content to end of file
        new_content = f"\n\n{content}"
        updated_content = file_content.rstrip() + new_content

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Reload the notebook
        _reload_notebook(str(notebook_path), notebook_id, notebook_manager)
        st.success(f"New section added!")
        return True

    except Exception as e:
        st.error(f"Error inserting block: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False


def handle_block_delete(
    block_index: int,
    repo_root: Path,
    notebook_manager
) -> bool:
    """
    Handle block delete from the renderer.

    Args:
        block_index: Index of the block (unused, kept for interface compatibility)
        repo_root: Path to repository root
        notebook_manager: NotebookManager instance

    Returns:
        True if successful, False otherwise
    """
    active_notebook = _get_active_notebook()
    if not active_notebook:
        st.error("No active notebook")
        return False

    notebook_id, notebook_path, notebook_config = active_notebook

    # Get content to delete from session state
    content_to_delete = st.session_state.get('_content_to_delete', '')
    if not content_to_delete:
        st.error("No content selected for deletion")
        return False

    try:
        path = _resolve_notebook_path(notebook_path, repo_root)

        # Read current file content
        with open(path, 'r') as f:
            file_content = f.read()

        # Try exact match first
        if content_to_delete in file_content:
            updated_content = file_content.replace(content_to_delete, '', 1)
        else:
            # Try header-based matching
            delete_lines = content_to_delete.strip().split('\n')
            if delete_lines and delete_lines[0].strip().startswith('#'):
                header_line = delete_lines[0].strip()
                header_level = len(header_line) - len(header_line.lstrip('#'))

                # Find and remove the section
                file_lines = file_content.split('\n')
                found = False

                for i, line in enumerate(file_lines):
                    if line.strip() == header_line:
                        section_start = i
                        section_end = len(file_lines)

                        for j in range(i + 1, len(file_lines)):
                            next_line = file_lines[j].strip()
                            if next_line.startswith('#'):
                                next_level = len(next_line) - len(next_line.lstrip('#'))
                                if next_level <= header_level:
                                    section_end = j
                                    break

                        # Remove this section
                        new_lines = file_lines[:section_start] + file_lines[section_end:]
                        updated_content = '\n'.join(new_lines)
                        found = True
                        break

                if not found:
                    st.error(f"Could not find section '{header_line}' to delete")
                    return False
            else:
                st.error("Could not find content to delete in file")
                return False

        # Clean up extra blank lines
        updated_content = re.sub(r'\n{3,}', '\n\n', updated_content)
        updated_content = updated_content.strip() + '\n'

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Clear session state
        if '_content_to_delete' in st.session_state:
            del st.session_state['_content_to_delete']

        # Reload the notebook
        _reload_notebook(str(notebook_path), notebook_id, notebook_manager)
        st.success("Section deleted!")
        return True

    except Exception as e:
        st.error(f"Error deleting block: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False


def handle_header_edit(
    block_index: int,
    new_header: str,
    repo_root: Path,
    notebook_manager
) -> bool:
    """
    Handle header edit from the renderer.

    Updates the header text in the markdown block while preserving
    the header level and rest of the content.

    Args:
        block_index: Index of the block containing the header
        new_header: New header text (without # symbols)
        repo_root: Path to repository root
        notebook_manager: NotebookManager instance

    Returns:
        True if successful, False otherwise
    """
    active_notebook = _get_active_notebook()
    if not active_notebook:
        st.error("No active notebook")
        return False

    notebook_id, notebook_path, notebook_config = active_notebook

    # Get content blocks
    if not hasattr(notebook_config, '_content_blocks') or not notebook_config._content_blocks:
        st.error("Notebook has no content blocks")
        return False

    content_blocks = notebook_config._content_blocks

    # Find the block with this header
    if block_index >= len(content_blocks):
        st.error(f"Invalid block index: {block_index}")
        return False

    block = content_blocks[block_index]
    if block.get('type') != 'markdown':
        st.error("Block is not markdown")
        return False

    content = block.get('content', '')
    lines = content.split('\n')

    if not lines or not lines[0].strip().startswith('#'):
        st.error("Block does not start with a header")
        return False

    # Get the header level (number of # symbols)
    old_header_line = lines[0]
    header_level = len(old_header_line) - len(old_header_line.lstrip('#'))

    # Build new header line
    new_header_line = '#' * header_level + ' ' + new_header

    # Replace in the block content
    new_lines = [new_header_line] + lines[1:]
    new_content = '\n'.join(new_lines)

    try:
        path = _resolve_notebook_path(notebook_path, repo_root)

        # Read current file content
        with open(path, 'r') as f:
            file_content = f.read()

        # Replace the old header line with new one
        updated_content = file_content.replace(old_header_line, new_header_line, 1)

        # Write back
        with open(path, 'w') as f:
            f.write(updated_content)

        # Reload the notebook
        _reload_notebook(str(notebook_path), notebook_id, notebook_manager)
        st.success("Header updated!")
        return True

    except Exception as e:
        st.error(f"Error updating header: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False
