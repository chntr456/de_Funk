"""
YAML editor component.

Provides editing interface for notebook YAML files with validation and save.
"""

import streamlit as st
import yaml
from pathlib import Path


def render_yaml_editor(notebook_id: str, notebook_path: Path, notebook_session):
    """
    Render YAML editor for a notebook.

    Args:
        notebook_id: Unique identifier for the notebook
        notebook_path: Path to the notebook YAML file
        notebook_session: NotebookSession for reloading
    """
    st.subheader("📝 Edit Notebook YAML")

    # Get current YAML content
    yaml_content = st.session_state.yaml_content.get(notebook_id, "")

    # Text area for editing
    edited_content = st.text_area(
        "YAML Content",
        value=yaml_content,
        height=600,
        key=f"yaml_editor_{notebook_id}",
    )

    # Save button
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6])

    with col1:
        if st.button("💾 Save", key=f"save_{notebook_id}"):
            try:
                # Validate YAML
                yaml.safe_load(edited_content)

                # Save to file
                with open(notebook_path, 'w') as f:
                    f.write(edited_content)

                # Update session state
                st.session_state.yaml_content[notebook_id] = edited_content

                # Reload notebook
                notebook_config = notebook_session.load_notebook(str(notebook_path))

                # Update open tab
                for i, tab in enumerate(st.session_state.open_tabs):
                    if tab[0] == notebook_id:
                        st.session_state.open_tabs[i] = (notebook_id, notebook_path, notebook_config)
                        break

                st.success("✅ Notebook saved and reloaded!")

            except yaml.YAMLError as e:
                st.error(f"❌ Invalid YAML: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error saving: {str(e)}")

    with col2:
        if st.button("🔄 Reload", key=f"reload_{notebook_id}"):
            with open(notebook_path, 'r') as f:
                st.session_state.yaml_content[notebook_id] = f.read()
            st.rerun()

    # Preview
    st.subheader("📋 YAML Preview")
    st.code(edited_content, language="yaml")
