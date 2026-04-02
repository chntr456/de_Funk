/**
 * AG Grid renderer for table.data and table.pivot exhibits.
 *
 * Replaces the manual HTML table rendering with AG Grid Community,
 * which provides native horizontal scroll (always visible), frozen
 * columns, sorting, and proper viewport handling out of the box.
 */
import { createGrid, ModuleRegistry, AllCommunityModule, type GridOptions, type ColDef } from "ag-grid-community";
import type { DeFunkBlock, TableResponse } from "../contract";
import { formatValue } from "./format";

// AG Grid CSS — imported as text by esbuild, injected into document once
import agGridCss from "ag-grid-community/styles/ag-grid.css";
import agThemeCss from "ag-grid-community/styles/ag-theme-alpine.css";

let initialized = false;

function initAgGrid(): void {
  if (initialized) return;
  initialized = true;

  // Register all community modules
  ModuleRegistry.registerModules([AllCommunityModule]);

  // Inject CSS
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


  const tableResponse = response as TableResponse;
  const { columns, rows } = tableResponse;

  if (!columns || !rows || rows.length === 0) {
    el.createDiv({ cls: "de-funk-empty", text: "No data returned" });
    return;
  }

  // Build AG Grid column definitions
  // Detect pivot-style columns (key contains "||" separator: measure||colValue)
  const hasPivotCols = columns.some(c => c.key.includes("||"));

  let columnDefs: (ColDef | { headerName: string; children: ColDef[] })[];

  if (hasPivotCols) {
    // Group columns by measure prefix
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
          suppressSizeToFit: true,
          type: typeof rows[0]?.[idx] === "number" ? "numericColumn" : undefined,
          valueFormatter: col.format
            ? (params: { value: unknown }) => formatValue(params.value, col.format ?? null)
            : (params: { value: unknown }) => {
                const v = params.value;
                return typeof v === "number" ? v.toLocaleString() : String(v ?? "");
              },
          sortable: true,
          resizable: true,
        });
      } else {
        rowCols.push({
          headerName: col.label || col.key,
          field: col.key,
          pinned: "left" as const,
          lockPinned: true,
          minWidth: 180,
          maxWidth: 300,
          sortable: true,
          resizable: true,
          cellStyle: { fontWeight: "500" },
        });
      }
    });

    columnDefs = [
      ...rowCols,
      ...Object.entries(groups).map(([measure, children]) => ({
        headerName: measure.replace("_", " ").toUpperCase(),
        children,
      })),
    ];
  } else {
    // Standard flat columns
    columnDefs = columns.map((col, idx) => ({
      headerName: col.label || col.key,
      field: col.key,
      pinned: idx === 0 ? "left" as const : undefined,
      lockPinned: idx === 0 ? true : undefined,
      width: idx === 0 ? 180 : undefined,
      minWidth: idx === 0 ? 150 : 80,
      suppressSizeToFit: true,
      valueFormatter: col.format
        ? (params: { value: unknown }) => formatValue(params.value, col.format ?? null)
        : undefined,
      type: typeof rows[0]?.[idx] === "number" ? "numericColumn" : undefined,
      sortable: true,
      resizable: true,
    }));
  }

  // Build row data (convert arrays to objects)
  const rowData = rows.map((row) => {
    const obj: Record<string, unknown> = {};
    columns.forEach((col, idx) => {
      obj[col.key] = row[idx];
    });
    return obj;
  });

  // Create the grid container
  const gridDiv = el.createDiv({ cls: "de-funk-ag-grid" });
  gridDiv.style.cssText = `height:${Math.min(maxH, rows.length * 32 + 48)}px;width:100%;`;
  gridDiv.classList.add("ag-theme-alpine");

  // Check if dark mode
  if (document.body.classList.contains("theme-dark")) {
    gridDiv.classList.remove("ag-theme-alpine");
    gridDiv.classList.add("ag-theme-alpine-dark");
  }

  // Grid options
  const gridOptions: GridOptions = {
    columnDefs,
    rowData,
    defaultColDef: {
      sortable: true,
      resizable: true,
      minWidth: 70,
    },
    animateRows: false,
    suppressCellFocus: false,
    enableCellTextSelection: true,
    ensureDomOrder: true,
    domLayout: "normal",
    // Horizontal scroll always visible — AG Grid handles this natively
    suppressHorizontalScroll: false,
    alwaysShowHorizontalScroll: true,
    alwaysShowVerticalScroll: false,
  };

  // For pivot tables, pin TOTAL rows to bottom and sort by last data column desc
  if (hasPivotCols) {
    gridOptions.pinnedBottomRowData = rowData.filter(r => {
      const firstKey = columns[0]?.key;
      return firstKey && r[firstKey] === "TOTAL";
    });
    gridOptions.rowData = rowData.filter(r => {
      const firstKey = columns[0]?.key;
      return !(firstKey && r[firstKey] === "TOTAL");
    });

    // Find the last non-null column to sort by
    const lastCol = columns.filter(c => c.key.includes("||")).pop();
    if (lastCol) {
      gridOptions.initialState = {
        sort: { sortModel: [{ colId: lastCol.key, sort: "desc" }] },
      };
    }
  }

  // Create the grid
  createGrid(gridDiv, gridOptions);

  // Truncation warning
  if (tableResponse.truncated) {
    const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
    warn.setText("Results were capped by the server row limit. Apply a filter to narrow the data.");
  }
}

/**
 * Render a pivot table using AG Grid with pinned row labels.
 */
export function renderAgGridPivot(
  block: DeFunkBlock,
  response: TableResponse,
  el: HTMLElement,
): void {
  // For GT HTML pivots, use regular AG Grid data table
  // The backend already computes the pivot — we just display it
  renderAgGrid(block, response, el);
}
