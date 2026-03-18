/**
 * Shared scroll utilities for table/pivot exhibits.
 *
 * applyViewport: turns a wrapper into a bounded scroll viewport with
 * both horizontal and vertical scrollbars always accessible.
 */

/**
 * Apply inline viewport styles with !important so nothing in Obsidian
 * or Great Tables CSS can override them. Creates a fixed-height
 * scrollable window with both scrollbars at the viewport edges.
 */
export function applyViewport(
  wrapper: HTMLElement,
  explicitMaxHeight?: number,
): void {
  const maxH = explicitMaxHeight ?? 500;
  wrapper.style.setProperty("overflow", "auto", "important");
  wrapper.style.setProperty("max-height", `${maxH}px`, "important");
}
