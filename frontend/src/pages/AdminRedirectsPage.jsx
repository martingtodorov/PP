import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, Plus, Trash2 } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";

const EMPTY = { from_path: "", to_url: "", note: "" };

export default function AdminRedirectsPage() {
  const [rows, setRows] = useState([]);
  const [draft, setDraft] = useState(EMPTY);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/redirects");
      setRows(data.redirects || []);
    } catch (e) { toast.error(formatErr(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!draft.from_path.trim() || !draft.to_url.trim()) return;
    setBusy(true);
    try {
      await api.post("/admin/redirects", draft);
      toast.success("301 препратката е активна");
      setDraft(EMPTY);
      load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const update = async (r, patch) => {
    try {
      await api.put(`/admin/redirects/${r.id}`, { ...r, ...patch });
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const remove = async (r) => {
    if (!window.confirm(`Да махна ли препратката от ${r.from_path}?`)) return;
    try {
      await api.delete(`/admin/redirects/${r.id}`);
      toast.success("Махната");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  return (
    <AdminLayout title="301 препратки">
      <p className="text-sm text-slate-600 mb-6 max-w-3xl">
        Стар адрес → нов адрес, с истинска <span className="font-mono">301</span>. Отделно от
        „Изтеглени линкове“: там ротираните адреси остават мъртви с 404 и никога не се пренасочват.
      </p>

      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6" data-testid="redirect-form">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_auto] gap-3 items-start">
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">От (стар адрес)</label>
            <input value={draft.from_path} onChange={(e) => setDraft({ ...draft, from_path: e.target.value })}
              placeholder="/pages/staro-nesto или https://purepeptide.bg/pages/staro-nesto"
              className="w-full mt-1 border border-slate-300 rounded-md px-3 py-2 text-sm font-mono"
              data-testid="redirect-from" />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Към (нов адрес)</label>
            <input value={draft.to_url} onChange={(e) => setDraft({ ...draft, to_url: e.target.value })}
              placeholder="/collections/2all-the-peptides-1"
              className="w-full mt-1 border border-slate-300 rounded-md px-3 py-2 text-sm font-mono"
              data-testid="redirect-to" />
          </div>
          <button onClick={add} disabled={busy || !draft.from_path.trim() || !draft.to_url.trim()}
            className="mt-6 inline-flex items-center gap-2 px-5 py-2 rounded-full bg-coral-600 text-white text-sm font-semibold disabled:opacity-50"
            data-testid="redirect-add">
            <Plus className="h-4 w-4" /> Добави
          </button>
        </div>
        <input value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          placeholder="Бележка (защо) — само за теб"
          className="w-full mt-3 border border-slate-200 rounded-md px-3 py-2 text-sm"
          data-testid="redirect-note" />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm" data-testid="redirects-table">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">От</th>
              <th className="text-left px-4 py-3">Към</th>
              <th className="text-left px-4 py-3">Бележка</th>
              <th className="text-left px-4 py-3">Ползвана</th>
              <th className="text-left px-4 py-3">Активна</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Няма препратки.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} data-testid="redirect-row">
                <td className="px-4 py-3 font-mono text-xs text-slate-800">{r.from_path}</td>
                <td className="px-4 py-3">
                  <span className="flex items-center gap-2">
                    <ArrowRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <input defaultValue={r.to_url}
                      onBlur={(e) => e.target.value !== r.to_url && update(r, { to_url: e.target.value })}
                      className="border border-slate-200 rounded-md px-2 py-1 text-xs font-mono w-64"
                      data-testid={`redirect-to-${r.id}`} />
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{r.note || "—"}</td>
                <td className="px-4 py-3 text-slate-500 text-xs tabular-nums" data-testid={`redirect-hits-${r.id}`}>
                  {r.hits || 0}
                </td>
                <td className="px-4 py-3">
                  <input type="checkbox" checked={r.active !== false}
                    onChange={(e) => update(r, { active: e.target.checked })}
                    data-testid={`redirect-active-${r.id}`} />
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => remove(r)} className="text-slate-400 hover:text-red-600"
                    data-testid={`redirect-delete-${r.id}`}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
