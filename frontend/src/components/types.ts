// Type definitions for the ExcelTable component.
// Re-exported from `ExcelTable.tsx`; this file documents the public API.

import type { ReactNode } from "react";

/** A cell holds a plain value — strings, numbers, or empty. No formulas. */
export type CellValue = string | number | null;

/** Coordinates inside the table grid. */
export interface CellPosition {
  row: number;
  col: number;
}

/** Definition of a single column. */
export interface ColumnDef<T> {
  /** Property key in the row object, or a virtual column id. */
  key: keyof T & string | string;
  /** Display text in the header. May be a ReactNode for icons / sort controls. */
  header: ReactNode;
  /** Fixed or flexible width: number (px) or string (e.g. "20%", "minmax(80px, 1fr)"). */
  width?: number | string;
  /** Whether cells in this column are editable. Default: true. */
  editable?: boolean;
  /** Hint for default editor and copy/paste coercion. */
  type?: "text" | "number";
  /** Text alignment for cells in this column. */
  align?: "left" | "center" | "right";
  /** Optional custom cell renderer — see `references/customization.md`. */
  render?: CellRenderer<T>;
}

/** Props passed to a custom cell renderer. */
export interface CellRenderProps<T> {
  /** Current cell value. */
  value: CellValue;
  /** The full row object. */
  row: T;
  /** Row index in the data array. */
  rowIndex: number;
  /** Column definition for this cell. */
  column: ColumnDef<T>;
  /** True while the cell is being edited. */
  isEditing: boolean;
  /** True while the cell is part of the active selection. */
  isSelected: boolean;
  /** True while the cell is the active (focus) cell of the selection. */
  isActive: boolean;
  /** True when the cell is the anchor of a multi-cell range. */
  isRangeAnchor: boolean;
  /** Persist a new value. Called by the editor on every keystroke. */
  onChange: (value: CellValue) => void;
  /** Commit the edit and exit edit mode. */
  onCommit: () => void;
  /** Cancel the edit and revert to the original value. */
  onCancel: () => void;
  /** Reference to attach to the editor element so the table can focus it. */
  editorRef: (el: HTMLElement | null) => void;
}

export type CellRenderer<T> = (props: CellRenderProps<T>) => ReactNode;
