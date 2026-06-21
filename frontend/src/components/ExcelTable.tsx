"use client";

/**
 * ExcelTable — a drop-in table component with Excel-like behavior.
 *
 * Features:
 *   - Click a cell to select, shift-click / shift-arrows for a range.
 *   - Double-click, F2, or just start typing to enter edit mode.
 *   - Arrow keys, Tab, Enter move the active cell.
 *   - Ctrl/Cmd+C, Ctrl/Cmd+X, Ctrl/Cmd+V work both internally and with
 *     Excel / Google Sheets / Numbers via the TSV clipboard format.
 *   - Delete / Backspace clears the active cell (or selected range).
 *   - Escape cancels an edit. Enter / Tab / clicking away commits.
 *   - Custom `render` per column lets the cell look however you want
 *     (badges, dropdowns, color swatches) while keeping Excel semantics.
 *
 * Values only — no formulas. Cells hold strings, numbers, or null.
 *
 * Styling: ships minimal structural CSS in `excel-table.css`. Override
 * classes (`.excel-table`, `.excel-cell--selected`, etc.) to restyle.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import type { CellPosition, CellRenderProps, CellValue, ColumnDef } from "./types";

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

const isMac =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");

const modKey = (e: KeyboardEvent | ReactKeyboardEvent) =>
  isMac ? e.metaKey : e.ctrlKey;

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function positionsInRange(a: CellPosition, b: CellPosition): CellPosition[] {
  const r0 = Math.min(a.row, b.row);
  const r1 = Math.max(a.row, b.row);
  const c0 = Math.min(a.col, b.col);
  const c1 = Math.max(a.col, b.col);
  const out: CellPosition[] = [];
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      out.push({ row: r, col: c });
    }
  }
  return out;
}

function rangeSize(a: CellPosition, b: CellPosition) {
  return {
    rows: Math.abs(a.row - b.row) + 1,
    cols: Math.abs(a.col - b.col) + 1,
  };
}

/** Parse tab/newline-delimited clipboard text into a 2D grid of strings. */
function parseTsv(text: string): string[][] {
  return text
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .filter((line, idx, arr) => line.length > 0 || idx < arr.length - 1)
    .map((line) => line.split("\t"));
}

/** Encode a 2D grid of values as TSV suitable for the clipboard. */
function encodeTsv(grid: CellValue[][]): string {
  return grid
    .map((row) =>
      row
        .map((v) => (v === null || v === undefined ? "" : String(v)))
        .join("\t")
    )
    .join("\n");
}

function coerce(value: string, type: ColumnDef<unknown>["type"]): CellValue {
  if (value === "") return null;
  if (type === "number") {
    const n = Number(value);
    return Number.isFinite(n) ? n : value;
  }
  return value;
}

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

export interface ExcelTableProps<T> {
  /** Row data. The component does not own this array — supply an updated
   *  copy via `onChange` / `onRowsChange` to mutate. */
  rows: T[];
  /** Column definitions in display order. */
  columns: ColumnDef<T>[];
  /** Stable row id. Defaults to row index (which breaks under paste). */
  getRowId?: (row: T, index: number) => string | number;
  /** Called for any single-cell value change (typing, paste into one cell). */
  onChange?: (rowIndex: number, key: string, value: CellValue) => void;
  /** Called when paste inserts multiple rows / columns. The table does not
   *  mutate the input array; it expects a new array back. */
  onRowsChange?: (next: T[]) => void;
  /** Disable all editing. Selection and copy still work. */
  readOnly?: boolean;
  /** Keep the header row visible while scrolling. Default: true. */
  stickyHeader?: boolean;
  /** Optional className for the root element. */
  className?: string;
  /** Empty-state placeholder when `rows` is empty. */
  emptyMessage?: React.ReactNode;
}

export function ExcelTable<T extends Record<string, unknown>>(
  props: ExcelTableProps<T>
) {
  const {
    rows,
    columns,
    getRowId,
    onChange,
    onRowsChange,
    readOnly = false,
    stickyHeader = true,
    className,
    emptyMessage = "Нет данных",
  } = props;
  // getRowId is part of the public API but not used inside the component
  // (row identity is positional for paste/copy semantics).
  void getRowId;

  const colCount = columns.length;
  const rowCount = rows.length;

  /* ----- selection ------------------------------------------------------- */

  const [anchor, setAnchor] = useState<CellPosition>({ row: 0, col: 0 });
  const [focus, setFocus] = useState<CellPosition>({ row: 0, col: 0 });
  const [editing, setEditing] = useState<CellPosition | null>(null);
  const [editBuffer, setEditBuffer] = useState<CellValue | "">(null);

  const isCellSelected = useCallback(
    (p: CellPosition) => {
      const sel = positionsInRange(anchor, focus);
      return sel.some((s) => s.row === p.row && s.col === p.col);
    },
    [anchor, focus]
  );
  const isActive = (p: CellPosition) =>
    p.row === focus.row && p.col === focus.col;
  const isRangeAnchor = (p: CellPosition) =>
    p.row === anchor.row && p.col === anchor.col;

  const moveTo = useCallback(
    (next: CellPosition, extend = false) => {
      const clamped: CellPosition = {
        row: clamp(next.row, 0, Math.max(0, rowCount - 1)),
        col: clamp(next.col, 0, colCount - 1),
      };
      if (extend) {
        setFocus(clamped);
      } else {
        setAnchor(clamped);
        setFocus(clamped);
      }
    },
    [rowCount, colCount]
  );

  /* ----- cell value lookup ---------------------------------------------- */

  const getCellValue = (r: number, c: number): CellValue => {
    const row = rows[r];
    if (!row) return null;
    const col = columns[c];
    const v = (row as Record<string, unknown>)[col.key as string];
    if (v === undefined || v === null) return null;
    if (typeof v === "string" || typeof v === "number") return v;
    return String(v);
  };

  /* ----- mutations ------------------------------------------------------- */

  const setCell = useCallback(
    (r: number, c: number, value: CellValue) => {
      const col = columns[c];
      if (!col) return;
      if (onChange) {
        onChange(r, col.key as string, value);
      } else if (onRowsChange) {
        const next = rows.map((row, i) =>
          i === r
            ? ({ ...row, [col.key as string]: value } as T)
            : row
        );
        onRowsChange(next);
      }
    },
    [columns, onChange, onRowsChange, rows]
  );

  /** Apply a 2D grid of values starting at (r0, c0), growing the table if
   *  the paste extends past the bottom-right. */
  const pasteGrid = useCallback(
    (r0: number, c0: number, grid: string[][], type: ColumnDef<unknown>["type"]) => {
      const needRows = r0 + grid.length;
      // needCols would be used if we truncated the paste to in-table columns;
      // we currently let it run to whatever the grid supplies.
      void (c0 + (grid[0]?.length ?? 0));
      let next: T[] = rows.slice();
      while (next.length < needRows) {
        next = [...next, {} as T];
      }
      for (let r = 0; r < grid.length; r++) {
        for (let c = 0; c < grid[r].length; c++) {
          const col = columns[c0 + c];
          if (!col || col.editable === false) continue;
          const rowIdx = r0 + r;
          const value = coerce(grid[r][c], col.type ?? type);
          next[rowIdx] = {
            ...next[rowIdx],
            [col.key as string]: value,
          } as T;
        }
      }
      onRowsChange?.(next);
    },
    [rows, columns, onRowsChange]
  );

  /* ----- edit mode ------------------------------------------------------- */

  const startEdit = useCallback(
    (p: CellPosition, initial?: CellValue) => {
      if (readOnly) return;
      const col = columns[p.col];
      if (!col || col.editable === false) return;
      setEditing(p);
      setEditBuffer(initial === undefined ? getCellValue(p.row, p.col) : initial);
    },
    [columns, readOnly]
  );

  const commitEdit = useCallback(
    (advance?: CellPosition) => {
      if (!editing) return;
      setCell(editing.row, editing.col, editBuffer === "" ? null : editBuffer);
      setEditing(null);
      setEditBuffer(null);
      if (advance) moveTo(advance);
    },
    [editing, editBuffer, setCell, moveTo]
  );

  const cancelEdit = useCallback(() => {
    setEditing(null);
    setEditBuffer(null);
  }, []);

  /* ----- mouse handlers -------------------------------------------------- */

  const onCellMouseDown = (e: ReactMouseEvent, p: CellPosition) => {
    if (editing && !isActive(p)) {
      commitEdit();
    }
    if (e.shiftKey) {
      setFocus(p);
    } else {
      moveTo(p, false);
    }
    if (e.detail === 2) {
      // double click
      startEdit(p);
    }
  };

  /* ----- keyboard handlers ---------------------------------------------- */

  const onKeyDown = (e: ReactKeyboardEvent) => {
    if (editing) {
      if (e.key === "Enter") {
        e.preventDefault();
        commitEdit({ row: focus.row + (e.shiftKey ? -1 : 1), col: focus.col });
      } else if (e.key === "Tab") {
        e.preventDefault();
        commitEdit({ row: focus.row, col: focus.col + (e.shiftKey ? -1 : 1) });
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelEdit();
      }
      return;
    }

    const extend = e.shiftKey;

    switch (e.key) {
      case "ArrowUp":
        e.preventDefault();
        moveTo({ row: focus.row - 1, col: focus.col }, extend);
        break;
      case "ArrowDown":
        e.preventDefault();
        moveTo({ row: focus.row + 1, col: focus.col }, extend);
        break;
      case "ArrowLeft":
        e.preventDefault();
        moveTo({ row: focus.row, col: focus.col - 1 }, extend);
        break;
      case "ArrowRight":
        e.preventDefault();
        moveTo({ row: focus.row, col: focus.col + 1 }, extend);
        break;
      case "Tab":
        e.preventDefault();
        moveTo({ row: focus.row, col: focus.col + (e.shiftKey ? -1 : 1) });
        break;
      case "Enter":
        e.preventDefault();
        if (extend) {
          moveTo({ row: focus.row - 1, col: focus.col });
        } else {
          moveTo({ row: focus.row + 1, col: focus.col });
        }
        break;
      case "Home":
        e.preventDefault();
        moveTo({ row: focus.row, col: 0 }, extend);
        break;
      case "End":
        e.preventDefault();
        moveTo({ row: focus.row, col: colCount - 1 }, extend);
        break;
      case "F2":
        e.preventDefault();
        startEdit(focus);
        break;
      case "Delete":
      case "Backspace":
        if (readOnly) return;
        e.preventDefault();
        positionsInRange(anchor, focus).forEach((p) => {
          const col = columns[p.col];
          if (col && col.editable !== false) setCell(p.row, p.col, null);
        });
        break;
      default:
        if (modKey(e) && (e.key === "c" || e.key === "C")) {
          e.preventDefault();
          copySelection();
        } else if (modKey(e) && (e.key === "x" || e.key === "X")) {
          if (readOnly) return;
          e.preventDefault();
          copySelection();
          positionsInRange(anchor, focus).forEach((p) => {
            const col = columns[p.col];
            if (col && col.editable !== false) setCell(p.row, p.col, null);
          });
        } else if (modKey(e) && (e.key === "v" || e.key === "V")) {
          // paste handled in onPaste
        } else if (modKey(e) && (e.key === "a" || e.key === "A")) {
          e.preventDefault();
          setAnchor({ row: 0, col: 0 });
          setFocus({ row: rowCount - 1, col: colCount - 1 });
        } else if (
          e.key.length === 1 &&
          !e.ctrlKey &&
          !e.metaKey &&
          !e.altKey
        ) {
          // printable char starts edit mode, replacing the cell value
          if (readOnly) return;
          startEdit(focus, e.key);
        }
        break;
    }
  };

  /* ----- clipboard ------------------------------------------------------- */

  const copySelection = useCallback(() => {
    const cells = positionsInRange(anchor, focus);
    if (cells.length === 0) return;
    const { rows: rh, cols: cw } = rangeSize(anchor, focus);
    const grid: CellValue[][] = Array.from({ length: rh }, () =>
      Array.from({ length: cw }, () => null)
    );
    cells.forEach((p) => {
      grid[p.row - anchor.row][p.col - anchor.col] = getCellValue(p.row, p.col);
    });
    const tsv = encodeTsv(grid);
    void navigator.clipboard?.writeText(tsv);
  }, [anchor, focus, rows, columns]); // eslint-disable-line react-hooks/exhaustive-deps

  const onPaste = useCallback(
    (e: ClipboardEvent) => {
      if (readOnly) return;
      const text = e.clipboardData.getData("text/plain");
      if (!text) return;
      e.preventDefault();
      const grid = parseTsv(text);
      if (grid.length === 0) return;
      pasteGrid(focus.row, focus.col, grid, undefined);
    },
    [focus, pasteGrid, readOnly]
  );

  /* ----- auto-focus the active cell on mount + key changes -------------- */

  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = containerRef.current?.querySelector<HTMLElement>(
      `[data-row="${focus.row}"][data-col="${focus.col}"]`
    );
    if (el && document.activeElement !== el && !editing) {
      el.focus({ preventScroll: true });
    }
  }, [focus, editing]);

  /* ----- render ---------------------------------------------------------- */

  const gridTemplate = useMemo(
    () => columns.map((c) => c.width ?? "minmax(80px, 1fr)").join(" "),
    [columns]
  );

  if (rowCount === 0) {
    return (
      <div className={`excel-table excel-table--empty ${className ?? ""}`}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`excel-table ${className ?? ""}`}
      role="grid"
      tabIndex={-1}
      onKeyDown={onKeyDown}
      onPaste={onPaste}
    >
      <div
        className={`excel-table__grid ${stickyHeader ? "excel-table__grid--sticky" : ""}`}
        style={{ gridTemplateColumns: gridTemplate }}
      >
        {/* Header */}
        {columns.map((col, c) => (
          <div
            key={String(col.key)}
            className="excel-table__header"
            role="columnheader"
            data-col={c}
            style={{ textAlign: col.align ?? "left" }}
          >
            {col.header}
          </div>
        ))}

        {/* Body */}
        {rows.map((row, r) =>
          columns.map((col, c) => {
            const value = getCellValue(r, c);
            const isSel = isCellSelected({ row: r, col: c });
            const isAct = isActive({ row: r, col: c });
            const isAnch = isRangeAnchor({ row: r, col: c });
            const isEd = editing?.row === r && editing?.col === c;

            const classes = [
              "excel-table__cell",
              isSel && "excel-table__cell--selected",
              isAct && "excel-table__cell--active",
              isAnch && !isAct && "excel-table__cell--anchor",
              isEd && "excel-table__cell--editing",
              col.align && `excel-table__cell--align-${col.align}`,
            ]
              .filter(Boolean)
              .join(" ");

            let editorRef: (el: HTMLElement | null) => void = () => {};
            const wrap = (child: React.ReactNode) => (
              <div
                key={`${r}-${c}`}
                className={classes}
                role="gridcell"
                tabIndex={-1}
                data-row={r}
                data-col={c}
                onMouseDown={(e) => onCellMouseDown(e, { row: r, col: c })}
                onDoubleClick={() => startEdit({ row: r, col: c })}
                style={{ textAlign: col.align ?? "left" }}
              >
                {child}
              </div>
            );

            if (col.render) {
              const renderProps: CellRenderProps<T> = {
                value,
                row,
                rowIndex: r,
                column: col,
                isEditing: isEd,
                isSelected: isSel,
                isActive: isAct,
                isRangeAnchor: isAnch,
                onChange: (v) => {
                  if (!isEd) startEdit({ row: r, col: c }, v);
                  setEditBuffer(v);
                },
                onCommit: () => commitEdit(),
                onCancel: cancelEdit,
                editorRef,
              };
              return wrap(col.render(renderProps));
            }

            if (isEd) {
              return wrap(
                <DefaultEditor
                  type={col.type}
                  initial={editBuffer === null ? "" : String(editBuffer)}
                  onChange={(v) => setEditBuffer(v)}
                  onCommit={commitEdit}
                  onCancel={cancelEdit}
                />
              );
            }

            return wrap(<span className="excel-table__value">{value ?? ""}</span>);
          })
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Default editor — a plain <input> used when the column has no `render`    */
/* -------------------------------------------------------------------------- */

function DefaultEditor({
  type,
  initial,
  onChange,
  onCommit,
  onCancel,
}: {
  type: ColumnDef<unknown>["type"];
  initial: string;
  onChange: (v: CellValue) => void;
  onCommit: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    el.select();
  }, []);
  return (
    <input
      ref={ref}
      className="excel-table__editor"
      type={type === "number" ? "number" : "text"}
      defaultValue={initial}
      onChange={(e) =>
        onChange(
          type === "number"
            ? e.target.value === ""
              ? null
              : Number(e.target.value)
            : e.target.value
        )
      }
      onBlur={onCommit}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
        // Enter / Tab are handled by the table-level keydown
      }}
    />
  );
}
