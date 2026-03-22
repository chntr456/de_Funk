#!/usr/bin/env python
"""
puml_to_drawio — Convert PlantUML class diagrams to draw.io XML.

Usage:
    python -m scripts.tools.puml_to_drawio docs/diagrams/full_vision.puml

Reads a .puml file, extracts classes/packages/relationships,
and generates a .drawio file with the same name.
"""
from __future__ import annotations
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


def xe(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


@dataclass
class PumlClass:
    name: str
    attrs: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    stereotype: str = ""
    is_abstract: bool = False
    package: str = ""
    color: str = "#E6E6E6"


@dataclass
class PumlEdge:
    src: str
    tgt: str
    style: str
    label: str = ""


def parse_puml(text: str) -> tuple[list[PumlClass], list[PumlEdge], dict[str, str]]:
    classes: dict[str, PumlClass] = {}
    edges: list[PumlEdge] = []
    pkg_colors: dict[str, str] = {}
    current_class: PumlClass | None = None
    current_pkg = ""
    current_pkg_color = "#E6E6E6"
    in_attrs = True
    pkg_stack: list[tuple[str, str]] = []

    for line in text.split('\n'):
        stripped = line.strip()

        if stripped.startswith("'") or stripped.startswith("skinparam") or stripped.startswith("title"):
            continue
        if stripped.startswith("@start") or stripped.startswith("@end") or stripped.startswith("set "):
            continue

        pkg_match = re.match(r'package\s+"([^"]+)"\s*(#\w+)?\s*\{', stripped)
        if pkg_match:
            pkg_stack.append((current_pkg, current_pkg_color))
            current_pkg = pkg_match.group(1)
            current_pkg_color = pkg_match.group(2) or "#E6E6E6"
            pkg_colors[current_pkg] = current_pkg_color
            continue

        if stripped == '}':
            if current_class:
                current_class = None
                in_attrs = True
            elif pkg_stack:
                current_pkg, current_pkg_color = pkg_stack.pop()
            continue

        cls_match = re.match(
            r'(abstract\s+)?(?:class|interface)\s+(\S+?)(?:\s+<<(\w+)>>)?\s*(?:(#\w+))?\s*\{', stripped)
        if cls_match:
            is_abstract = bool(cls_match.group(1))
            name = cls_match.group(2).strip('"')
            stereotype = cls_match.group(3) or ""
            color = cls_match.group(4) or current_pkg_color
            # Auto-detect interface keyword
            if stripped.startswith('interface ') and not stereotype:
                stereotype = 'interface'
            current_class = PumlClass(
                name=name, is_abstract=is_abstract,
                stereotype=stereotype, package=current_pkg,
                color=color)
            classes[name] = current_class
            in_attrs = True
            continue

        if current_class:
            if stripped == '--' or stripped.startswith('__ ') or stripped.startswith('.. '):
                in_attrs = False
                if stripped.startswith('.. ') and stripped.endswith(' ..'):
                    current_class.attrs.append(stripped[3:-3])
                continue
            if stripped == '':
                continue
            member = re.sub(r'^[+\-#~]\s*', '', stripped)
            if in_attrs:
                current_class.attrs.append(member)
            else:
                current_class.methods.append(member)

        if not current_class:
            m = re.match(r'(\S+)\s+<\|--\s+(\S+)(?:\s*:\s*(.+))?', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(2), tgt=m.group(1), style='inherit', label=m.group(3) or ''))
                continue
            m = re.match(r'(\S+)\s+--\|>\s+(\S+)(?:\s*:\s*(.+))?', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='inherit', label=m.group(3) or ''))
                continue
            m = re.match(r'(\S+)\s+\*--\s+(\S+)(?:\s*:\s*(.+))?', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='compose', label=m.group(3) or ''))
                continue
            m = re.match(r'(\S+)\s+\.\.>\s+(\S+)(?:\s*:\s*(.+))?', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='delegate', label=m.group(3) or ''))
                continue
            # A <|.. B (B realizes interface A)
            m = re.match(r'(\S+)\s+<\|\.\.\s+(\S+)(?:\s*:\s*(.+))?', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(2), tgt=m.group(1), style='realize', label=m.group(3) or ''))
                continue

    return list(classes.values()), edges, pkg_colors


def _node_height(c: PumlClass) -> int:
    ITEM_H = 20
    SEP_H = 8
    header_lines = 1 + (1 if c.stereotype else 0) + (1 if c.is_abstract else 0)
    start_size = max(26, header_lines * 18 + 4)
    attr_count = max(len(c.attrs), 1)
    method_count = max(len(c.methods), 1)
    return start_size + attr_count * ITEM_H + SEP_H + method_count * ITEM_H


def _sugiyama_layout(
    classes: list[PumlClass],
    edges: list[PumlEdge],
    pkg_colors: dict[str, str],
) -> dict[str, tuple[int, int]]:
    """Sugiyama hierarchical layout: ABCs at top, children below, packages as columns.

    Steps:
      1. Build inheritance graph, compute rank (depth from root ABCs)
      2. Order packages left-to-right by a dependency heuristic
      3. Within each package, sort classes by rank (ABCs first)
      4. Assign x by package column, y by rank within package
      5. Minimize edge crossings by reordering within ranks
    """
    class_map = {c.name: c for c in classes}
    COL_W = 380
    NODE_W = COL_W - 30
    RANK_GAP = 30  # vertical gap between nodes
    PKG_LABEL_H = 30
    PKG_GAP_X = 40  # horizontal gap between package columns
    PKG_GAP_Y = 60  # vertical gap between package rows

    # Step 1: compute inheritance rank (depth from root)
    children: dict[str, list[str]] = {}
    parent_of: dict[str, str] = {}
    for e in edges:
        if e.style == 'inherit':
            children.setdefault(e.tgt, []).append(e.src)
            parent_of[e.src] = e.tgt

    def rank_of(name: str, _memo: dict = {}) -> int:
        if name in _memo:
            return _memo[name]
        p = parent_of.get(name)
        r = (rank_of(p, _memo) + 1) if p else 0
        _memo[name] = r
        return r

    ranks = {c.name: rank_of(c.name) for c in classes}

    # Step 2: order packages by dependency (packages with ABCs first)
    packages: dict[str, list[PumlClass]] = {}
    for c in classes:
        pkg = c.package or "Other"
        packages.setdefault(pkg, []).append(c)

    # Heuristic: packages with lower average rank come first (more abstract)
    def pkg_sort_key(pkg_name: str) -> tuple:
        pkg_classes = packages[pkg_name]
        avg_rank = sum(ranks.get(c.name, 0) for c in pkg_classes) / max(len(pkg_classes), 1)
        # Also consider cross-package edges: packages that are depended on come first
        depended_on = sum(
            1 for e in edges
            if e.style == 'inherit'
            and class_map.get(e.tgt, PumlClass("")).package == pkg_name
            and class_map.get(e.src, PumlClass("")).package != pkg_name
        )
        return (-depended_on, avg_rank, pkg_name)

    sorted_pkgs = sorted(packages.keys(), key=pkg_sort_key)

    # Step 3: within each package, sort by rank then alphabetically
    for pkg_name in sorted_pkgs:
        packages[pkg_name].sort(key=lambda c: (ranks.get(c.name, 0), c.name))

    # Step 4: assign positions using balanced grid layout
    # Goal: minimize total canvas area by balancing column heights
    MAX_COLS = 4
    positions: dict[str, tuple[int, int]] = {}

    # Calculate total height per package
    pkg_heights: dict[str, int] = {}
    for pkg_name, pkg_classes in packages.items():
        total = PKG_LABEL_H
        for c in pkg_classes:
            total += _node_height(c) + RANK_GAP
        pkg_heights[pkg_name] = total

    # Greedy bin-packing: assign each package to the shortest column
    col_heights: list[int] = [0] * MAX_COLS
    col_packages: list[list[str]] = [[] for _ in range(MAX_COLS)]

    # Sort packages by height descending (pack tallest first for better balance)
    sorted_by_height = sorted(sorted_pkgs, key=lambda p: -pkg_heights.get(p, 0))

    for pkg_name in sorted_by_height:
        # Find shortest column
        min_col = min(range(MAX_COLS), key=lambda c: col_heights[c])
        col_packages[min_col].append(pkg_name)
        col_heights[min_col] += pkg_heights[pkg_name] + PKG_GAP_Y

    # Assign positions: each column gets its packages stacked vertically
    for col in range(MAX_COLS):
        base_x = col * (COL_W + PKG_GAP_X) + 20
        y = PKG_GAP_Y

        for pkg_name in col_packages[col]:
            y += PKG_LABEL_H
            pkg_classes = packages.get(pkg_name, [])

            # Within package: use 2 columns if > 6 classes
            if len(pkg_classes) > 6:
                inner_cols = 2
            else:
                inner_cols = 1

            inner_col_y = [y] * inner_cols
            for i, c in enumerate(pkg_classes):
                ic = i % inner_cols
                h = _node_height(c)
                cx = base_x + ic * (NODE_W + 10)
                positions[c.name] = (cx, inner_col_y[ic])
                inner_col_y[ic] += h + RANK_GAP

            y = max(inner_col_y) + PKG_GAP_Y

    return positions


def generate_drawio(classes: list[PumlClass], edges: list[PumlEdge],
                     pkg_colors: dict[str, str]) -> str:
    """Generate draw.io XML with Sugiyama hierarchical layout."""
    cells = []
    cid = 2
    node_ids: dict[str, int] = {}
    COL_W = 380
    NODE_W = COL_W - 30
    PKG_GAP_X = 40
    PKG_GAP_Y = 60
    PKG_LABEL_H = 30

    # Compute positions
    positions = _sugiyama_layout(classes, edges, pkg_colors)

    # Group by package for labels
    packages: dict[str, list[PumlClass]] = {}
    for c in classes:
        pkg = c.package or "Other"
        packages.setdefault(pkg, []).append(c)

    # Render package labels (at top of each package's bounding box)
    pkg_bounds: dict[str, tuple[int, int, int, int]] = {}
    for pkg_name, pkg_classes in packages.items():
        if not pkg_classes:
            continue
        xs = [positions[c.name][0] for c in pkg_classes if c.name in positions]
        ys = [positions[c.name][1] for c in pkg_classes if c.name in positions]
        if not xs:
            continue
        min_x, max_x = min(xs), max(xs)
        min_y = min(ys)
        # Find the tallest class for bottom bound
        max_y = max(positions[c.name][1] + _node_height(c)
                     for c in pkg_classes if c.name in positions)
        pkg_bounds[pkg_name] = (min_x, min_y - PKG_LABEL_H, max_x + NODE_W, max_y)

        color = pkg_colors.get(pkg_name, "#E6E6E6")
        # Package background rectangle
        bx, by, bx2, by2 = min_x - 10, min_y - PKG_LABEL_H - 5, max_x + NODE_W + 10, max_y + 10
        cells.append(
            f'      <mxCell id="{cid}" value="{xe(pkg_name)}" '
            f'style="rounded=1;whiteSpace=wrap;fontSize=13;fontStyle=1;fontFamily=Courier New;'
            f'verticalAlign=top;dashed=1;dashPattern=5 5;opacity=30;'
            f'fillColor={color};strokeColor=#999999;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{bx}" y="{by}" width="{bx2 - bx}" height="{by2 - by}" as="geometry"/>'
            f'</mxCell>')
        cid += 1

    # Render classes as UML 2.5 swimlane containers with stacked children
    ITEM_H = 20
    SEP_H = 8

    for c in classes:
        if c.name not in positions:
            continue
        x, y = positions[c.name]

        # Build header value — needs HTML since swimlane has html=1
        # XML attribute encoding: &lt; for < that draw.io renders as HTML
        # But draw.io's XML parser is lenient with value attributes
        # Use &#xa; for line breaks (works in both XML and draw.io)
        header_lines = []
        if c.stereotype:
            header_lines.append(f"&#171;{xe(c.stereotype)}&#187;")
        header_lines.append(xe(c.name))
        if c.is_abstract:
            header_lines.append("{abstract}")
        header_value = "&#xa;".join(header_lines)

        # Calculate header height based on lines
        num_header_lines = len(header_lines)
        start_size = max(26, num_header_lines * 18 + 4)

        # Calculate total height
        attr_count = max(len(c.attrs), 1)
        method_count = max(len(c.methods), 1)
        body_h = attr_count * ITEM_H + SEP_H + method_count * ITEM_H
        total_h = start_size + body_h

        # Font style: 1=bold for concrete, 0 for abstract/interface
        font_style = 0 if (c.is_abstract or c.stereotype in ('interface', 'abstract')) else 1

        # Swimlane container (the UML 2.5 classifier box)
        cells.append(
            f'      <mxCell id="{cid}" value="{header_value}" '
            f'style="swimlane;fontStyle={font_style};align=center;verticalAlign=top;'
            f'childLayout=stackLayout;horizontal=1;startSize={start_size};'
            f'horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;'
            f'collapsible=0;marginBottom=0;html=1;whiteSpace=wrap;'
            f'fillColor={c.color};strokeColor=#333333;fontFamily=Courier New;fontSize=10;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{NODE_W}" height="{total_h}" as="geometry"/>'
            f'</mxCell>')
        container_id = cid
        node_ids[c.name] = cid
        cid += 1

        # Attribute items — use explicit y positions
        child_y = start_size
        for attr in (c.attrs or [' ']):
            cells.append(
                f'      <mxCell id="{cid}" value="{xe(attr)}" '
                f'style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                f'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                f'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                f'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;" '
                f'vertex="1" parent="{container_id}">'
                f'<mxGeometry y="{child_y}" width="{NODE_W}" height="{ITEM_H}" as="geometry"/>'
                f'</mxCell>')
            cid += 1
            child_y += ITEM_H

        # Separator line between attributes and methods
        cells.append(
            f'      <mxCell id="{cid}" value="" '
            f'style="line;strokeWidth=1;fillColor=none;align=left;'
            f'verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;'
            f'rotatable=0;labelPosition=right;points=[];portConstraint=eastwest;" '
            f'vertex="1" parent="{container_id}">'
            f'<mxGeometry y="{child_y}" width="{NODE_W}" height="{SEP_H}" as="geometry"/>'
            f'</mxCell>')
        cid += 1
        child_y += SEP_H

        # Method items
        for method in (c.methods or [' ']):
            cells.append(
                f'      <mxCell id="{cid}" value="{xe(method)}" '
                f'style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                f'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                f'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                f'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;" '
                f'vertex="1" parent="{container_id}">'
                f'<mxGeometry y="{child_y}" width="{NODE_W}" height="{ITEM_H}" as="geometry"/>'
                f'</mxCell>')
            cid += 1
            child_y += ITEM_H

    # Render edges
    ORTHO = 'edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;targetPerimeterSpacing=0;'
    edge_styles = {
        'inherit': f'{ORTHO}endArrow=block;endFill=0;strokeColor=#555555;',
        'compose': f'{ORTHO}endArrow=diamond;endFill=1;strokeColor=#555555;',
        'delegate': f'{ORTHO}endArrow=open;endFill=0;strokeColor=#999999;dashed=1;',
        'realize': f'{ORTHO}endArrow=block;endFill=0;strokeColor=#555555;dashed=1;',
    }

    for e in edges:
        src_id = node_ids.get(e.src)
        tgt_id = node_ids.get(e.tgt)
        if src_id and tgt_id:
            style = edge_styles.get(e.style, edge_styles['delegate'])
            label = xe(e.label.strip()) if e.label else ''
            cells.append(
                f'      <mxCell id="{cid}" value="{label}" style="{style}'
                f'fontSize=9;fontFamily=Courier New;" '
                f'edge="1" parent="1" source="{src_id}" target="{tgt_id}">'
                f'<mxGeometry relative="1" as="geometry"/></mxCell>')
            cid += 1

    # Render legend
    all_positions = [positions[c.name] for c in classes if c.name in positions]
    legend_x = max(p[0] for p in all_positions) + COL_W + 60 if all_positions else 20
    legend_y = 60

    # Title
    cells.append(
        f'      <mxCell id="{cid}" value="{xe("LEGEND")}" '
        f'style="text;fontSize=14;fontStyle=1;fontFamily=Courier New;align=left;verticalAlign=middle;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{legend_x}" y="{legend_y}" width="200" height="25" as="geometry"/></mxCell>')
    cid += 1
    legend_y += 30

    # Package color swatches
    for pkg_name in sorted(pkg_colors.keys()):
        color = pkg_colors[pkg_name]
        cells.append(
            f'      <mxCell id="{cid}" value="{xe(pkg_name)}" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor={color};strokeColor=#666666;'
            f'fontSize=10;fontFamily=Courier New;align=left;spacingLeft=8;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{legend_x}" y="{legend_y}" width="220" height="22" as="geometry"/></mxCell>')
        cid += 1
        legend_y += 26

    # Edge legend
    legend_y += 15
    cells.append(
        f'      <mxCell id="{cid}" value="{xe("ARROWS")}" '
        f'style="text;fontSize=12;fontStyle=1;fontFamily=Courier New;align=left;verticalAlign=middle;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{legend_x}" y="{legend_y}" width="200" height="22" as="geometry"/></mxCell>')
    cid += 1
    legend_y += 28

    for label, style_desc in [
        ("hollow triangle = inherits", "endArrow=block;endFill=0;strokeColor=#555555;"),
        ("filled diamond = composes", "endArrow=diamond;endFill=1;strokeColor=#555555;"),
        ("dashed arrow = delegates", "endArrow=open;endFill=0;strokeColor=#999999;dashed=1;"),
    ]:
        # Arrow sample line
        src_id = cid
        cells.append(
            f'      <mxCell id="{cid}" value="" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor=#E6E6E6;strokeColor=#999999;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{legend_x}" y="{legend_y + 4}" width="12" height="12" as="geometry"/></mxCell>')
        cid += 1
        tgt_id = cid
        cells.append(
            f'      <mxCell id="{cid}" value="" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor=#E6E6E6;strokeColor=#999999;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{legend_x + 50}" y="{legend_y + 4}" width="12" height="12" as="geometry"/></mxCell>')
        cid += 1
        cells.append(
            f'      <mxCell id="{cid}" value="" style="{style_desc}" '
            f'edge="1" parent="1" source="{src_id}" target="{tgt_id}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>')
        cid += 1
        cells.append(
            f'      <mxCell id="{cid}" value="{xe(label)}" '
            f'style="text;fontSize=10;fontFamily=Courier New;align=left;verticalAlign=middle;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{legend_x + 70}" y="{legend_y}" width="200" height="20" as="geometry"/></mxCell>')
        cid += 1
        legend_y += 28

    content = '\n'.join(cells)

    # Calculate page size from actual bounds
    all_x = [positions[c.name][0] for c in classes if c.name in positions]
    all_y = [positions[c.name][1] + _node_height(c) for c in classes if c.name in positions]
    page_w = max(all_x) + COL_W + 200 if all_x else 3000
    page_h = max(all_y) + 200 if all_y else 4000

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" type="device">
  <diagram id="puml-converted" name="Full Vision (from PlantUML)">
    <mxGraphModel dx="2800" dy="2400" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
{content}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''


def _find_class_name(value: str) -> str | None:
    """Extract class name from swimlane header value."""
    if not value:
        return None
    # Value might be "<<dataclass>>\nSchemaField" or just "Engine"
    lines = value.replace('\n', ' ').replace('&#xa;', ' ').split()
    # Skip stereotype tokens like <<dataclass>>, {abstract}
    for token in reversed(lines):
        if not token.startswith('<<') and not token.startswith('{') and not token.startswith('<'):
            return token
    return lines[-1] if lines else None


def update_drawio(drawio_path: Path, classes: list[PumlClass]) -> int:
    """Update class contents in existing drawio file without moving containers.

    Finds swimlane containers by class name, replaces their children
    (attributes, separator, methods) while preserving container position/size.
    Returns count of updated classes.
    """
    tree = ET.parse(drawio_path)
    root_elem = tree.getroot()
    updated = 0

    # Build lookup from puml class name -> PumlClass
    class_map = {c.name: c for c in classes}

    for diagram in root_elem.findall('diagram'):
        mg = diagram.find('mxGraphModel')
        if mg is None:
            continue
        rt = mg.find('root')
        if rt is None:
            continue

        # Find all swimlane containers and map name -> element + id
        containers: dict[str, tuple[ET.Element, str]] = {}
        for cell in rt.findall('mxCell'):
            style = cell.get('style', '')
            if 'swimlane' in style and 'childLayout' in style:
                name = _find_class_name(cell.get('value', ''))
                if name:
                    containers[name] = (cell, cell.get('id', ''))

        # For each matching class, update children
        for class_name, puml_class in class_map.items():
            if class_name not in containers:
                continue

            container, container_id = containers[class_name]

            # Remove existing children of this container
            children_to_remove = [
                c for c in rt.findall('mxCell')
                if c.get('parent') == container_id and c.get('id') != container_id
            ]
            for child in children_to_remove:
                rt.remove(child)

            # Find max existing ID to generate new unique IDs
            max_id = max(
                (int(c.get('id', '0')) for c in rt.findall('mxCell')
                 if c.get('id', '').isdigit()),
                default=1000
            )
            cid = max_id + 1

            # Get container geometry for width
            geo = container.find('mxGeometry')
            node_w = int(float(geo.get('width', '350'))) if geo is not None else 350

            # Read startSize from style
            style = container.get('style', '')
            start_size = 26
            for part in style.split(';'):
                if part.startswith('startSize='):
                    start_size = int(part.split('=')[1])

            # Update header value
            header_lines = []
            if puml_class.stereotype:
                header_lines.append(f"&#171;{xe(puml_class.stereotype)}&#187;")
            header_lines.append(xe(puml_class.name))
            if puml_class.is_abstract:
                header_lines.append("{abstract}")
            container.set('value', "&#xa;".join(header_lines))

            # Recalculate startSize based on header lines
            num_lines = len(header_lines)
            new_start_size = max(26, num_lines * 18 + 4)

            # Update startSize in style
            new_style = ';'.join(
                f'startSize={new_start_size}' if p.startswith('startSize=') else p
                for p in style.split(';')
            )
            container.set('style', new_style)

            # Add new children
            ITEM_H = 20
            SEP_H = 8
            child_y = new_start_size

            for attr in (puml_class.attrs or [' ']):
                child = ET.SubElement(rt, 'mxCell', {
                    'id': str(cid),
                    'value': xe(attr),
                    'style': ('text;html=1;strokeColor=none;fillColor=none;align=left;'
                              'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                              'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                              'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;'),
                    'vertex': '1',
                    'parent': container_id,
                })
                child_geo = ET.SubElement(child, 'mxGeometry', {
                    'y': str(child_y), 'width': str(node_w), 'height': str(ITEM_H),
                    'as': 'geometry',
                })
                cid += 1
                child_y += ITEM_H

            # Separator
            sep = ET.SubElement(rt, 'mxCell', {
                'id': str(cid),
                'value': '',
                'style': ('line;strokeWidth=1;fillColor=none;align=left;'
                          'verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;'
                          'rotatable=0;labelPosition=right;points=[];portConstraint=eastwest;'),
                'vertex': '1',
                'parent': container_id,
            })
            sep_geo = ET.SubElement(sep, 'mxGeometry', {
                'y': str(child_y), 'width': str(node_w), 'height': str(SEP_H),
                'as': 'geometry',
            })
            cid += 1
            child_y += SEP_H

            for method in (puml_class.methods or [' ']):
                child = ET.SubElement(rt, 'mxCell', {
                    'id': str(cid),
                    'value': xe(method),
                    'style': ('text;html=1;strokeColor=none;fillColor=none;align=left;'
                              'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                              'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                              'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;'),
                    'vertex': '1',
                    'parent': container_id,
                })
                child_geo = ET.SubElement(child, 'mxGeometry', {
                    'y': str(child_y), 'width': str(node_w), 'height': str(ITEM_H),
                    'as': 'geometry',
                })
                cid += 1
                child_y += ITEM_H

            # Update container height to fit new children
            if geo is not None:
                geo.set('height', str(child_y))

            updated += 1

    # Add new classes that don't exist in the drawio yet — staging area
    new_classes = [c for c in classes if c.name not in containers]
    if new_classes:
        # Find bottom-right of existing content for staging area
        max_y = 0
        for cell in rt.findall('mxCell'):
            geo = cell.find('mxGeometry')
            if geo is not None:
                cy = float(geo.get('y', '0')) + float(geo.get('height', '0'))
                if cy > max_y:
                    max_y = cy

        staging_x = 20
        staging_y = int(max_y) + 80

        # Find max ID
        max_id = max(
            (int(c.get('id', '0')) for c in rt.findall('mxCell')
             if c.get('id', '').isdigit()),
            default=1000
        )
        cid = max_id + 1

        # Add staging label
        label = ET.SubElement(rt, 'mxCell', {
            'id': str(cid),
            'value': 'NEW (drag into place)',
            'style': ('text;fontSize=14;fontStyle=1;fontFamily=Courier New;'
                      'align=left;verticalAlign=middle;fontColor=#CC0000;'),
            'vertex': '1',
            'parent': '1',
        })
        ET.SubElement(label, 'mxGeometry', {
            'x': str(staging_x), 'y': str(staging_y),
            'width': '300', 'height': '25', 'as': 'geometry',
        })
        cid += 1
        staging_y += 35
        NODE_W = 350
        ITEM_H = 20
        SEP_H = 8

        for c in new_classes:
            # Header
            header_lines = []
            if c.stereotype:
                header_lines.append(f"&#171;{xe(c.stereotype)}&#187;")
            header_lines.append(xe(c.name))
            if c.is_abstract:
                header_lines.append("{abstract}")
            header_value = "&#xa;".join(header_lines)

            num_lines = len(header_lines)
            start_size = max(26, num_lines * 18 + 4)
            font_style = 0 if (c.is_abstract or c.stereotype in ('interface', 'abstract')) else 1

            attr_count = max(len(c.attrs), 1)
            method_count = max(len(c.methods), 1)
            total_h = start_size + attr_count * ITEM_H + SEP_H + method_count * ITEM_H

            container = ET.SubElement(rt, 'mxCell', {
                'id': str(cid),
                'value': header_value,
                'style': (f'swimlane;fontStyle={font_style};align=center;verticalAlign=top;'
                          f'childLayout=stackLayout;horizontal=1;startSize={start_size};'
                          f'horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;'
                          f'collapsible=0;marginBottom=0;html=1;whiteSpace=wrap;'
                          f'fillColor={c.color};strokeColor=#333333;'
                          f'fontFamily=Courier New;fontSize=10;'),
                'vertex': '1',
                'parent': '1',
            })
            ET.SubElement(container, 'mxGeometry', {
                'x': str(staging_x), 'y': str(staging_y),
                'width': str(NODE_W), 'height': str(total_h), 'as': 'geometry',
            })
            container_id = str(cid)
            cid += 1

            child_y = start_size
            for attr in (c.attrs or [' ']):
                child = ET.SubElement(rt, 'mxCell', {
                    'id': str(cid), 'value': xe(attr),
                    'style': ('text;html=1;strokeColor=none;fillColor=none;align=left;'
                              'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                              'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                              'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;'),
                    'vertex': '1', 'parent': container_id,
                })
                ET.SubElement(child, 'mxGeometry', {
                    'y': str(child_y), 'width': str(NODE_W), 'height': str(ITEM_H),
                    'as': 'geometry',
                })
                cid += 1
                child_y += ITEM_H

            sep = ET.SubElement(rt, 'mxCell', {
                'id': str(cid), 'value': '',
                'style': ('line;strokeWidth=1;fillColor=none;align=left;'
                          'verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;'
                          'rotatable=0;labelPosition=right;points=[];portConstraint=eastwest;'),
                'vertex': '1', 'parent': container_id,
            })
            ET.SubElement(sep, 'mxGeometry', {
                'y': str(child_y), 'width': str(NODE_W), 'height': str(SEP_H),
                'as': 'geometry',
            })
            cid += 1
            child_y += SEP_H

            for method in (c.methods or [' ']):
                child = ET.SubElement(rt, 'mxCell', {
                    'id': str(cid), 'value': xe(method),
                    'style': ('text;html=1;strokeColor=none;fillColor=none;align=left;'
                              'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                              'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                              'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;'),
                    'vertex': '1', 'parent': container_id,
                })
                ET.SubElement(child, 'mxGeometry', {
                    'y': str(child_y), 'width': str(NODE_W), 'height': str(ITEM_H),
                    'as': 'geometry',
                })
                cid += 1
                child_y += ITEM_H

            staging_y += total_h + 15

    # Write back
    ET.indent(tree, space='  ')
    tree.write(drawio_path, encoding='unicode', xml_declaration=True)
    return updated, len(new_classes) if new_classes else 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.tools.puml_to_drawio <file.puml> [--full]")
        print("  Default: update existing .drawio in-place (preserve positions)")
        print("  --full:  full regenerate (replaces everything including layout)")
        sys.exit(1)

    puml_path = Path(sys.argv[1])
    if not puml_path.exists():
        print(f"File not found: {puml_path}")
        sys.exit(1)

    full_regen = '--full' in sys.argv
    out_path = puml_path.with_suffix('.drawio')

    text = puml_path.read_text()
    classes, edges, pkg_colors = parse_puml(text)

    if not full_regen and out_path.exists():
        updated, new = update_drawio(out_path, classes)
        msg = f"Updated: {out_path} ({updated} classes updated in-place)"
        if new:
            msg += f", {new} new classes added to staging area (drag into place)"
        print(msg)
    else:
        xml = generate_drawio(classes, edges, pkg_colors)
        ET.fromstring(xml)
        out_path.write_text(xml)
        print(f"Converted: {puml_path} -> {out_path}")
        print(f"  {len(classes)} classes, {len(edges)} edges, {len(pkg_colors)} packages")


if __name__ == "__main__":
    main()
