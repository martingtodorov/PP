/** A ranked list with share bars — used for countries, cities, pages and sources. */
export const StatList = ({ title, rows = [], label, count = (r) => r.visitors, note = "",
  suffix, testid, empty = "Няма данни за този период." }) => {
  const max = Math.max(1, ...rows.map(count));
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`stat-${testid}`}>
      <p className="text-xs uppercase tracking-wide text-slate-500 mb-3">{title}</p>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-400">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((r, i) => (
            <li key={`${testid}-${i}`} className="text-sm" data-testid={`${testid}-row`}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-slate-800">{label(r)}</span>
                <span className="tabular-nums text-slate-500 shrink-0">
                  {count(r)}
                  {suffix ? <span className="text-slate-400"> {suffix(r)}</span> : null}
                </span>
              </div>
              <div className="h-1.5 mt-1 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full rounded-full bg-sky-500 transition-[width] duration-500"
                  style={{ width: `${Math.round((count(r) / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="text-[11px] text-slate-400 mt-3">{note}</p> : null}
    </div>
  );
};

export default StatList;
