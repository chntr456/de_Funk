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
            r'(abstract\s+)?class\s+(\S+?)(?:\s+<<(\w+)>>)?\s*(?:(#\w+))?\s*\{', stripped)
        if cls_match:
            is_abstract = bool(cls_match.group(1))
            name = cls_match.group(2).strip('"')
            stereotype = cls_match.group(3) or ""
            color = cls_match.group(4) or current_pkg_color
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

    return list(classes.values()), edges, pkg_colors


def generate_drawio(classes: list[PumlClass], edges: list[PumlEdge],
                     pkg_colors: dict[str, str]) -> str:
    cells = []
    cid = 2
    node_ids: dict[str, int] = {}

    packages: dict[str, list[PumlClass]] = {}
    for c in classes:
        pkg = c.package or "Other"
        packages.setdefault(pkg, []).append(c)

    col_width = 380
    pkg_idx = 0

    for pkg_name, pkg_classes in packages.items():
        base_x = (pkg_idx % 5) * col_width + 20
        base_y = (pkg_idx // 5) * 2000 + 20
        color = pkg_colors.get(pkg_name, "#E6E6E6")

        cells.append(
            f'      <mxCell id="{cid}" value="{xe(pkg_name)}" '
            f'style="text;fontSize=13;fontStyle=1;fontFamily=Courier New;align=left;'
            f'verticalAlign=middle;fillColor={color};rounded=1;strokeColor=#999999;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{base_x}" y="{base_y}" width="{col_width - 30}" height="22" as="geometry"/>'
            f'</mxCell>')
        cid += 1

        y = base_y + 30
        for c in pkg_classes:
            title = c.name
            if c.stereotype:
                title = f"<<{c.stereotype}>> {title}"
            if c.is_abstract:
                title = f"abstract {title}"

            rows = [f'<tr><td align="center"><b>{xe(title)}</b></td></tr>']
            if c.attrs:
                attr_html = '<br/>'.join(xe(a) for a in c.attrs)
                rows.append(f'<tr><td align="left"><font point-size="9">{attr_html}</font></td></tr>')
            else:
                rows.append('<tr><td><font point-size="9"> </font></td></tr>')
            if c.methods:
                meth_html = '<br/>'.join(xe(m) for m in c.methods)
                rows.append(f'<tr><td align="left"><font point-size="9">{meth_html}</font></td></tr>')
            else:
                rows.append('<tr><td><font point-size="9"> </font></td></tr>')

            html = ''.join(rows)
            value = xe(f'<table border="0" cellspacing="0" cellpadding="3" width="100%">{html}</table>')
            h = max(50, 22 + max(len(c.attrs), 1) * 13 + max(len(c.methods), 1) * 13 + 10)
            w = col_width - 30

            cells.append(
                f'      <mxCell id="{cid}" value="{value}" '
                f'style="verticalAlign=top;align=left;overflow=fill;html=1;rounded=0;'
                f'strokeColor=#333333;fontFamily=Courier New;fontSize=10;fillColor={c.color};" '
                f'vertex="1" parent="1">'
                f'<mxGeometry x="{base_x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
                f'</mxCell>')
            node_ids[c.name] = cid
            cid += 1
            y += h + 6

        pkg_idx += 1

    edge_styles = {
        'inherit': 'endArrow=block;endFill=0;strokeColor=#555555;',
        'compose': 'endArrow=diamond;endFill=1;strokeColor=#555555;',
        'delegate': 'endArrow=open;endFill=0;strokeColor=#999999;dashed=1;',
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

    content = '\n'.join(cells)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" type="device">
  <diagram id="puml-converted" name="Full Vision (from PlantUML)">
    <mxGraphModel dx="2800" dy="2400" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="2400" pageHeight="4000" math="0" shadow="0">
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
