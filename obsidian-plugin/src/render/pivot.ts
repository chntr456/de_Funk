/**
 * Render table.pivot exhibits — handles both flat GT HTML and expandable
 * hierarchical pivots with server-computed subtotals.
 */
import type { DeFunkBlock, TableResponse, GreatTablesResponse, ExpandableData } from "../contract";
import { renderTabular } from "./tabular";
import { formatValue } from "./format";
import { applyViewport } from "./scroll";

export function renderPivot(
  block: DeFunkBlock,
  response: TableResponse | GreatTablesResponse,
  el: HTMLElement,
): void {
  const gtResponse = response as GreatTablesResponse;

  // If expandable data is present, wire up expand/collapse after GT render
  if (gtResponse.expandable) {
    renderExpandablePivot(block, gtResponse, el);
    return;
  }

  // Standard GT or plain table render
  renderTabular(block, response, el);
}

/**
 * Render a hierarchical pivot where subtotals are in the GT HTML and
 * detail rows are in the expandable JSON. Clicking a subtotal row
 * expands its children inline.
 */
function renderExpandablePivot(
  block: DeFunkBlock,
  response: GreatTablesResponse,
  el: HTMLElement,
): void {
  const formatting = block.formatting ?? {};
  const title = formatting.title;
  const expandable = response.expandable!;

  if (title) {
    el.createEl("h4", { text: title, cls: "de-funk-table-title" });
  }

  // Inject the GT HTML (subtotals + grand total only)
  const wrapper = el.createDiv({ cls: "de-funk-great-tables de-funk-expandable" });
  wrapper.innerHTML = response.html;
  applyViewport(wrapper, formatting.max_height);

  // Info bar
  const detailCount = Object.values(expandable.children).reduce(
    (sum, rows) => sum + rows.length, 0,
  );
  const info = el.createDiv({ cls: "de-funk-expand-info" });
  info.setText(
    `Showing ${expandable.total_rows - detailCount} summary rows of ${expandable.total_rows} total. ` +
    `Click a row to expand its ${detailCount} detail rows.`,
  );

  // Find all <tbody> rows in the GT table and wire up expand/collapse
  const tbody = wrapper.querySelector("tbody");
  if (!tbody) return;

  const rows = tbody.querySelectorAll("tr");
  rows.forEach((tr) => {
    // The first cell text is the parent key for children lookup
    const firstCell = tr.querySelector("td");
    if (!firstCell) return;
    const parentKey = firstCell.textContent?.trim() ?? "";

    // Only make expandable if this parent has children
    if (!expandable.children[parentKey]) return;

    tr.classList.add("de-funk-expandable-row");
    tr.style.cursor = "pointer";

    // Add expand indicator
    const indicator = document.createElement("span");
    indicator.classList.add("de-funk-expand-indicator");
    indicator.textContent = "\u25B6 ";  // ▶
    firstCell.insertBefore(indicator, firstCell.firstChild);

    let expanded = false;
    let childRows: HTMLTableRowElement[] = [];

    tr.addEventListener("click", () => {
      if (expanded) {
        // Collapse — remove child rows
        childRows.forEach((cr) => cr.remove());
        childRows = [];
        indicator.textContent = "\u25B6 ";
        expanded = false;
      } else {
        // Expand — insert child rows after this row
        const children = expandable.children[parentKey];
        const cols = expandable.columns;
        let insertAfter: Element = tr;

        for (const childData of children) {
          const childTr = document.createElement("tr");
          childTr.classList.add("de-funk-child-row");

          for (let i = 0; i < cols.length; i++) {
            const td = document.createElement("td");
            td.textContent = formatValue(childData[i], cols[i].format ?? null);
            childTr.appendChild(td);
          }

          insertAfter.after(childTr);
          insertAfter = childTr;
          childRows.push(childTr);
        }

        indicator.textContent = "\u25BC ";  // ▼
        expanded = true;
      }
    });
  });

  // Add styles for expand/collapse
  const styleEl = document.createElement("style");
  styleEl.textContent = `
    .de-funk-expandable-row:hover {
      background-color: rgba(0, 0, 0, 0.05) !important;
    }
    .de-funk-expand-indicator {
      font-size: 0.7em;
      margin-right: 4px;
      display: inline-block;
      transition: transform 0.15s;
    }
    .de-funk-child-row {
      background-color: rgba(0, 0, 0, 0.02);
    }
    .de-funk-child-row td:first-child {
      padding-left: 24px !important;
    }
    .de-funk-expand-info {
      font-size: 0.8em;
      color: var(--text-muted);
      margin-top: 4px;
      margin-bottom: 8px;
    }
  `;
  el.prepend(styleEl);
}
