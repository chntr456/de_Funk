/**
 * Render table.data and table.great exhibits.
 */
import type { DeFunkBlock, TableResponse, GreatTablesResponse } from "../contract";
import { formatValue } from "./format";
import { applyViewport } from "./scroll";

export function renderTabular(
  block: DeFunkBlock,
  response: TableResponse | GreatTablesResponse,
  el: HTMLElement,
): void {
  const formatting = block.formatting ?? {};
  const title = formatting.title;

  if (title) {
    el.createEl("h4", { text: title, cls: "de-funk-table-title" });
  }

  // Great Tables — inject raw HTML
  if ("html" in response) {
    const wrapper = el.createDiv({ cls: "de-funk-great-tables" });
    wrapper.innerHTML = (response as GreatTablesResponse).html;
    applyViewport(wrapper, formatting.max_height);
    if ("truncated" in response && response.truncated) {
      const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
      warn.setText("Results were capped by the server row limit. Apply a filter to narrow the data.");
    }
    return;
  }

  const tableResponse = response as TableResponse;
  const { columns, rows } = tableResponse;

  const wrapper = el.createDiv({ cls: "de-funk-table-wrapper" });
  applyViewport(wrapper, formatting.max_height);
  const table = wrapper.createEl("table", { cls: "de-funk-table" });

  // Header
  const thead = table.createEl("thead");
  const headerRow = thead.createEl("tr");
  for (const col of columns) {
    headerRow.createEl("th", { text: col.label });
  }

  // Body
  const tbody = table.createEl("tbody");
  const pageSize = formatting.page_size ?? 100;
  const visibleRows = rows.slice(0, pageSize);

  for (const row of visibleRows) {
    const tr = tbody.createEl("tr");
    for (let i = 0; i < columns.length; i++) {
      tr.createEl("td", { text: formatValue(row[i], columns[i].format) });
    }
  }

  // Pagination info
  if (rows.length > pageSize) {
    el.createEl("p", {
      text: `Showing ${pageSize} of ${rows.length} rows`,
      cls: "de-funk-table-pagination",
    });
  }

  // Download button
  if (formatting.download) {
    const btn = el.createEl("button", { text: "Download CSV", cls: "de-funk-download" });
    btn.addEventListener("click", () => downloadCsv(columns, rows));
  }

  // Truncation warning at the bottom
  if (tableResponse.truncated) {
    const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
    warn.setText("Results were capped by the server row limit. Apply a filter to narrow the data.");
  }
}

function downloadCsv(columns: TableResponse["columns"], rows: TableResponse["rows"]): void {
  const header = columns.map((c) => c.label).join(",");
  const csvRows = rows.map((row) =>
    row.map((v) => (typeof v === "string" && v.includes(",") ? `"${v}"` : v)).join(",")
  );
  const csv = [header, ...csvRows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "de_funk_export.csv";
  a.click();
  URL.revokeObjectURL(url);
}
