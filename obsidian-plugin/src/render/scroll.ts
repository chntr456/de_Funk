/**
 * Shared scroll utilities for table/pivot exhibits.
 *
 * applyViewport: sets max-height. CSS handles overflow-x: scroll
 * (always visible) and overflow-y: auto (when content exceeds height).
 */

export function applyViewport(
  wrapper: HTMLElement,
  explicitMaxHeight?: number,
): void {
  const maxH = explicitMaxHeight ?? 500;
  wrapper.style.setProperty("max-height", maxH + "px", "important");
}
