import { useEffect, useState } from "react";
import { Plus, Trash2, ExternalLink, RotateCcw, Check } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";
import { LOCALES, LOCALE_META } from "../i18n/locales";

const STATUSES = [
  { v: "pending", label: "Чака ротация", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  { v: "rotated", label: "Ротирана", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { v: "redirected", label: "Пренасочена", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  { v: "ignored", label: "Игнорирана", cls: "bg-slate-100 text-slate-600 border-slate-200" },
];

const EMPTY = { url: "", locale: "bg", reason: "", status: "pending", replacement_url: "", notes: "" };

export default function AdminDelistedLinksPage() {
  const [links, setLinks] = useState([]);
  const [draft, setDraft] = useState(EMPTY);
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/delisted-links").then(({ data }) => setLinks(data.links));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!draft.url.trim()) return;
    setBusy(true);
    try {
      await api.post("/admin/delisted-links", draft);
      setDraft(EMPTY);
      toast.success("Линкът е добавен");
      load();
    } catch (err) { toast.error(formatErr(err)); } finally { setBusy(false); }
  };

  const update = async (l, patch) => {
    try {
      await api.put(`/admin/delisted-links/${l.id}`, { ...l, ...patch });
      load();
    } catch (err) { toast.error(formatErr(err)); }
  };

  const remove = async (l) => {
    if (!window.confirm("Да изтрия ли този запис?")) return;
    try { await api.delete(`/admin/delisted-links/${l.id}`); load(); } catch (err) { toast.error(formatErr(err)); }
  };

  const visible = filter === "all" ? links : links.filter((l) => l.status === filter);
  const pendingCount = links.filter((l) => l.status === "pending").length;

  return (
    <AdminLayout title="Изтеглени линкове (ротация на съдържание)">
      <p className="text-sm text-slate-500 mb-6 max-w-2xl">
        Добавяйте тук всички делистнати / премахнати URL адреси, за да следите кои страници трябва да бъдат
        ротирани, презаписани или пренасочени. Записите с етикет „Чака ротация" са вашият списък със задачи.
      </p>

      <form onSubmit={add} className="bg-white border border-slate-200 rounded-xl p-5 grid gap-3 md:grid-cols-12 mb-6" data-testid="delisted-form">
        <input
          className="md:col-span-5 border border-slate-300 rounded-md px-3 py-2 text-sm font-mono"
          placeholder="https://purepeptide.bg/products/…"
          value={draft.url}
          onChange={(e) => setDraft({ ...draft, url: e.target.value })}
          data-testid="delisted-url-input"
        />
        <select
          className="md:col-span-2 border border-slate-300 rounded-md px-2 py-2 text-sm"
          value={draft.locale}
          onChange={(e) => setDraft({ ...draft, locale: e.target.value })}
          data-testid="delisted-locale-select"
        >
          {LOCALES.map((l) => <option key={l} value={l}>{LOCALE_META[l].label}</option>)}
        </select>
        <input
          className="md:col-span-4 border border-slate-300 rounded-md px-3 py-2 text-sm"
          placeholder="Причина (напр. премахнат продукт, дублирано съдържание)"
          value={draft.reason}
          onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
          data-testid="delisted-reason-input"
        />
        <button
          type="submit"
          disabled={busy}
          className="md:col-span-1 inline-flex items-center justify-center gap-1 bg-coral-600 hover:bg-coral-700 text-white rounded-md px-3 py-2 text-sm font-semibold disabled:opacity-60"
          data-testid="delisted-add-btn"
        >
          <Plus className="h-4 w-4" />
        </button>
      </form>

      <div className="flex flex-wrap gap-2 mb-4" data-testid="delisted-filters">
        {[{ v: "all", label: `Всички (${links.length})` }, ...STATUSES.map((s) => ({ v: s.v, label: s.label }))].map((f) => (
          <button
            key={f.v}
            onClick={() => setFilter(f.v)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
              filter === f.v ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200"
            }`}
            data-testid={`delisted-filter-${f.v}`}
          >
            {f.label}
          </button>
        ))}
        {pendingCount > 0 && (
          <span className="ml-auto text-xs text-amber-700 font-semibold self-center" data-testid="delisted-pending-count">
            {pendingCount} страници чакат ротация
          </span>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">URL</th>
              <th className="text-left px-4 py-3">Език</th>
              <th className="text-left px-4 py-3">Причина</th>
              <th className="text-left px-4 py-3">Заместващ URL</th>
              <th className="text-left px-4 py-3">Статус</th>
              <th className="text-right px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((l) => {
              const st = STATUSES.find((s) => s.v === l.status) || STATUSES[0];
              return (
                <tr key={l.id} className="border-t border-slate-100" data-testid={`delisted-row-${l.id}`}>
                  <td className="px-4 py-3 font-mono text-xs">
                    <a href={l.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-slate-800 hover:text-coral-600 break-all">
                      {l.url} <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                  </td>
                  <td className="px-4 py-3">{LOCALE_META[l.locale]?.label || l.locale}</td>
                  <td className="px-4 py-3 text-slate-600">{l.reason || "—"}</td>
                  <td className="px-4 py-3">
                    <input
                      defaultValue={l.replacement_url}
                      onBlur={(e) => e.target.value !== l.replacement_url && update(l, { replacement_url: e.target.value })}
                      placeholder="/collections/…"
                      className="border border-slate-200 rounded-md px-2 py-1 text-xs font-mono w-44"
                      data-testid={`delisted-replacement-${l.id}`}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={l.status}
                      onChange={(e) => update(l, { status: e.target.value })}
                      className={`border rounded-full px-2.5 py-1 text-xs font-semibold ${st.cls}`}
                      data-testid={`delisted-status-${l.id}`}
                    >
                      {STATUSES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {l.status !== "rotated" ? (
                      <button onClick={() => update(l, { status: "rotated" })} className="text-emerald-700 hover:underline mr-3 inline-flex items-center gap-1 text-xs" data-testid={`delisted-mark-rotated-${l.id}`}>
                        <Check className="h-3.5 w-3.5" /> Ротирана
                      </button>
                    ) : (
                      <button onClick={() => update(l, { status: "pending" })} className="text-slate-500 hover:underline mr-3 inline-flex items-center gap-1 text-xs">
                        <RotateCcw className="h-3.5 w-3.5" /> Върни
                      </button>
                    )}
                    <button onClick={() => remove(l)} className="text-slate-400 hover:text-red-600" data-testid={`delisted-delete-${l.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400">Няма записи</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
