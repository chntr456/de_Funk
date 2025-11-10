"""
Model Graph Viewer - Visualize model dependencies in Streamlit.

Provides interactive visualization of the model dependency graph using:
- Plotly for interactive network diagrams
- Metrics and statistics about the graph
- Model-specific dependency trees
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Optional, Dict, Any, List
import networkx as nx


def render_model_graph(model_graph, selected_model: Optional[str] = None):
    """
    Render interactive model dependency graph.

    Args:
        model_graph: ModelGraph instance
        selected_model: Optional model to highlight
    """
    st.subheader("📊 Model Dependency Graph")

    # Show metrics
    metrics = model_graph.get_metrics()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Models", metrics['num_models'])
    with col2:
        st.metric("Relationships", metrics['num_relationships'])
    with col3:
        st.metric("Is DAG", "✓" if metrics['is_dag'] else "✗")
    with col4:
        st.metric("Connected", "✓" if metrics['is_connected'] else "✗")

    # Graph visualization tabs
    tab1, tab2, tab3 = st.tabs(["🔗 Network Diagram", "📋 Model Details", "🔍 Build Order"])

    with tab1:
        _render_network_diagram(model_graph, selected_model)

    with tab2:
        _render_model_details(model_graph)

    with tab3:
        _render_build_order(model_graph)


def _render_network_diagram(model_graph, selected_model: Optional[str] = None):
    """Render interactive network diagram using Plotly."""
    st.write("### Network Visualization")

    if model_graph.graph.number_of_nodes() == 0:
        st.info("No models in graph")
        return

    # Use NetworkX spring layout for positioning
    pos = nx.spring_layout(model_graph.graph, k=2, iterations=50)

    # Create edge traces
    edge_trace = []
    for edge in model_graph.graph.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]

        edge_data = edge[2]
        edge_type = edge_data.get('type', 'dependency')

        # Different colors for different edge types
        color = {
            'dependency': 'rgb(125,125,125)',
            'cross_model_edge': 'rgb(0,100,200)',
        }.get(edge_type, 'rgb(125,125,125)')

        edge_trace.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=2, color=color),
                hoverinfo='text',
                text=f"{edge[0]} → {edge[1]}<br>Type: {edge_type}",
                showlegend=False
            )
        )

    # Create node trace
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []

    for node in model_graph.graph.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        # Get node stats
        stats = model_graph.get_model_stats(node)
        num_deps = len(stats.get('direct_dependencies', []))
        num_dependents = len(stats.get('direct_dependents', []))
        depth = stats.get('depth', 0)

        node_text.append(
            f"<b>{node}</b><br>" +
            f"Depth: {depth}<br>" +
            f"Dependencies: {num_deps}<br>" +
            f"Dependents: {num_dependents}"
        )

        # Highlight selected model
        if selected_model and node == selected_model:
            node_color.append('rgb(255,100,100)')
            node_size.append(30)
        else:
            # Color by depth
            depth_colors = ['rgb(100,200,100)', 'rgb(100,150,200)', 'rgb(150,100,200)']
            node_color.append(depth_colors[min(depth, len(depth_colors) - 1)])
            node_size.append(20)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[node for node in model_graph.graph.nodes()],
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            size=node_size,
            color=node_color,
            line=dict(width=2, color='white')
        )
    )

    # Create figure
    fig = go.Figure(
        data=edge_trace + [node_trace],
        layout=go.Layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # Legend
    st.caption("🟢 Depth 0 (core)  🔵 Depth 1  🟣 Depth 2+  🔴 Selected")


def _render_model_details(model_graph):
    """Render detailed model information."""
    st.write("### Model Details")

    # Model selector
    models = list(model_graph.graph.nodes())
    if not models:
        st.info("No models available")
        return

    selected = st.selectbox("Select model to inspect:", models)

    if selected:
        stats = model_graph.get_model_stats(selected)

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Dependencies (models this depends on):**")
            direct_deps = stats.get('direct_dependencies', [])
            all_deps = stats.get('all_dependencies', [])

            if direct_deps:
                st.write("*Direct:*")
                for dep in direct_deps:
                    edge_data = model_graph.get_edge_metadata(selected, dep)
                    edge_type = edge_data.get('type', '') if edge_data else ''
                    st.write(f"  - `{dep}` ({edge_type})")

                transitive = set(all_deps) - set(direct_deps)
                if transitive:
                    st.write("*Transitive:*")
                    for dep in transitive:
                        st.write(f"  - `{dep}`")
            else:
                st.info("No dependencies (core model)")

        with col2:
            st.write("**Dependents (models that depend on this):**")
            direct_dependents = stats.get('direct_dependents', [])
            all_dependents = stats.get('all_dependents', [])

            if direct_dependents:
                st.write("*Direct:*")
                for dep in direct_dependents:
                    st.write(f"  - `{dep}`")

                transitive = set(all_dependents) - set(direct_dependents)
                if transitive:
                    st.write("*Transitive:*")
                    for dep in transitive:
                        st.write(f"  - `{dep}`")
            else:
                st.info("No dependents")

        # Additional stats
        st.write("**Statistics:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Depth", stats.get('depth', 0))
        with col2:
            st.metric("In Degree", stats.get('in_degree', 0))
        with col3:
            st.metric("Out Degree", stats.get('out_degree', 0))


def _render_build_order(model_graph):
    """Render topological build order."""
    st.write("### Build Order (Topological Sort)")

    try:
        build_order = model_graph.get_build_order()

        st.write("Models should be built in this order:")
        for i, model in enumerate(build_order, 1):
            depth = model_graph.get_depth(model)
            st.write(f"{i}. **`{model}`** (depth: {depth})")

        st.info(
            "💡 Build order ensures dependencies are built before dependents. "
            "Models at the same depth can be built in parallel."
        )

    except ValueError as e:
        st.error(f"Cannot determine build order: {e}")


def render_graph_debug_panel(model_graph):
    """
    Render debug panel for graph inspection.

    Shows raw graph data and metrics for debugging.
    """
    with st.expander("🔧 Graph Debug Info"):
        st.write("### Graph Metrics")
        st.json(model_graph.get_metrics())

        st.write("### Graph Data")
        graph_dict = model_graph.to_dict()

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Nodes:**")
            st.json(graph_dict['nodes'])

        with col2:
            st.write("**Edges:**")
            st.json(graph_dict['edges'])

        st.write("### Mermaid Diagram")
        st.code(model_graph.to_mermaid(), language='mermaid')


def render_relationship_checker(model_graph):
    """
    Render interactive relationship checker.

    Allows users to check if two models are related and see the path.
    """
    st.write("### 🔗 Relationship Checker")

    models = list(model_graph.graph.nodes())
    if len(models) < 2:
        st.info("Need at least 2 models to check relationships")
        return

    col1, col2 = st.columns(2)
    with col1:
        model_a = st.selectbox("From model:", models, key="rel_from")
    with col2:
        model_b = st.selectbox("To model:", models, key="rel_to")

    if st.button("Check Relationship"):
        if model_a == model_b:
            st.warning("Select different models")
            return

        related = model_graph.are_related(model_a, model_b)

        if related:
            st.success(f"✓ **{model_a}** is related to **{model_b}**")

            path = model_graph.get_join_path(model_a, model_b)
            if path:
                st.write("**Path:**")
                st.write(" → ".join(path))

                # Show edge details
                st.write("**Edge details:**")
                for i in range(len(path) - 1):
                    edge_data = model_graph.get_edge_metadata(path[i], path[i+1])
                    if edge_data:
                        st.write(f"- {path[i]} → {path[i+1]}: {edge_data.get('type', 'unknown')}")
        else:
            st.error(f"✗ **{model_a}** is NOT related to **{model_b}**")
            st.info("Filters from one model will not apply to the other")
