import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "../lib/cn";

export type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  /** Value used for sorting; omit to make the column unsortable. */
  sortValue?: (row: T) => string | number;
  className?: string;
};

type Props<T> = {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  caption?: string;
  empty?: ReactNode;
  className?: string;
  rowClassName?: (row: T) => string | undefined;
};

export function DataTable<T>({ columns, rows, rowKey, onRowClick, caption, empty, className, rowClassName }: Props<T>) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const get = col.sortValue;
    return [...rows].sort((a, b) => {
      const [x, y] = [get(a), get(b)];
      const r = x < y ? -1 : x > y ? 1 : 0;
      return sort.dir === "asc" ? r : -r;
    });
  }, [rows, columns, sort]);

  const toggle = (key: string) =>
    setSort((s) => (s?.key !== key ? { key, dir: "asc" } : s.dir === "asc" ? { key, dir: "desc" } : null));

  return (
    <div className={cn("overflow-x-auto rounded-2xl", className)}>
      <table className="w-full border-collapse text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-mist">
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={cn("px-4 py-3 font-semibold", c.className)}
                  aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                >
                  {c.sortValue ? (
                    <button
                      type="button"
                      onClick={() => toggle(c.key)}
                      className="inline-flex items-center gap-1 uppercase hover:text-cream"
                    >
                      {c.header}
                      {active ? (
                        sort!.dir === "asc" ? <ArrowUp className="h-3.5 w-3.5" aria-hidden /> : <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" aria-hidden />
                      )}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-mist">
                {empty ?? "Nothing to show yet."}
              </td>
            </tr>
          ) : (
            sorted.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                className={cn(
                  "border-b border-white/5 transition last:border-0",
                  onRowClick && "cursor-pointer hover:bg-white/[0.06] focus-visible:bg-white/[0.08]",
                  rowClassName?.(row),
                )}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn("px-4 py-3 align-middle text-cream", c.className)}>
                    {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
