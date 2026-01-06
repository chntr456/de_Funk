# Proposal: React Whiteboard UI Overhaul

**Status**: 📋 Draft
**Author**: Claude
**Date**: 2026-01-06
**Priority**: High
**Estimated Effort**: 15-20 weeks

---

## Executive Summary

Replace the current Streamlit UI with a React-based whiteboard/canvas interface using ReactFlow. This enables spatial data exploration where users can arrange exhibits, draw connections between insights, and interact with data in a more flexible, powerful way—while preserving the existing markdown notebook paradigm.

### Key Benefits
- **Whiteboard exploration**: Drag, arrange, and connect data visualizations spatially
- **Full CRUD**: Create, edit, delete notebooks entirely in-app (currently missing)
- **Better UX**: Modern React components, keyboard shortcuts, undo/redo
- **Same markdown source**: Existing notebooks work with minimal changes
- **Dynamic dimensions**: First-class support for dimension switching and cross-filtering
- **Geographic maps**: Full map support via Mapbox GL / DeckGL

---

## Table of Contents

1. [Motivation](#motivation)
2. [Current State & Gaps](#current-state--gaps)
3. [Architecture Overview](#architecture-overview)
4. [Technical Stack](#technical-stack)
5. [ReactFlow Container Patterns](#reactflow-container-patterns)
6. [Component Migration Guide](#component-migration-guide)
7. [API Specification](#api-specification)
8. [Phased Implementation Plan](#phased-implementation-plan)
9. [Development Environment](#development-environment)
10. [Risk Mitigation](#risk-mitigation)
11. [Success Metrics](#success-metrics)
12. [References](#references)

---

## Motivation

### Why Move Away from Streamlit?

| Limitation | Impact |
|------------|--------|
| No in-app content editing | Users must edit markdown files externally |
| Linear layout only | Can't spatially arrange related insights |
| No connection drawing | Can't visually link cause → effect |
| Limited state management | Reruns entire script on interaction |
| Basic component library | Custom widgets are difficult |
| No undo/redo | Destructive actions are permanent |
| Limited keyboard shortcuts | Power users slowed down |

### Why Whiteboard/Canvas?

The whiteboard paradigm enables **exploratory data analysis** where:
- Related exhibits are grouped spatially
- Connections show data flow and insights
- Users build narratives by arrangement
- Layouts persist and can be shared

**Inspiration**: Count.co, Miro + BI, Observable notebooks

---

## Current State & Gaps

### What Exists Today ✅
```
✅ Markdown notebook parser ($filter$, $exhibit$, $grid$ syntax)
✅ DuckDB/Spark backend with UniversalSession
✅ Model/measure framework
✅ Filter context system
✅ Plotly visualizations
✅ Great Tables integration
✅ Basic Streamlit rendering
```

### Missing User Functionality ❌

| Category | Missing Feature | Priority |
|----------|-----------------|----------|
| **Content Management** | Create new notebook | 🔴 Critical |
| | Edit notebook content in-app | 🔴 Critical |
| | Delete notebook | 🔴 Critical |
| | Rename notebook | 🔴 Critical |
| | Duplicate notebook | 🟡 High |
| | Move between folders | 🟡 High |
| **Properties/Config** | Edit YAML frontmatter | 🔴 Critical |
| | Edit filter configs | 🔴 Critical |
| | Edit exhibit configs | 🔴 Critical |
| | Visual config builder | 🟡 High |
| **Organization** | Create folders | 🟡 High |
| | Folder tree navigation | 🟡 High |
| | Search notebooks | 🟡 High |
| | Tags/labels | 🟢 Medium |
| | Favorites | 🟢 Medium |
| | Recent notebooks | 🟢 Medium |
| **Canvas Features** | Drag/drop layout | 🔴 Critical |
| | Draw connections | 🔴 Critical |
| | Add nodes dynamically | 🔴 Critical |
| | Resize widgets | 🟡 High |
| | Grouping/frames | 🟡 High |
| | Freeform annotations | 🟢 Medium |
| **Data Interaction** | Drill-down on click | 🟡 High |
| | Cross-filtering | 🟡 High |
| | Export chart/data | 🟡 High |
| | Refresh data | 🟡 High |
| **Editing** | Undo/redo | 🔴 Critical |
| | Autosave | 🔴 Critical |
| | Version history | 🟢 Medium |
| **Collaboration** | Share link | 🟢 Medium |
| | Comments | 🟢 Medium |
| **Export** | PDF export | 🟡 High |
| | PNG/SVG export | 🟡 High |
| **System** | Templates | 🟡 High |
| | Keyboard shortcuts | 🟡 High |

---

## Architecture Overview

### Current Architecture (Streamlit)
```
┌─────────────────────────────────────────┐
│         Streamlit (Python)              │
│  - UI rendering                         │
│  - State management                     │
│  - Direct DuckDB calls                  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         DuckDB + Parquet                │
└─────────────────────────────────────────┘
```

### New Architecture (React + FastAPI + DuckDB)
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Frontend                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ ReactFlow   │  │ Plotly.js   │  │ Tabulator   │             │
│  │ (Canvas)    │  │ (Charts)    │  │ (Tables)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  State: Zustand    Styling: Tailwind + shadcn/ui                │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ /notebooks  │  │ /query      │  │ /canvas     │             │
│  │ CRUD        │  │ Execute SQL │  │ Persistence │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  Uses: UniversalSession, FilterEngine, Models (unchanged)       │
└─────────────────────────────┬───────────────────────────────────┘
                              │ SQL
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DuckDB + Parquet (unchanged)                    │
│                  storage/bronze, storage/silver                  │
└─────────────────────────────────────────────────────────────────┘
```

### What Changes vs. What Stays

| Layer | Changes | Stays Same |
|-------|---------|------------|
| **Frontend** | Complete rewrite in React | — |
| **API** | New FastAPI layer | — |
| **Session** | — | UniversalSession, FilterEngine |
| **Models** | — | All model code, measures |
| **Storage** | — | DuckDB, Parquet files |
| **Configs** | Minor syntax additions | Markdown notebooks, YAML |

---

## Technical Stack

### Frontend
```json
{
  "framework": "React 18+ with TypeScript",
  "build": "Vite",
  "canvas": "ReactFlow",
  "charts": "Plotly.js (react-plotly.js)",
  "tables": "Tabulator (react-tabulator)",
  "maps": "Mapbox GL JS + DeckGL",
  "styling": "Tailwind CSS + shadcn/ui",
  "state": "Zustand",
  "forms": "React Hook Form + Zod",
  "markdown": "react-markdown + remark-gfm",
  "editors": {
    "markdown": "Milkdown or BlockNote",
    "yaml": "Monaco Editor",
    "code": "Monaco Editor"
  },
  "icons": "Lucide React"
}
```

### Backend
```python
# requirements-api.txt
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.0
python-multipart
aiofiles
websockets  # Future: real-time collaboration

# Existing (unchanged)
duckdb
pyarrow
pyyaml
```

### Development
```
IDE: VS Code (monorepo)
Node: v20 LTS
Python: 3.11+
Package Manager: pnpm (frontend), pip (backend)
```

---

## ReactFlow Container Patterns

### Node Types

```typescript
// frontend/src/types/nodes.ts
export type NodeType =
  | 'markdown'    // Text content
  | 'filter'      // Dimension selector
  | 'exhibit'     // Chart (Plotly)
  | 'grid'        // Table (Tabulator)
  | 'map'         // Geographic map
  | 'group'       // Container for other nodes
  | 'frame'       // Visual annotation frame
  | 'note';       // Sticky note annotation

export interface BaseNodeData {
  id: string;
  label?: string;
}

export interface ExhibitNodeData extends BaseNodeData {
  chartType: 'bar' | 'line' | 'scatter' | 'pie' | 'area' | 'heatmap';
  query: string;
  x: string;
  y: string | string[];
  color?: string;
  title?: string;
}

export interface FilterNodeData extends BaseNodeData {
  dimension: string;
  type: 'select' | 'multiselect' | 'date_range' | 'slider';
  selected?: any;
}

export interface GridNodeData extends BaseNodeData {
  query: string;
  columns: ColumnDef[];
  groupBy?: string;
  showFooter?: boolean;
}

export interface GroupNodeData extends BaseNodeData {
  label: string;
  collapsed?: boolean;
  style?: 'default' | 'dashed' | 'solid';
}
```

### Parent-Child Grouping

```typescript
// Nodes can be nested inside group nodes
const nodes = [
  {
    id: 'group-sector-analysis',
    type: 'group',
    position: { x: 100, y: 100 },
    style: { width: 600, height: 400 },
    data: { label: 'Sector Analysis' }
  },
  {
    id: 'filter-sector',
    type: 'filter',
    position: { x: 20, y: 50 },      // Relative to parent
    parentId: 'group-sector-analysis', // Key: parent reference
    extent: 'parent',                  // Constrain to parent bounds
    data: { dimension: 'sector', type: 'select' }
  },
  {
    id: 'chart-revenue',
    type: 'exhibit',
    position: { x: 200, y: 50 },
    parentId: 'group-sector-analysis',
    extent: 'parent',
    data: {
      chartType: 'bar',
      query: 'SELECT sector, SUM(revenue) FROM ...',
      x: 'sector',
      y: 'revenue'
    }
  }
];
```

### Group Node Component

```tsx
// frontend/src/components/nodes/GroupNode.tsx
import { NodeResizer } from '@reactflow/node-resizer';
import { memo, useState } from 'react';
import { NodeProps, useReactFlow } from 'reactflow';

export const GroupNode = memo(({ id, data, selected }: NodeProps<GroupNodeData>) => {
  const [collapsed, setCollapsed] = useState(data.collapsed ?? false);
  const { setNodes } = useReactFlow();

  const toggleCollapse = () => {
    const newCollapsed = !collapsed;
    setCollapsed(newCollapsed);

    // Hide/show child nodes
    setNodes(nodes => nodes.map(node => {
      if (node.parentId === id) {
        return { ...node, hidden: newCollapsed };
      }
      return node;
    }));
  };

  return (
    <>
      <NodeResizer
        minWidth={200}
        minHeight={150}
        isVisible={selected}
        lineClassName="border-blue-500"
        handleClassName="bg-blue-500"
      />
      <div className={`
        rounded-lg border-2 border-dashed border-blue-400
        bg-blue-50/50 min-h-full
        ${collapsed ? 'h-12' : ''}
      `}>
        <div className="flex items-center justify-between px-3 py-2 border-b border-blue-300">
          <span className="font-semibold text-blue-700">{data.label}</span>
          <button
            onClick={toggleCollapse}
            className="text-blue-500 hover:text-blue-700"
          >
            {collapsed ? '▶' : '▼'}
          </button>
        </div>
        {!collapsed && (
          <div className="p-2">
            {/* Child nodes render here via parentId */}
          </div>
        )}
      </div>
    </>
  );
});
```

### Edge Types

```typescript
// frontend/src/types/edges.ts
export type EdgeType =
  | 'dataFlow'    // Solid line: filter → exhibit data connection
  | 'insight'     // Dashed line: user-drawn insight/annotation
  | 'dependency'; // Dotted line: model/query dependency

export interface InsightEdgeData {
  label?: string;
  color?: string;
}
```

```tsx
// frontend/src/components/edges/InsightEdge.tsx
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from 'reactflow';

export function InsightEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data, style
}) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          strokeDasharray: '5,5',
          stroke: data?.color ?? '#64748b'
        }}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
            className="bg-white px-2 py-1 rounded border text-sm"
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
```

### Canvas State Structure

```typescript
// frontend/src/stores/canvasStore.ts
import { create } from 'zustand';
import { Node, Edge } from 'reactflow';

interface CanvasState {
  nodes: Node[];
  edges: Edge[];

  // Actions
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  addNode: (node: Node) => void;
  updateNode: (id: string, data: Partial<Node>) => void;
  deleteNode: (id: string) => void;
  addEdge: (edge: Edge) => void;
  deleteEdge: (id: string) => void;

  // History for undo/redo
  history: { nodes: Node[], edges: Edge[] }[];
  historyIndex: number;
  undo: () => void;
  redo: () => void;

  // Persistence
  loadCanvas: (notebookId: string) => Promise<void>;
  saveCanvas: () => Promise<void>;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  history: [],
  historyIndex: -1,

  // ... implementation
}));
```

---

## Component Migration Guide

### Charts: Plotly (Direct Transfer)

Plotly configs transfer nearly 1:1:

```python
# Current Python
fig = px.bar(df, x='sector', y='revenue', color='region')
st.plotly_chart(fig)
```

```tsx
// New React
import Plot from 'react-plotly.js';

function ExhibitNode({ data }: NodeProps<ExhibitNodeData>) {
  const { data: chartData } = useQuery(['chart', data.query], () =>
    fetchQuery(data.query)
  );

  return (
    <Plot
      data={[{
        type: 'bar',
        x: chartData.map(d => d[data.x]),
        y: chartData.map(d => d[data.y]),
        marker: { color: data.color }
      }]}
      layout={{
        title: data.title,
        autosize: true,
      }}
      useResizeHandler
      style={{ width: '100%', height: '100%' }}
    />
  );
}
```

### Tables: Great Tables → Tabulator

```python
# Current Python (Great Tables)
GT(df).tab_header(title="Revenue").fmt_currency(columns="revenue")
```

```tsx
// New React (Tabulator)
import { ReactTabulator } from 'react-tabulator';
import 'react-tabulator/lib/styles.css';

function GridNode({ data }: NodeProps<GridNodeData>) {
  const { data: tableData } = useQuery(['table', data.query], () =>
    fetchQuery(data.query)
  );

  const columns = data.columns.map(col => ({
    title: col.label,
    field: col.field,
    formatter: col.format === 'currency' ? 'money' : undefined,
    formatterParams: col.format === 'currency' ? { symbol: '$' } : undefined,
    bottomCalc: col.showTotal ? 'sum' : undefined,
    headerFilter: data.filterable ? true : undefined,
  }));

  return (
    <div className="grid-node">
      {data.title && <h3 className="font-semibold mb-2">{data.title}</h3>}
      <ReactTabulator
        data={tableData}
        columns={columns}
        layout="fitDataFill"
        groupBy={data.groupBy}
        options={{
          pagination: data.paginate ? 'local' : false,
          paginationSize: 20,
        }}
      />
    </div>
  );
}
```

### Tabulator Feature Mapping

| Great Tables | Tabulator Equivalent |
|--------------|---------------------|
| `tab_header(title=)` | Wrapper `<h3>` or custom header |
| `tab_spanner(label=, columns=)` | `{ title: "Group", columns: [...] }` |
| `fmt_currency()` | `formatter: "money"` |
| `fmt_percent()` | `formatter: "progress"` or custom |
| `data_color(palette=)` | `formatter` function with style |
| `tab_footnote()` | Custom footer component |
| `cols_label()` | `title` in column def |
| Row grouping | `groupBy` option |
| Footer calculations | `bottomCalc: "sum"/"avg"/"count"` |

### Maps: New Capability

```tsx
// frontend/src/components/nodes/MapNode.tsx
import Map, { Layer, Source } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

function MapNode({ data }: NodeProps<MapNodeData>) {
  const { data: geoData } = useQuery(['map', data.query], () =>
    fetchQuery(data.query)
  );

  return (
    <Map
      mapboxAccessToken={MAPBOX_TOKEN}
      initialViewState={{
        longitude: -98.5,
        latitude: 39.8,
        zoom: 3.5
      }}
      style={{ width: '100%', height: '100%' }}
      mapStyle="mapbox://styles/mapbox/light-v11"
    >
      <Source type="geojson" data={geoData}>
        <Layer
          type="fill"
          paint={{
            'fill-color': [
              'interpolate',
              ['linear'],
              ['get', data.valueField],
              0, '#f7fbff',
              100, '#08306b'
            ],
            'fill-opacity': 0.7
          }}
        />
      </Source>
    </Map>
  );
}
```

### Filters: Enhanced

```tsx
// frontend/src/components/nodes/FilterNode.tsx
import { Select, MultiSelect, DateRangePicker, Slider } from '@/components/ui';

function FilterNode({ data, id }: NodeProps<FilterNodeData>) {
  const { dimensions } = useDimensions();
  const { setFilterValue, getConnectedNodes } = useCanvasStore();

  const handleChange = (value: any) => {
    setFilterValue(id, value);

    // Trigger re-query on connected exhibit nodes
    const connected = getConnectedNodes(id);
    connected.forEach(nodeId => invalidateQueries(['chart', nodeId]));
  };

  const options = dimensions[data.dimension]?.values ?? [];

  switch (data.type) {
    case 'select':
      return (
        <Select
          label={data.label ?? data.dimension}
          options={options}
          value={data.selected}
          onChange={handleChange}
        />
      );
    case 'multiselect':
      return (
        <MultiSelect
          label={data.label ?? data.dimension}
          options={options}
          value={data.selected ?? []}
          onChange={handleChange}
        />
      );
    case 'date_range':
      return (
        <DateRangePicker
          label={data.label ?? 'Date Range'}
          value={data.selected}
          onChange={handleChange}
        />
      );
    case 'slider':
      return (
        <Slider
          label={data.label ?? data.dimension}
          min={data.min}
          max={data.max}
          value={data.selected}
          onChange={handleChange}
        />
      );
  }
}
```

---

## API Specification

### Endpoints

```yaml
# Notebooks
GET    /api/notebooks              # List all notebooks
GET    /api/notebooks/{id}         # Get notebook content + canvas state
POST   /api/notebooks              # Create notebook
PUT    /api/notebooks/{id}         # Update notebook
DELETE /api/notebooks/{id}         # Delete notebook
POST   /api/notebooks/{id}/duplicate  # Duplicate notebook

# Folders
GET    /api/folders                # List folder tree
POST   /api/folders                # Create folder
PUT    /api/folders/{id}           # Rename/move folder
DELETE /api/folders/{id}           # Delete folder

# Queries
POST   /api/query                  # Execute SQL query
POST   /api/query/validate         # Validate SQL without executing

# Dimensions
GET    /api/dimensions             # List available dimensions
GET    /api/dimensions/{name}      # Get dimension values

# Canvas
PUT    /api/notebooks/{id}/canvas  # Save canvas layout
GET    /api/notebooks/{id}/canvas  # Get canvas layout

# Export
POST   /api/export/pdf             # Export canvas to PDF
POST   /api/export/png             # Export canvas to PNG
POST   /api/export/data            # Export query results
```

### Request/Response Models

```python
# api/models/notebooks.py
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class NotebookBase(BaseModel):
    title: str
    folder_id: Optional[str] = None
    tags: List[str] = []

class NotebookCreate(NotebookBase):
    content: str  # Markdown content

class NotebookUpdate(NotebookBase):
    content: Optional[str] = None
    canvas_state: Optional[dict] = None

class NotebookResponse(NotebookBase):
    id: str
    content: str
    canvas_state: Optional[dict]
    created_at: datetime
    updated_at: datetime

class QueryRequest(BaseModel):
    sql: str
    params: Optional[dict] = None
    limit: int = 10000

class QueryResponse(BaseModel):
    data: List[dict]
    columns: List[dict]  # name, type
    row_count: int
    execution_time_ms: float

class DimensionResponse(BaseModel):
    name: str
    display_name: str
    values: List[Any]
    type: str  # string, number, date
```

### FastAPI Implementation

```python
# api/routers/queries.py
from fastapi import APIRouter, HTTPException
from core.session.universal_session import UniversalSession
import time

router = APIRouter(prefix="/api")
session = UniversalSession(backend="duckdb")

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    start = time.time()
    try:
        df = session.query(request.sql, params=request.params)
        if len(df) > request.limit:
            df = df.head(request.limit)

        return QueryResponse(
            data=df.to_dict(orient="records"),
            columns=[
                {"name": col, "type": str(df[col].dtype)}
                for col in df.columns
            ],
            row_count=len(df),
            execution_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/dimensions/{name}", response_model=DimensionResponse)
async def get_dimension(name: str):
    # Use existing dimension metadata from models
    values = session.get_dimension_values(name)
    return DimensionResponse(
        name=name,
        display_name=name.replace("_", " ").title(),
        values=values,
        type="string"
    )
```

---

## Phased Implementation Plan

### Phase 1: Foundation (Weeks 1-4)
**Goal**: React app with feature parity to current Streamlit

```
Week 1-2: Project Setup
├── Initialize Vite + React + TypeScript
├── Configure Tailwind + shadcn/ui
├── Set up FastAPI with basic routers
├── Notebook CRUD endpoints
├── Query execution endpoint
└── Project structure and conventions

Week 3-4: Core Views
├── Notebook tree sidebar
├── Document view (linear markdown rendering)
├── Filter components
├── Exhibit components (Plotly charts)
├── Grid components (Tabulator tables)
└── Basic navigation and routing
```

**Deliverable**: Browse and view existing notebooks in React

### Phase 2: Editing & Management (Weeks 5-8)
**Goal**: Full content management in-app

```
Week 5-6: Content Editing
├── Markdown editor integration (Milkdown/BlockNote)
├── YAML/properties panel (Monaco)
├── Create new notebook
├── Delete/rename notebook
├── Autosave with debounce
└── Undo/redo system

Week 7-8: Organization
├── Folder creation and management
├── Drag-drop in tree view
├── Search functionality
├── Templates system
├── Duplicate notebook
└── Recent/favorites
```

**Deliverable**: Full notebook CRUD entirely in-app

### Phase 3: Canvas/Whiteboard (Weeks 9-13)
**Goal**: ReactFlow whiteboard implementation

```
Week 9-10: Canvas Foundation
├── ReactFlow integration
├── Markdown → nodes parser
├── Custom node types (filter, exhibit, grid, markdown)
├── Auto-layout algorithm (dagre)
├── Manual drag positioning
└── Position persistence to markdown

Week 11-12: Connections & Interaction
├── Data flow edges (filter → exhibit)
├── Insight edges (user annotations)
├── Cross-filtering via connections
├── Node resize handles
├── Group nodes (containers)
└── Minimap and controls

Week 13: Polish
├── Keyboard shortcuts
├── Context menus
├── View toggle (document/canvas/split)
├── Canvas templates
└── Performance optimization
```

**Deliverable**: Full whiteboard experience with drawable connections

### Phase 4: Advanced Features (Weeks 14-17)
**Goal**: Production-ready polish

```
Week 14-15: Data Interaction
├── Click-through drill-down
├── Chart ↔ filter synchronization
├── Data refresh controls
├── Export (PNG, PDF, CSV)
└── Embed code generation

Week 16-17: Maps & Visualization
├── Map node type (Mapbox GL)
├── Choropleth support
├── Point/marker layers
├── DeckGL integration (3D, heatmaps)
└── GeoJSON upload
```

**Deliverable**: Full-featured data exploration platform

### Phase 5: Collaboration (Weeks 18-20, Optional)
**Goal**: Multi-user features

```
├── User authentication
├── Share links (view-only, edit)
├── Comments on nodes
├── Real-time cursors (WebSocket)
└── Permission system
```

---

## Development Environment

### Recommended Setup

**IDE**: VS Code (monorepo for frontend + backend)

```bash
# Install VS Code extensions
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension bradlc.vscode-tailwindcss
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
```

### Project Structure

```
de_Funk/
├── frontend/                    # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── canvas/         # ReactFlow setup
│   │   │   ├── nodes/          # Custom node types
│   │   │   ├── edges/          # Custom edge types
│   │   │   ├── panels/         # Sidebar panels
│   │   │   ├── editors/        # Markdown, YAML editors
│   │   │   └── ui/             # shadcn/ui components
│   │   ├── views/
│   │   │   ├── DocumentView/
│   │   │   ├── CanvasView/
│   │   │   └── SplitView/
│   │   ├── hooks/
│   │   ├── stores/             # Zustand stores
│   │   ├── services/           # API client
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── api/                         # FastAPI backend
│   ├── routers/
│   │   ├── notebooks.py
│   │   ├── queries.py
│   │   ├── dimensions.py
│   │   └── export.py
│   ├── services/
│   ├── models/
│   └── main.py
│
├── app/                         # Legacy Streamlit (deprecated)
├── configs/                     # Notebooks, models (unchanged)
├── core/                        # Session, filters (unchanged)
├── models/                      # Domain models (unchanged)
└── storage/                     # Data (unchanged)
```

### Development Workflow

```bash
# Terminal 1: Frontend dev server
cd frontend
pnpm install
pnpm dev  # http://localhost:5173

# Terminal 2: Backend dev server
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000  # http://localhost:8000

# Terminal 3: Existing DuckDB (if needed)
# DuckDB is file-based, no server needed
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ReactFlow learning curve | Medium | Medium | Prototype early, validate with complex layouts |
| State management complexity | Medium | High | Start simple with Zustand, add complexity as needed |
| Parser compatibility | Low | High | Keep Python parser, call via API |
| Performance with many nodes | Medium | Medium | Virtual rendering, lazy loading, benchmarking |
| Tabulator styling parity | Medium | Low | Invest in CSS theme early |
| Map integration complexity | Medium | Medium | Start with basic choropleth, add features incrementally |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Time to create notebook | N/A (external) | < 30 seconds | In-app creation |
| Time to edit content | N/A (external) | < 5 seconds | In-app editing |
| Canvas interactions/minute | N/A | > 20 | Drag, connect, resize |
| Page load time | ~3s | < 1s | Lighthouse |
| Bundle size | N/A | < 500KB gzipped | Build output |
| Test coverage | ~20% | > 70% | Jest + pytest |

---

## UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  de_Funk                    [🔍 Search...]           [+ New] [⚙️] [👤]      │
├────────────────┬────────────────────────────────────────────────────────────┤
│                │  Market Analysis            [📄 Doc] [🎨 Canvas] [⊞ Split] │
│  📁 Notebooks  │────────────────────────────────────────────────────────────│
│  ├─ 📁 Equity  │                                                            │
│  │  ├─ 📄 Over.│  ┌────────────────────────────────────────────────────┐   │
│  │  └─ 📄 Tech │  │                  CANVAS VIEW                       │   │
│  ├─ 📁 Macro   │  │                                                    │   │
│  └─ 📄 Dashb.. │  │  ┌─── Sector Analysis ─────────────────────────┐  │   │
│                │  │  │                                              │  │   │
│  ───────────── │  │  │  [Sector ▼]────────┐                        │  │   │
│  ⭐ Favorites  │  │  │  [Technology]       │                        │  │   │
│  ├─ 📄 Daily   │  │  │  [Healthcare]       ▼                        │  │   │
│  └─ 📄 Weekly  │  │  │              ┌─────────────┐                 │  │   │
│                │  │  │              │ ████ Bar    │                 │  │   │
│  🕐 Recent     │  │  │              │ ██████      │                 │  │   │
│  ├─ 📄 Q4 Rev  │  │  │              │ ███         │                 │  │   │
│  └─ 📄 Forecast│  │  │              └──────┬──────┘                 │  │   │
│                │  │  │                     │                        │  │   │
│                │  │  └─────────────────────┼────────────────────────┘  │   │
│                │  │                        │                           │   │
│                │  │         ┌──────────────┴──────────────┐           │   │
│                │  │         ▼                             ▼           │   │
│                │  │  ┌─────────────┐           ┌─────────────────┐   │   │
│                │  │  │ 🗺️ Map     │◀ ─ ─ ─ ─ ─│ Grid Table      │   │   │
│                │  │  │ [Choropleth]│  insight  │ AAPL  $185.50   │   │   │
│                │  │  │             │   arrow   │ MSFT  $420.00   │   │   │
│                │  │  └─────────────┘           │ GOOGL $175.25   │   │   │
│                │  │                            └─────────────────┘   │   │
│                │  │                                                    │   │
│                │  └────────────────────────────────────────────────────┘   │
│                │  [🔍 100%] [⊡ Fit] [🔒 Lock] [📤 Export ▼]               │
├────────────────┴────────────────────────────────────────────────────────────┤
│  Properties Panel (collapsible)                                             │
│  ┌─ Selected: revenue-chart ────────────────────────────────────────────┐  │
│  │ Type: [Bar ▼]    X: [sector ▼]    Y: [revenue ▼]    Color: [🎨]     │  │
│  │ Title: [Revenue by Sector           ]  Legend: [✓]  Animate: [✓]    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Markdown Syntax Extensions

Minimal additions to support canvas positions (backward compatible):

```markdown
---
title: Market Analysis
canvas:
  default_view: canvas  # or "document" or "split"
  auto_layout: dagre    # or "manual"
---

# Overview

Analysis of sector performance and trends.

$filter${
  "id": "sector-filter",
  "type": "multiselect",
  "dimension": "sector",
  "canvas": { "x": 100, "y": 100, "width": 200 }
}

$exhibit${
  "id": "revenue-chart",
  "type": "bar",
  "x": "sector",
  "y": "revenue",
  "connects_from": ["sector-filter"],
  "canvas": { "x": 400, "y": 100, "width": 400, "height": 300 }
}

$grid${
  "id": "company-table",
  "columns": ["ticker", "revenue", "growth"],
  "connects_from": ["sector-filter"],
  "canvas": { "x": 400, "y": 450, "width": 400 }
}

$insight${
  "from": "revenue-chart",
  "to": "company-table",
  "label": "Click to drill down"
}
```

---

## References

- [ReactFlow Documentation](https://reactflow.dev/)
- [Tabulator Documentation](http://tabulator.info/)
- [Plotly.js React](https://plotly.com/javascript/react/)
- [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [Zustand State Management](https://zustand-demo.pmnd.rs/)

---

## Appendix A: Node Type Specifications

### ExhibitNode (Charts)

```typescript
interface ExhibitNodeData {
  id: string;
  chartType: 'bar' | 'line' | 'scatter' | 'pie' | 'area' | 'heatmap' | 'box' | 'histogram';
  query: string;

  // Axes
  x: string;
  y: string | string[];  // Multiple Y for multi-series
  color?: string;        // Color dimension
  size?: string;         // Size dimension (scatter)

  // Labels
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;

  // Options
  showLegend?: boolean;
  animate?: boolean;
  stacked?: boolean;     // For bar/area

  // Canvas
  canvas?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };

  // Connections
  connects_from?: string[];  // Filter node IDs
}
```

### GridNode (Tables)

```typescript
interface GridNodeData {
  id: string;
  query: string;

  // Columns
  columns: {
    field: string;
    label?: string;
    format?: 'currency' | 'percent' | 'number' | 'date' | 'text';
    align?: 'left' | 'center' | 'right';
    width?: number;
    sortable?: boolean;
    showTotal?: boolean;
  }[];

  // Grouping
  groupBy?: string;

  // Features
  sortable?: boolean;
  filterable?: boolean;
  paginate?: boolean;
  pageSize?: number;

  // Footer
  showFooter?: boolean;

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
  connects_from?: string[];
}
```

### MapNode (Geographic)

```typescript
interface MapNodeData {
  id: string;
  mapType: 'choropleth' | 'points' | 'heatmap' | 'arc';
  query: string;

  // Geography
  geoField: string;       // Field containing geo identifiers
  geoType: 'us_states' | 'us_counties' | 'countries' | 'custom';
  customGeoJson?: string; // URL or inline GeoJSON

  // Value
  valueField: string;
  colorScale?: string;    // 'blues', 'reds', 'viridis', etc.

  // Points (for point maps)
  latField?: string;
  lonField?: string;
  sizeField?: string;

  // Options
  showLegend?: boolean;
  interactive?: boolean;

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
  connects_from?: string[];
}
```

### FilterNode

```typescript
interface FilterNodeData {
  id: string;
  dimension: string;
  type: 'select' | 'multiselect' | 'date_range' | 'slider' | 'text';

  // Display
  label?: string;
  placeholder?: string;

  // Options (for select types)
  options?: { value: any; label: string; }[];
  optionsQuery?: string;  // Dynamic options from query

  // Range (for slider/date)
  min?: number | string;
  max?: number | string;
  step?: number;

  // State
  selected?: any;
  defaultValue?: any;

  // Canvas
  canvas?: { x: number; y: number; width: number; };
}
```

### GroupNode (Container)

```typescript
interface GroupNodeData {
  id: string;
  label: string;

  // Style
  style?: 'default' | 'dashed' | 'solid' | 'none';
  color?: string;

  // State
  collapsed?: boolean;
  locked?: boolean;  // Prevent child dragging outside

  // Canvas
  canvas?: { x: number; y: number; width: number; height: number; };
}
```

---

## Appendix B: Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + S` | Save notebook |
| `Ctrl/Cmd + Z` | Undo |
| `Ctrl/Cmd + Shift + Z` | Redo |
| `Ctrl/Cmd + D` | Duplicate selected node |
| `Delete / Backspace` | Delete selected node |
| `Ctrl/Cmd + G` | Group selected nodes |
| `Ctrl/Cmd + Shift + G` | Ungroup |
| `Ctrl/Cmd + A` | Select all nodes |
| `Escape` | Deselect all |
| `Ctrl/Cmd + +` | Zoom in |
| `Ctrl/Cmd + -` | Zoom out |
| `Ctrl/Cmd + 0` | Fit view |
| `Space + Drag` | Pan canvas |
| `Ctrl/Cmd + Click` | Multi-select |
| `Ctrl/Cmd + E` | Toggle edit mode |
| `Ctrl/Cmd + 1` | Document view |
| `Ctrl/Cmd + 2` | Canvas view |
| `Ctrl/Cmd + 3` | Split view |

---

## Appendix C: Migration Checklist

### Pre-Migration
- [ ] Audit all existing notebooks
- [ ] Document custom Streamlit components
- [ ] List all Great Tables usages
- [ ] Identify Python-only rendering
- [ ] Set up VS Code workspace

### Phase 1 Checklist
- [ ] Vite + React + TypeScript initialized
- [ ] Tailwind + shadcn/ui configured
- [ ] FastAPI with CORS configured
- [ ] `/api/notebooks` CRUD working
- [ ] `/api/query` executing SQL
- [ ] Basic notebook tree rendering
- [ ] Document view rendering markdown
- [ ] Filter components functional
- [ ] Plotly charts rendering
- [ ] Tabulator tables rendering

### Phase 2 Checklist
- [ ] Markdown editor integrated
- [ ] YAML editor for properties
- [ ] Create notebook working
- [ ] Delete notebook working
- [ ] Autosave implemented
- [ ] Undo/redo functional
- [ ] Folder management working
- [ ] Search implemented
- [ ] Templates system working

### Phase 3 Checklist
- [ ] ReactFlow canvas rendering
- [ ] All node types implemented
- [ ] Edge drawing working
- [ ] Cross-filtering via edges
- [ ] Node resize working
- [ ] Group nodes working
- [ ] Position persistence working
- [ ] View toggle working
- [ ] Keyboard shortcuts implemented

### Phase 4 Checklist
- [ ] Click drill-down working
- [ ] Export to PNG/PDF working
- [ ] Map node type working
- [ ] Choropleth rendering
- [ ] Point maps rendering
- [ ] Performance optimized

### Post-Migration
- [ ] All existing notebooks render correctly
- [ ] Feature parity verified
- [ ] Performance benchmarked
- [ ] Documentation updated
- [ ] Streamlit code deprecated
