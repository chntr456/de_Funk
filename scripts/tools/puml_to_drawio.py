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
            m = re.match(r'(\S+)\s+<\|--\s+(\S+)', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(2), tgt=m.group(1), style='inherit'))
                continue
            m = re.match(r'(\S+)\s+--\|>\s+(\S+)', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='inherit'))
                continue
            m = re.match(r'(\S+)\s+\*--\s+(\S+)', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='compose'))
                continue
            m = re.match(r'(\S+)\s+\.\.>\s+(\S+)', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(1), tgt=m.group(2), style='delegate'))
                continue
            # A <|.. B (B realizes interface A)
            m = re.match(r'(\S+)\s+<\|\.\.\s+(\S+)', stripped)
            if m:
                edges.append(PumlEdge(src=m.group(2), tgt=m.group(1), style='realize'))
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

    # Step 4: assign positions
    # Arrange packages in rows of up to 5 columns
    MAX_COLS = 5
    positions: dict[str, tuple[int, int]] = {}
    col_heights: list[int] = [0] * MAX_COLS  # track height per column

    for pkg_i, pkg_name in enumerate(sorted_pkgs):
        col = pkg_i % MAX_COLS
        # Find the starting y for this package (below previous package in same column)
        base_x = col * (COL_W + PKG_GAP_X) + 20
        base_y = col_heights[col] + PKG_GAP_Y

        y = base_y + PKG_LABEL_H
        for c in packages[pkg_name]:
            h = _node_height(c)
            positions[c.name] = (base_x, y)
            y += h + RANK_GAP

        col_heights[col] = y

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
            header_lines.append(f"&lt;&lt;{xe(c.stereotype)}&gt;&gt;")
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

        # Attribute items
        for attr in (c.attrs or [' ']):
            cells.append(
                f'      <mxCell id="{cid}" value="{xe(attr)}" '
                f'style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                f'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                f'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                f'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;" '
                f'vertex="1" parent="{container_id}">'
                f'<mxGeometry width="{NODE_W}" height="{ITEM_H}" as="geometry"/>'
                f'</mxCell>')
            cid += 1

        # Separator line between attributes and methods
        cells.append(
            f'      <mxCell id="{cid}" value="" '
            f'style="line;strokeWidth=1;fillColor=none;align=left;'
            f'verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;'
            f'rotatable=0;labelPosition=right;points=[];portConstraint=eastwest;" '
            f'vertex="1" parent="{container_id}">'
            f'<mxGeometry width="{NODE_W}" height="{SEP_H}" as="geometry"/>'
            f'</mxCell>')
        cid += 1

        # Method items
        for method in (c.methods or [' ']):
            cells.append(
                f'      <mxCell id="{cid}" value="{xe(method)}" '
                f'style="text;html=1;strokeColor=none;fillColor=none;align=left;'
                f'verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;'
                f'rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;'
                f'fontFamily=Courier New;fontSize=10;whiteSpace=wrap;" '
                f'vertex="1" parent="{container_id}">'
                f'<mxGeometry width="{NODE_W}" height="{ITEM_H}" as="geometry"/>'
                f'</mxCell>')
            cid += 1

    # Render edges
    edge_styles = {
        'inherit': 'endArrow=block;endFill=0;strokeColor=#555555;',
        'compose': 'endArrow=diamond;endFill=1;strokeColor=#555555;',
        'delegate': 'endArrow=open;endFill=0;strokeColor=#999999;dashed=1;',
        'realize': 'endArrow=block;endFill=0;strokeColor=#555555;dashed=1;',
    }

    for e in edges:
        src_id = node_ids.get(e.src)
        tgt_id = node_ids.get(e.tgt)
        if src_id and tgt_id:
            style = edge_styles.get(e.style, edge_styles['delegate'])
            cells.append(
                f'      <mxCell id="{cid}" value="" style="{style}" '
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.tools.puml_to_drawio <file.puml>")
        sys.exit(1)

    puml_path = Path(sys.argv[1])
    if not puml_path.exists():
        print(f"File not found: {puml_path}")
        sys.exit(1)

    text = puml_path.read_text()
    classes, edges, pkg_colors = parse_puml(text)
    xml = generate_drawio(classes, edges, pkg_colors)

    ET.fromstring(xml)

    out_path = puml_path.with_suffix('.drawio')
    out_path.write_text(xml)
    print(f"Converted: {puml_path} -> {out_path}")
    print(f"  {len(classes)} classes, {len(edges)} edges, {len(pkg_colors)} packages")


if __name__ == "__main__":
    main()
