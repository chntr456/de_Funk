/**
 * AG Grid renderer for table.data and table.pivot exhibits.
 *
 * Uses AG Grid Community for native horizontal scroll, frozen columns,
 * column grouping (spanners), sorting, and proper viewport handling.
 */
import { createGrid, ModuleRegistry, AllCommunityModule, type GridOptions, type ColDef, type ColGroupDef } from "ag-grid-community";
import type { DeFunkBlock, TableResponse } from "../contract";
import { formatValue } from "./format";

// AG Grid CSS — imported as text by esbuild, injected into document once
import agGridCss from "ag-grid-community/styles/ag-grid.css";
import agThemeCss from "ag-grid-community/styles/ag-theme-alpine.css";

let initialized = false;

function initAgGrid(): void {
  if (initialized) return;
  initialized = true;

  ModuleRegistry.registerModules([AllCommunityModule]);

  const style = document.createElement("style");
  style.id = "de-funk-ag-grid-styles";
  style.textContent = agGridCss + "\n" + agThemeCss;
  document.head.appendChild(style);
}

/**
 * Render a table.data or table.pivot response using AG Grid.
 */
export function renderAgGrid(
  block: DeFunkBlock,
  response: TableResponse,
  el: HTMLElement,
): void {
  initAgGrid();

  const formatting = block.formatting ?? {};
  const title = formatting.title;
  const maxH = formatting.max_height ?? 500;

  if (title) {
    el.createEl("h4", { text: title, cls: "de-funk-table-title" });
  }

  const { columns, rows } = response;

  if (!columns || !rows || rows.length === 0) {
    el.createDiv({ cls: "de-funk-empty", text: "No data returned" });
    return;
  }

  // Detect pivot-style columns (key contains "||" separator)
  const hasPivotCols = columns.some(c => c.key.includes("||"));

  let columnDefs: (ColDef | ColGroupDef)[];

  if (hasPivotCols) {
    // Pivot: group data columns by measure, pin row labels
    const groups: Record<string, ColDef[]> = {};
    const rowCols: ColDef[] = [];

    columns.forEach((col, idx) => {
      if (col.key.includes("||")) {
        const [measure, value] = col.key.split("||", 2);
        if (!groups[measure]) groups[measure] = [];
        groups[measure].push({
          headerName: value || col.label,
          field: col.key,
          width: 90,
          minWidth: 70,
          type: typeof rows[0]?.[idx] === "number" ? "numericColumn" : undefined,
          valueFormatter: (params) => {
            const v = params.value;
            if (col.format) return formatValue(v, col.format);
            return typeof v === "number" ? v.toLocaleString() : String(v ?? "");
          },
          sortable: true,
          resizable: true,
        });
      } else {
        rowCols.push({
          headerName: col.label || col.key,
          field: col.key,
          pinned: "left",
          lockPinned: true,
          width: 200,
          minWidth: 150,
          sortable: true,
          resizable: true,
          cellStyle: { fontWeight: "500" },
        });
      }
    });

    // Build column groups (spanners)
    const groupDefs: ColGroupDef[] = Object.entries(groups).map(([measure, children]) => ({
      headerName: measure.replace(/_/g, " ").toUpperCase(),
      markerNode: true,
      children,
    }));

    columnDefs = [...rowCols, ...groupDefs];
  } else {
    // Flat table
    columnDefs = columns.map((col, idx) => ({
      headerName: col.label || col.key,
      field: col.key,
      pinned: idx === 0 ? ("left" as const) : undefined,
      lockPinned: idx === 0 ? true : undefined,
      width: idx === 0 ? 200 : undefined,
      minWidth: idx === 0 ? 150 : 80,
      valueFormatter: col.format
        ? (params: { value: unknown }) => formatValue(params.value, col.format ?? null)
        : undefined,
      type: typeof rows[0]?.[idx] === "number" ? "numericColumn" : undefined,
      sortable: true,
      resizable: true,
    }));
  }

  // Build row data
  const rowData = rows.map((row) => {
    const obj: Record<string, unknown> = {};
    columns.forEach((col, idx) => {
      obj[col.key] = row[idx];
    });
    return obj;
  });

  // Grid container — fixed height for proper scrolling
  const gridDiv = el.createDiv({ cls: "de-funk-ag-grid" });
  const gridHeight = Math.min(maxH, rows.length * 28 + 80);
  gridDiv.style.cssText = `height:${gridHeight}px; width:100%;`;

  // Theme
  const isDark = document.body.classList.contains("theme-dark");
  gridDiv.classList.add(isDark ? "ag-theme-alpine-dark" : "ag-theme-alpine");

  // Grid options
  const gridOptions: GridOptions = {
    columnDefs,
    rowData,
    defaultColDef: {
      sortable: true,
      resizable: true,
      minWidth: 70,
      suppressMovable: true,
    },
    // Layout
    domLayout: "normal",
    suppressHorizontalScroll: false,
    alwaysShowHorizontalScroll: true,
    alwaysShowVerticalScroll: false,
    // Interaction
    animateRows: false,
    suppressCellFocus: false,
    enableCellTextSelection: true,
    ensureDomOrder: true,
    // Header stays fixed while scrolling
    suppressColumnVirtualisation: false,
  };

  // Pivot: pin TOTAL rows to bottom, sort by last year desc
  if (hasPivotCols) {
    const firstKey = columns[0]?.key;
    if (firstKey) {
      gridOptions.pinnedBottomRowData = rowData.filter(r => r[firstKey] === "TOTAL");
      gridOptions.rowData = rowData.filter(r => r[firstKey] !== "TOTAL");
    }

    const lastCol = columns.filter(c => c.key.includes("||")).pop();
    if (lastCol) {
      gridOptions.initialState = {
        sort: { sortModel: [{ colId: lastCol.key, sort: "desc" }] },
      };
    }
  }

  createGrid(gridDiv, gridOptions);

  // Truncation warning
  if (response.truncated) {
    const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
    warn.setText("Results were capped by the server row limit. Apply a filter to narrow the data.");
  }
}

/**
 * Render a pivot table using AG Grid.
 */
export function renderAgGridPivot(
  block: DeFunkBlock,
  response: TableResponse,
  el: HTMLElement,
): void {
  renderAgGrid(block, response, el);
}
