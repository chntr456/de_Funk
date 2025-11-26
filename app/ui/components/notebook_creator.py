"""
Notebook creator component.

Provides UI for creating new notebooks with templates and metadata.
"""

import streamlit as st
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# Notebook templates
NOTEBOOK_TEMPLATES = {
    "blank": {
        "name": "Blank Notebook",
        "description": "Start with an empty notebook",
        "content": """---
id: {notebook_id}
title: {title}
description: {description}
models: []
author: {author}
created: {created}
tags: []
---

# {title}

{description}

<!-- Add your content below -->

"""
    },
    "data_analysis": {
        "name": "Data Analysis",
        "description": "Template for analyzing data with charts and tables",
        "content": """---
id: {notebook_id}
title: {title}
description: {description}
models: [{model}]
author: {author}
created: {created}
tags: [analysis, data]
---

# {title}

{description}

## Overview

This notebook provides analysis of your data.

## Data Visualization

$exhibits${{
type: line_chart
title: Time Series View
source: {model}.{table}
x: date
y: value
color: category
}}

## Data Table

$exhibits${{
type: data_table
title: Raw Data
source: {model}.{table}
columns: [date, category, value]
pagination: true
page_size: 25
download: true
searchable: true
}}

"""
    },
    "metrics_dashboard": {
        "name": "Metrics Dashboard",
        "description": "Template with KPI cards and summary metrics",
        "content": """---
id: {notebook_id}
title: {title}
description: {description}
models: [{model}]
author: {author}
created: {created}
tags: [dashboard, metrics]
---

# {title}

{description}

## Key Metrics

$exhibits${{
type: metric_cards
title: Summary
source: {model}.{table}
metrics:
  - measure: count
    label: Total Records
  - measure: avg_value
    label: Average Value
}}

## Trend Analysis

$exhibits${{
type: line_chart
title: Trend Over Time
source: {model}.{table}
x: date
y: value
}}

"""
    },
    "stock_analysis": {
        "name": "Stock Analysis",
        "description": "Template for analyzing stock price data",
        "content": """---
id: {notebook_id}
title: {title}
description: {description}
models: [stocks]
author: {author}
created: {created}
tags: [stocks, finance, analysis]
---

# {title}

{description}

$filter${{
id: ticker
label: Stock Ticker
type: select
multi: true
source: {{model: stocks, table: dim_stock, column: ticker}}
default: [AAPL]
help_text: Select stocks to analyze
}}

$filter${{
id: trade_date
label: Date Range
type: date_range
default: {{start: -30d, end: today}}
help_text: Select date range for analysis
}}

## Price Chart

$exhibits${{
type: line_chart
title: Daily Closing Prices
source: stocks.fact_stock_prices
x: trade_date
y: close
color: ticker
}}

## Volume Analysis

$exhibits${{
type: bar_chart
title: Trading Volume
source: stocks.fact_stock_prices
x: trade_date
y: volume
color: ticker
}}

## Price Data

$exhibits${{
type: data_table
title: Price History
source: stocks.fact_stock_prices
columns: [ticker, trade_date, open, high, low, close, volume]
pagination: true
page_size: 50
download: true
sortable: true
}}

"""
    }
}


def sanitize_id(text: str) -> str:
    """
    Convert text to a valid notebook ID.

    Args:
        text: Input text (e.g., title)

    Returns:
        Valid ID (lowercase, underscores, no special chars)
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and hyphens with underscores
    text = re.sub(r'[\s\-]+', '_', text)
    # Remove special characters
    text = re.sub(r'[^a-z0-9_]', '', text)
    # Remove consecutive underscores
    text = re.sub(r'_+', '_', text)
    # Trim underscores from ends
    text = text.strip('_')

    return text or "new_notebook"


def render_notebook_creator(
    notebooks_root: Path,
    available_models: Optional[List[str]] = None,
    on_create: Optional[callable] = None
):
    """
    Render the notebook creation form.

    Args:
        notebooks_root: Root directory for notebooks
        available_models: List of available model names
        on_create: Callback when notebook is created (receives path)
    """
    st.header("Create New Notebook")

    # Template selection
    st.subheader("1. Choose a Template")

    template_options = {k: v["name"] for k, v in NOTEBOOK_TEMPLATES.items()}
    selected_template = st.radio(
        "Template",
        options=list(template_options.keys()),
        format_func=lambda x: template_options[x],
        horizontal=True,
        label_visibility="collapsed"
    )

    # Show template description
    st.caption(NOTEBOOK_TEMPLATES[selected_template]["description"])

    st.divider()

    # Notebook metadata
    st.subheader("2. Notebook Details")

    col1, col2 = st.columns(2)

    with col1:
        title = st.text_input(
            "Title",
            placeholder="My Analysis Notebook",
            help="Display title for the notebook"
        )

    with col2:
        # Auto-generate ID from title
        auto_id = sanitize_id(title) if title else ""
        notebook_id = st.text_input(
            "ID",
            value=auto_id,
            placeholder="my_analysis_notebook",
            help="Unique identifier (auto-generated from title)"
        )

    description = st.text_area(
        "Description",
        placeholder="Brief description of this notebook's purpose",
        height=100
    )

    author = st.text_input(
        "Author",
        placeholder="Your name or email",
        help="Optional author attribution"
    )

    st.divider()

    # Model selection (if template uses models)
    st.subheader("3. Data Source")

    if available_models:
        model = st.selectbox(
            "Primary Model",
            options=[""] + available_models,
            help="Select the main data model for this notebook"
        )
    else:
        model = st.text_input(
            "Model Name",
            placeholder="stocks",
            help="Name of the data model to use"
        )

    table = st.text_input(
        "Default Table",
        placeholder="fact_prices",
        help="Default table within the model"
    )

    st.divider()

    # Location selection
    st.subheader("4. Save Location")

    # Get existing folders
    folders = ["."]  # Root
    for item in notebooks_root.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            folders.append(item.name)

    folder_option = st.radio(
        "Save to:",
        options=["existing", "new"],
        format_func=lambda x: "Existing folder" if x == "existing" else "New folder",
        horizontal=True
    )

    if folder_option == "existing":
        selected_folder = st.selectbox(
            "Folder",
            options=folders,
            format_func=lambda x: "Root" if x == "." else x
        )
        new_folder = None
    else:
        selected_folder = None
        new_folder = st.text_input(
            "New Folder Name",
            placeholder="My Analysis",
            help="Name for the new folder"
        )

    st.divider()

    # Preview
    st.subheader("Preview")

    with st.expander("Show generated content", expanded=False):
        if title:
            preview_content = generate_notebook_content(
                template=selected_template,
                notebook_id=notebook_id,
                title=title,
                description=description,
                author=author,
                model=model or "model",
                table=table or "table"
            )
            st.code(preview_content, language="markdown")
        else:
            st.info("Enter a title to see the preview")

    st.divider()

    # Create button
    col1, col2, col3 = st.columns([0.3, 0.4, 0.3])

    with col2:
        create_disabled = not title or not notebook_id
        if st.button(
            "Create Notebook",
            type="primary",
            use_container_width=True,
            disabled=create_disabled
        ):
            # Determine save path
            if folder_option == "new" and new_folder:
                save_folder = notebooks_root / sanitize_id(new_folder)
                save_folder.mkdir(parents=True, exist_ok=True)
            elif selected_folder and selected_folder != ".":
                save_folder = notebooks_root / selected_folder
            else:
                save_folder = notebooks_root

            # Generate file path
            file_name = f"{notebook_id}.md"
            file_path = save_folder / file_name

            # Check if file exists
            if file_path.exists():
                st.error(f"A notebook with ID '{notebook_id}' already exists in this location")
                return

            # Generate and save content
            try:
                content = generate_notebook_content(
                    template=selected_template,
                    notebook_id=notebook_id,
                    title=title,
                    description=description,
                    author=author,
                    model=model or "model",
                    table=table or "table"
                )

                with open(file_path, 'w') as f:
                    f.write(content)

                st.success(f"Notebook created: {file_path.relative_to(notebooks_root)}")

                # Call callback if provided
                if on_create:
                    on_create(file_path)

            except Exception as e:
                st.error(f"Error creating notebook: {str(e)}")

    if create_disabled:
        st.caption("Enter a title and ID to create the notebook")


def generate_notebook_content(
    template: str,
    notebook_id: str,
    title: str,
    description: str,
    author: str,
    model: str,
    table: str
) -> str:
    """
    Generate notebook content from template.

    Args:
        template: Template key
        notebook_id: Unique notebook ID
        title: Notebook title
        description: Notebook description
        author: Author name
        model: Data model name
        table: Default table name

    Returns:
        Generated markdown content
    """
    template_content = NOTEBOOK_TEMPLATES.get(template, NOTEBOOK_TEMPLATES["blank"])["content"]

    # Format with provided values
    content = template_content.format(
        notebook_id=notebook_id,
        title=title,
        description=description or "Add description here",
        author=author or "Anonymous",
        created=datetime.now().strftime("%Y-%m-%d"),
        model=model,
        table=table
    )

    return content


def render_create_notebook_button(
    notebooks_root: Path,
    available_models: Optional[List[str]] = None
):
    """
    Render a button that opens the notebook creator in a dialog/modal.

    Args:
        notebooks_root: Root directory for notebooks
        available_models: List of available model names
    """
    # Check if creator mode is active
    if 'show_notebook_creator' not in st.session_state:
        st.session_state.show_notebook_creator = False

    if st.button("New Notebook", key="new_notebook_btn", use_container_width=True, type="primary"):
        st.session_state.show_notebook_creator = True
        st.rerun()


def render_notebook_creator_modal(
    notebooks_root: Path,
    available_models: Optional[List[str]] = None,
    on_create: Optional[callable] = None
):
    """
    Render the notebook creator as a modal-like interface.

    Should be called in the main content area when show_notebook_creator is True.

    Args:
        notebooks_root: Root directory for notebooks
        available_models: List of available model names
        on_create: Callback when notebook is created
    """
    # Close button
    col1, col2 = st.columns([0.9, 0.1])
    with col2:
        if st.button("", key="close_creator", help="Close"):
            st.session_state.show_notebook_creator = False
            st.rerun()

    render_notebook_creator(
        notebooks_root=notebooks_root,
        available_models=available_models,
        on_create=on_create
    )
