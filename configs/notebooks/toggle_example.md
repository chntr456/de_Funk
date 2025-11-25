---
id: toggle_example
title: Toggle Containers Example
description: Demonstrates the new toggle container system and editable blocks
models: []
author: System
created: 2025-11-25
tags: [example, toggle, demo]
---

# Toggle Container Demo

This notebook demonstrates the new toggle container system that replaces `st.expander` to avoid nesting issues.

## Features Demonstrated

1. **Toggle Containers** - Click to expand/collapse sections
2. **Editable Blocks** - Enable block editing mode to edit individual sections
3. **Nested Content** - Toggle containers work at any depth without UI issues

## Basic Toggle Sections

This paragraph will be wrapped in a toggle container in view mode. Click the toggle button to expand it.

<details>
<summary>Click here to see a collapsible section</summary>

This content is inside a collapsible section using the `<details>` HTML tag.

You can put any markdown content here:
- Lists
- **Bold text**
- *Italic text*
- `Code snippets`

And even nested toggles work fine now!

</details>

## Another Section

Here's more content that demonstrates the clean separation between blocks.

<details>
<summary>Technical Details</summary>

### How Toggle Containers Work

The `ToggleContainer` component uses Streamlit session state to track open/closed status:

```python
with ToggleContainer("Section Title", expanded=False) as tc:
    if tc.is_open:
        st.write("Content here")
```

**Benefits:**
- No nesting issues (unlike st.expander)
- Consistent styling across the app
- Multiple style options: "default", "minimal", "card"
- Persistent state across reruns

</details>

## Block Editing Guide

When you enable **Block Editing Mode** (click the grid icon in the toolbar):

1. Each markdown block gets an edit button
2. Click the edit button to modify that block inline
3. See a live preview as you type
4. Save or cancel your changes

This makes it easy to update specific parts of a notebook without editing the entire file.
