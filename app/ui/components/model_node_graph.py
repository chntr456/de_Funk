"""
Hierarchical Model Node Graph - Visualize models with dependencies and inheritance.

Provides an interactive visualization for the splash screen showing:
- Models as parent nodes with dimensions/facts as children
- Dependency edges (depends_on) showing runtime dependencies
- Inheritance edges (inherits_from) showing template relationships
- Cross-model relationship edges (via ticker, date, etc.)
- Hierarchical layout to minimize edge crossings

Uses Plotly for interactive network diagrams with hover tooltips.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple, Set
import math
import yaml
from pathlib import Path


def render_model_node_graph(
    registry,
    show_tables: bool = True,
    height: int = 500
):
    """
    Render hierarchical model graph for splash screen.

    Args:
        registry: ModelRegistry instance
        show_tables: Whether to show dimension/fact sub-nodes
        height: Chart height in pixels
    """
    models = registry.list_models()

    if not models:
        st.info("No models found in registry")
        return

    # Build graph data with dependencies and inheritance
    nodes, edges, model_metadata = _build_graph_data(registry, models, show_tables)

    if not nodes:
        st.info("No model data available")
        return

    # Calculate hierarchical layout positions
    positions = _calculate_hierarchical_layout(nodes, models, model_metadata, show_tables)

    # Create Plotly figure
    fig = _create_figure(nodes, edges, positions, height)

    # Render
    st.plotly_chart(fig, use_container_width=True, key="model_node_graph")

    # Legend
    _render_legend()


def _build_graph_data(
    registry,
    models: List[str],
    show_tables: bool
) -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Build nodes and edges for the graph including dependencies and inheritance.

    Returns:
        Tuple of (nodes list, edges list, model_metadata dict)
    """
    nodes = []
    edges = []
    model_metadata = {}  # Store depends_on, inherits_from for each model

    # First pass: collect all model metadata
    for model_name in models:
        try:
            model_config = registry.get_model(model_name)

            # Try to get full config with depends_on and inherits_from
            try:
                full_config = registry.get_model_config(model_name)
                depends_on = full_config.get('depends_on', [])
                inherits_from = full_config.get('inherits_from', '')
            except Exception:
                depends_on = []
                inherits_from = ''

            model_metadata[model_name] = {
                'depends_on': depends_on if isinstance(depends_on, list) else [],
                'inherits_from': inherits_from,
                'config': model_config
            }
        except Exception:
            continue

    # Calculate depth (tier) for each model based on dependencies
    depths = _calculate_depths(model_metadata)

    # Second pass: build nodes and edges
    for model_name in models:
        if model_name not in model_metadata:
            continue

        metadata = model_metadata[model_name]
        model_config = metadata['config']

        dims = model_config.list_dimensions()
        facts = model_config.list_facts()

        # Add model node
        nodes.append({
            'id': model_name,
            'label': model_name,
            'type': 'model',
            'dims': len(dims),
            'facts': len(facts),
            'tables': dims + facts,
            'depth': depths.get(model_name, 0),
            'depends_on': metadata['depends_on'],
            'inherits_from': metadata['inherits_from']
        })

        # Add dimension/fact nodes if showing tables
        if show_tables:
            for dim in dims:
                node_id = f"{model_name}.{dim}"
                nodes.append({
                    'id': node_id,
                    'label': dim.replace('dim_', ''),
                    'type': 'dimension',
                    'parent': model_name,
                    'full_name': dim
                })
                edges.append({
                    'source': model_name,
                    'target': node_id,
                    'type': 'contains'
                })

            for fact in facts:
                node_id = f"{model_name}.{fact}"
                nodes.append({
                    'id': node_id,
                    'label': fact.replace('fact_', ''),
                    'type': 'fact',
                    'parent': model_name,
                    'full_name': fact
                })
                edges.append({
                    'source': model_name,
                    'target': node_id,
                    'type': 'contains'
                })

        # Add dependency edges (depends_on)
        for dep in metadata['depends_on']:
            if dep in models:
                edges.append({
                    'source': model_name,
                    'target': dep,
                    'type': 'dependency',
                    'label': 'depends_on'
                })

        # Add inheritance edges (inherits_from)
        if metadata['inherits_from']:
            # Parse inherits_from like "_base.securities"
            base_name = metadata['inherits_from'].replace('_base.', '')
            edges.append({
                'source': model_name,
                'target': f"_base_{base_name}",
                'type': 'inheritance',
                'label': 'inherits'
            })

        # Add cross-model relationship edges from graph config
        for edge in model_config.get_edges():
            if 'to' in edge:
                target_model = edge['to'].split('.')[0]
                if target_model in models and target_model != model_name:
                    via = edge.get('via', edge.get('on', [''])[0].split('=')[0] if edge.get('on') else '')
                    # Avoid duplicate edges
                    edge_key = (model_name, target_model, 'relationship')
                    existing = [e for e in edges if (e['source'], e['target'], e['type']) == edge_key]
                    if not existing:
                        edges.append({
                            'source': model_name,
                            'target': target_model,
                            'type': 'relationship',
                            'label': via
                        })

    # Add base template nodes if any model inherits from them
    base_templates = set()
    for model_name, metadata in model_metadata.items():
        if metadata['inherits_from']:
            base_name = metadata['inherits_from'].replace('_base.', '')
            base_templates.add(base_name)

    for base_name in base_templates:
        node_id = f"_base_{base_name}"
        nodes.append({
            'id': node_id,
            'label': base_name,
            'type': 'base_template',
            'depth': -1  # Base templates at top
        })

    return nodes, edges, model_metadata


def _calculate_depths(model_metadata: Dict) -> Dict[str, int]:
    """
    Calculate dependency depth for each model using topological sort.

    Depth 0: Models with no dependencies (core)
    Depth 1: Models that only depend on depth 0
    Depth N: Models that depend on depth N-1
    """
    depths = {}
    remaining = set(model_metadata.keys())

    # Iteratively assign depths
    current_depth = 0
    max_iterations = len(remaining) + 1

    while remaining and max_iterations > 0:
        max_iterations -= 1
        assigned_this_round = set()

        for model_name in remaining:
            deps = model_metadata[model_name]['depends_on']
            # Filter to only models that exist in our set
            valid_deps = [d for d in deps if d in model_metadata]

            if not valid_deps:
                # No dependencies - assign current depth
                depths[model_name] = current_depth
                assigned_this_round.add(model_name)
            elif all(d in depths for d in valid_deps):
                # All dependencies have been assigned
                depths[model_name] = current_depth
                assigned_this_round.add(model_name)

        remaining -= assigned_this_round
        if assigned_this_round:
            current_depth += 1

    # Assign remaining (circular deps) to max depth
    for model_name in remaining:
        depths[model_name] = current_depth

    return depths


def _calculate_hierarchical_layout(
    nodes: List[Dict],
    models: List[str],
    model_metadata: Dict,
    show_tables: bool
) -> Dict[str, Tuple[float, float]]:
    """
    Calculate hierarchical layout positions (Sugiyama-style).

    - Base templates at top (y=3)
    - Tier 0 (core) below (y=2)
    - Tier 1 (company) below (y=1)
    - Tier 2+ (stocks, options, etc.) at bottom (y=0, -1)
    """
    positions = {}

    # Group models by depth
    depth_groups = {}
    base_templates = []

    for node in nodes:
        if node['type'] == 'base_template':
            base_templates.append(node['id'])
        elif node['type'] == 'model':
            depth = node.get('depth', 0)
            if depth not in depth_groups:
                depth_groups[depth] = []
            depth_groups[depth].append(node['id'])

    # Layout base templates at the top
    if base_templates:
        y = 2.5
        width = len(base_templates)
        for i, template_id in enumerate(base_templates):
            x = (i - (width - 1) / 2) * 1.5
            positions[template_id] = (x, y)

    # Layout models by depth tier
    max_depth = max(depth_groups.keys()) if depth_groups else 0

    for depth, model_list in sorted(depth_groups.items()):
        # Y position: higher depth = lower on screen
        y = 1.5 - (depth * 1.2)

        # X position: spread horizontally
        width = len(model_list)
        for i, model_id in enumerate(model_list):
            x = (i - (width - 1) / 2) * 2.0
            positions[model_id] = (x, y)

    # Layout table nodes around their parent models
    if show_tables:
        for node in nodes:
            if node['type'] in ('dimension', 'fact'):
                parent = node.get('parent')
                if parent and parent in positions:
                    parent_x, parent_y = positions[parent]

                    # Get all siblings
                    siblings = [n for n in nodes
                               if n.get('parent') == parent and n['type'] in ('dimension', 'fact')]
                    num_siblings = len(siblings)

                    if num_siblings == 0:
                        continue

                    # Find this node's index
                    try:
                        idx = next(i for i, n in enumerate(siblings) if n['id'] == node['id'])
                    except StopIteration:
                        continue

                    # Position tables in a small arc below the model
                    table_radius = 0.4
                    spread = min(math.pi * 0.6, math.pi * 0.15 * num_siblings)
                    base_angle = -math.pi / 2  # Point downward

                    if num_siblings == 1:
                        angle = base_angle
                    else:
                        angle = base_angle - spread / 2 + (spread * idx / (num_siblings - 1))

                    x = parent_x + table_radius * math.cos(angle)
                    y = parent_y + table_radius * math.sin(angle)
                    positions[node['id']] = (x, y)

    return positions


def _create_figure(
    nodes: List[Dict],
    edges: List[Dict],
    positions: Dict[str, Tuple[float, float]],
    height: int
) -> go.Figure:
    """Create Plotly figure with nodes and edges."""
    fig = go.Figure()

    # Draw edges with different styles
    edge_styles = {
        'contains': {'color': 'rgba(150, 150, 150, 0.3)', 'width': 1, 'dash': 'dot'},
        'dependency': {'color': 'rgba(70, 130, 180, 0.7)', 'width': 2, 'dash': 'solid'},
        'inheritance': {'color': 'rgba(255, 140, 0, 0.7)', 'width': 2, 'dash': 'dash'},
        'relationship': {'color': 'rgba(50, 205, 50, 0.6)', 'width': 1.5, 'dash': 'dot'},
    }

    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']

        if source_id not in positions or target_id not in positions:
            continue

        x0, y0 = positions[source_id]
        x1, y1 = positions[target_id]

        style = edge_styles.get(edge['type'], edge_styles['dependency'])

        # For non-contains edges, draw curved lines to reduce crossings
        if edge['type'] != 'contains':
            # Create a bezier-like curve using intermediate points
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2

            # Offset the midpoint perpendicular to the line
            dx = x1 - x0
            dy = y1 - y0
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                # Perpendicular offset (curve amount)
                offset = 0.15 * length
                perp_x = -dy / length * offset
                perp_y = dx / length * offset
                mid_x += perp_x
                mid_y += perp_y

            # Draw as quadratic bezier approximation (3 points)
            fig.add_trace(go.Scatter(
                x=[x0, mid_x, x1],
                y=[y0, mid_y, y1],
                mode='lines',
                line=dict(
                    width=style['width'],
                    color=style['color'],
                    dash=style['dash'],
                    shape='spline',
                    smoothing=1.3
                ),
                hoverinfo='text',
                hovertext=f"{source_id} → {target_id}<br>Type: {edge['type']}<br>{edge.get('label', '')}",
                showlegend=False
            ))
        else:
            # Straight lines for contains edges
            fig.add_trace(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=style['width'], color=style['color'], dash=style['dash']),
                hoverinfo='skip',
                showlegend=False
            ))

    # Group nodes by type
    model_nodes = [n for n in nodes if n['type'] == 'model']
    base_nodes = [n for n in nodes if n['type'] == 'base_template']
    dim_nodes = [n for n in nodes if n['type'] == 'dimension']
    fact_nodes = [n for n in nodes if n['type'] == 'fact']

    # Draw base template nodes (orange hexagons)
    if base_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in base_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in base_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=35,
                color='rgba(255, 140, 0, 0.9)',
                line=dict(width=2, color='white'),
                symbol='hexagon'
            ),
            text=[n['label'].upper() for n in base_nodes if n['id'] in positions],
            textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            hoverinfo='text',
            hovertext=[
                f"<b>Base Template: {n['label']}</b><br>"
                f"Provides inheritance for securities models"
                for n in base_nodes if n['id'] in positions
            ],
            showlegend=False
        ))

    # Draw model nodes (blue circles) with depth-based sizing
    if model_nodes:
        sizes = [45 if n.get('depth', 0) == 0 else 38 for n in model_nodes if n['id'] in positions]
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in model_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in model_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=sizes,
                color='rgba(99, 110, 250, 0.9)',
                line=dict(width=2, color='white'),
                symbol='circle'
            ),
            text=[n['label'].upper() for n in model_nodes if n['id'] in positions],
            textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            hoverinfo='text',
            hovertext=[
                f"<b>{n['label']}</b> (Tier {n.get('depth', 0)})<br>"
                f"Dimensions: {n['dims']}<br>"
                f"Facts: {n['facts']}<br>"
                f"Depends on: {', '.join(n.get('depends_on', [])) or 'none'}<br>"
                f"Inherits: {n.get('inherits_from', 'none') or 'none'}"
                for n in model_nodes if n['id'] in positions
            ],
            showlegend=False
        ))

    # Draw dimension nodes
    if dim_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in dim_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in dim_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=16,
                color='rgba(0, 150, 200, 0.8)',
                line=dict(width=1, color='white'),
                symbol='diamond'
            ),
            text=[n['label'][:6] for n in dim_nodes if n['id'] in positions],
            textposition='bottom center',
            textfont=dict(size=6, color='#666'),
            hoverinfo='text',
            hovertext=[
                f"<b>Dimension: {n['full_name']}</b><br>Model: {n['parent']}"
                for n in dim_nodes if n['id'] in positions
            ],
            showlegend=False
        ))

    # Draw fact nodes
    if fact_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in fact_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in fact_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=16,
                color='rgba(0, 200, 100, 0.8)',
                line=dict(width=1, color='white'),
                symbol='square'
            ),
            text=[n['label'][:6] for n in fact_nodes if n['id'] in positions],
            textposition='bottom center',
            textfont=dict(size=6, color='#666'),
            hoverinfo='text',
            hovertext=[
                f"<b>Fact: {n['full_name']}</b><br>Model: {n['parent']}"
                for n in fact_nodes if n['id'] in positions
            ],
            showlegend=False
        ))

    # Layout
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=10, l=10, r=10, t=10),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-4, 4]
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-2.5, 3.5],
            scaleanchor='x',
            scaleratio=1
        ),
        height=height,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig


def _render_legend():
    """Render legend below the graph."""
    cols = st.columns(6)
    with cols[0]:
        st.markdown("🔵 **Model**")
    with cols[1]:
        st.markdown("🟠 **Base**")
    with cols[2]:
        st.markdown("◇ **Dim**")
    with cols[3]:
        st.markdown("◻ **Fact**")
    with cols[4]:
        st.markdown("― **Depends**")
    with cols[5]:
        st.markdown("┅ **Inherits**")


def render_model_summary_cards(registry):
    """
    Render summary cards for each model.
    Alternative to graph visualization - shows models as cards.
    """
    models = registry.list_models()

    if not models:
        st.info("No models found")
        return

    cols = st.columns(min(len(models), 4))

    for i, model_name in enumerate(models):
        col_idx = i % len(cols)

        try:
            model_config = registry.get_model(model_name)
            dims = model_config.list_dimensions()
            facts = model_config.list_facts()
            measures = model_config.list_measures()

            with cols[col_idx]:
                st.markdown(f"""
                <div style='
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem;
                    border-radius: 10px;
                    color: white;
                    margin-bottom: 1rem;
                '>
                    <h4 style='margin: 0 0 0.5rem 0;'>{model_name.upper()}</h4>
                    <p style='margin: 0; font-size: 0.85rem; opacity: 0.9;'>
                        📊 {len(dims)} dims · 📈 {len(facts)} facts · 📐 {len(measures)} measures
                    </p>
                </div>
                """, unsafe_allow_html=True)

        except Exception:
            with cols[col_idx]:
                st.warning(f"Could not load {model_name}")
