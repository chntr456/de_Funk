"""
Hierarchical Model Node Graph - Visualize models with their dimensions and facts.

Provides an interactive visualization for the splash screen showing:
- Models as parent nodes (expandable containers)
- Dimensions as blue child nodes
- Facts as green child nodes
- Cross-model dependencies as edges

Uses Plotly for interactive network diagrams with hover tooltips.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple
import math


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

    # Build graph data
    nodes, edges = _build_graph_data(registry, models, show_tables)

    if not nodes:
        st.info("No model data available")
        return

    # Calculate layout positions
    positions = _calculate_layout(nodes, models, show_tables)

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
) -> Tuple[List[Dict], List[Dict]]:
    """
    Build nodes and edges for the graph.

    Returns:
        Tuple of (nodes list, edges list)
    """
    nodes = []
    edges = []

    for model_name in models:
        try:
            model_config = registry.get_model(model_name)
        except Exception:
            continue

        # Add model node
        dims = model_config.list_dimensions()
        facts = model_config.list_facts()

        nodes.append({
            'id': model_name,
            'label': model_name,
            'type': 'model',
            'dims': len(dims),
            'facts': len(facts),
            'tables': dims + facts
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

        # Add cross-model edges (from graph config)
        for edge in model_config.get_edges():
            if 'from' in edge and 'to' in edge:
                # Check if target model exists
                target_model = edge['to'].split('.')[0]
                if target_model in models:
                    edges.append({
                        'source': model_name,
                        'target': target_model,
                        'type': 'dependency',
                        'label': edge.get('via', '')
                    })

    return nodes, edges


def _calculate_layout(
    nodes: List[Dict],
    models: List[str],
    show_tables: bool
) -> Dict[str, Tuple[float, float]]:
    """
    Calculate node positions using a hierarchical circular layout.

    Models arranged in a circle, with their tables arranged around them.
    """
    positions = {}
    num_models = len(models)

    if num_models == 0:
        return positions

    # Arrange models in a circle
    model_radius = 2.0
    for i, model in enumerate(models):
        angle = 2 * math.pi * i / num_models - math.pi / 2  # Start from top
        x = model_radius * math.cos(angle)
        y = model_radius * math.sin(angle)
        positions[model] = (x, y)

    # Arrange tables around their parent model
    if show_tables:
        table_radius = 0.5  # Distance from parent model

        for node in nodes:
            if node['type'] in ('dimension', 'fact'):
                parent = node.get('parent')
                if parent and parent in positions:
                    parent_x, parent_y = positions[parent]

                    # Get all siblings
                    siblings = [n for n in nodes
                               if n.get('parent') == parent and n['type'] in ('dimension', 'fact')]
                    num_siblings = len(siblings)

                    # Find this node's index among siblings
                    idx = next(i for i, n in enumerate(siblings) if n['id'] == node['id'])

                    # Calculate angle for this child
                    # Spread children in a semi-circle on the outer side of the model
                    parent_angle = math.atan2(parent_y, parent_x)
                    spread = math.pi * 0.8  # 144 degrees spread
                    child_angle = parent_angle - spread/2 + (spread * idx / max(num_siblings - 1, 1))

                    x = parent_x + table_radius * math.cos(child_angle)
                    y = parent_y + table_radius * math.sin(child_angle)
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

    # Add edges
    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']

        if source_id not in positions or target_id not in positions:
            continue

        x0, y0 = positions[source_id]
        x1, y1 = positions[target_id]

        # Style based on edge type
        if edge['type'] == 'contains':
            color = 'rgba(150, 150, 150, 0.3)'
            width = 1
            dash = 'dot'
        else:  # dependency
            color = 'rgba(100, 100, 200, 0.6)'
            width = 2
            dash = 'solid'

        fig.add_trace(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=width, color=color, dash=dash),
            hoverinfo='skip',
            showlegend=False
        ))

    # Group nodes by type for consistent styling
    model_nodes = [n for n in nodes if n['type'] == 'model']
    dim_nodes = [n for n in nodes if n['type'] == 'dimension']
    fact_nodes = [n for n in nodes if n['type'] == 'fact']

    # Add model nodes (large, prominent)
    if model_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in model_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in model_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=40,
                color='rgba(99, 110, 250, 0.9)',
                line=dict(width=2, color='white'),
                symbol='circle'
            ),
            text=[n['label'].upper() for n in model_nodes if n['id'] in positions],
            textposition='middle center',
            textfont=dict(size=9, color='white', family='Arial Black'),
            hoverinfo='text',
            hovertext=[
                f"<b>{n['label']}</b><br>"
                f"Dimensions: {n['dims']}<br>"
                f"Facts: {n['facts']}<br>"
                f"Tables: {', '.join(n['tables'][:5])}{'...' if len(n['tables']) > 5 else ''}"
                for n in model_nodes if n['id'] in positions
            ],
            showlegend=False,
            name='Models'
        ))

    # Add dimension nodes (blue, smaller)
    if dim_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in dim_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in dim_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=18,
                color='rgba(0, 150, 200, 0.8)',
                line=dict(width=1, color='white'),
                symbol='diamond'
            ),
            text=[n['label'][:8] for n in dim_nodes if n['id'] in positions],
            textposition='bottom center',
            textfont=dict(size=7, color='#666'),
            hoverinfo='text',
            hovertext=[
                f"<b>Dimension: {n['full_name']}</b><br>"
                f"Model: {n['parent']}"
                for n in dim_nodes if n['id'] in positions
            ],
            showlegend=False,
            name='Dimensions'
        ))

    # Add fact nodes (green, smaller)
    if fact_nodes:
        fig.add_trace(go.Scatter(
            x=[positions[n['id']][0] for n in fact_nodes if n['id'] in positions],
            y=[positions[n['id']][1] for n in fact_nodes if n['id'] in positions],
            mode='markers+text',
            marker=dict(
                size=18,
                color='rgba(0, 200, 100, 0.8)',
                line=dict(width=1, color='white'),
                symbol='square'
            ),
            text=[n['label'][:8] for n in fact_nodes if n['id'] in positions],
            textposition='bottom center',
            textfont=dict(size=7, color='#666'),
            hoverinfo='text',
            hovertext=[
                f"<b>Fact: {n['full_name']}</b><br>"
                f"Model: {n['parent']}"
                for n in fact_nodes if n['id'] in positions
            ],
            showlegend=False,
            name='Facts'
        ))

    # Layout
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=20, r=20, t=20),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-3.5, 3.5]
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-3.5, 3.5],
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
    cols = st.columns(4)
    with cols[0]:
        st.markdown("🔵 **Model**")
    with cols[1]:
        st.markdown("◇ **Dimension**")
    with cols[2]:
        st.markdown("◻ **Fact**")
    with cols[3]:
        st.markdown("― **Dependency**")


def render_model_summary_cards(registry):
    """
    Render summary cards for each model.

    Alternative to graph visualization - shows models as cards.
    """
    models = registry.list_models()

    if not models:
        st.info("No models found")
        return

    # Create columns for cards
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

        except Exception as e:
            with cols[col_idx]:
                st.warning(f"Could not load {model_name}")
