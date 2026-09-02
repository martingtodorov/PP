import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, Sparkles, RotateCcw } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";
import { LOCALES, LOCALE_META } from "../i18n/locales";
import { CHECKOUT_STRINGS, CHECKOUT_KEYS } from "../i18n/checkoutStrings";

export default function AdminUiStringsPage() {
  const [locale, setLocale] = useState("ro");
  const [overrides, setOverrides] = useState({});
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/ui-strings");
      setOverrides(data.strings || {});
    } catch (e) { toast.error(formatErr(e)); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setDraft({}); }, [locale]);

  const defaults = useMemo(() => CHECKOUT_STRINGS[locale] || CHECKOUT_STRINGS.en, [locale]);
  const saved = overrides[locale] || {};
  const valueOf = (key) => (key in draft ? draft[key] : (saved[key] ?? defaults[key] ?? ""));
  const changed = Object.keys(draft).length;

  const save = () => run("save", async () => {
    const payload = {};
    Object.entries(draft).forEach(([k, v]) => {
      payload[k] = v.trim() === (defaults[k] || "").trim() ? "" : v;   // same as default -> no override
    });
    await api.put("/admin/ui-strings", { locale, strings: payload });
    setDraft({});
    toast.success("Текстовете са запазени");
    load();
  });

  const translate = () => run("ai", async () => {
    const source = {};
    CHECKOUT_KEYS.forEach((k) => { source[k] = CHECKOUT_STRINGS.bg[k]; });
    const { data } = await api.post("/admin/ui-strings/translate", { locale, source });
    toast.success(`Преведени ${Object.keys(data.translated || {}).length} текста`);
    setDraft({});
    load();
  });

  const resetKey = (key) => run("save", async () => {
    await api.put("/admin/ui-strings", { locale, strings: { [key]: "" } });
    setDraft((d) => { const n = { ...d }; delete n[key]; return n; });
    load();
  });

  async function run(kind, fn) {
    setBusy(kind);
    try { await fn(); } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  }

  return (
    <AdminLayout title="Текстове на количката и чекаута">
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">
        Всеки текст има готов превод за всички езици. Тук можеш да го промениш за конкретен език — записаното
        тук има приоритет и се вижда веднага, без ново качване на сайта. Заместителите
        <code className="mx-1 text-xs bg-slate-100 px-1 rounded">{"{amount}"}</code>
        <code className="mr-1 text-xs bg-slate-100 px-1 rounded">{"{code}"}</code>
        <code className="mr-1 text-xs bg-slate-100 px-1 rounded">{"{city}"}</code>
        <code className="mr-1 text-xs bg-slate-100 px-1 rounded">{"{courier}"}</code>
        трябва да останат както са.
      </p>

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <select value={locale} onChange={(e) => setLocale(e.target.value)}
          className="border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="ui-locale-select">
          {LOCALES.map((loc) => (
            <option key={loc} value={loc}>{LOCALE_META[loc].label} ({loc})</option>
          ))}
        </select>
        <button type="button" onClick={save} disabled={!changed || Boolean(busy)}
          className="inline-flex items-center gap-2 rounded-full bg-coral-600 px-4 py-2 text-sm font-semibold text-white hover:bg-coral-700 disabled:opacity-50 transition-colors"
          data-testid="ui-save-btn">
          {busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Запази{changed ? ` (${changed})` : ""}
        </button>
        <button type="button" onClick={translate} disabled={locale === "bg" || Boolean(busy)}
          className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          data-testid="ui-translate-btn">
          {busy === "ai" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          AI превод от български
        </button>
        <span className="text-xs text-slate-500">
          {Object.keys(saved).length} ръчно редактирани текста за този език
        </span>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3 w-56">Ключ</th>
              <th className="text-left px-4 py-3">Български (източник)</th>
              <th className="text-left px-4 py-3">{LOCALE_META[locale].label}</th>
              <th className="px-4 py-3 w-12" />
            </tr>
          </thead>
          <tbody data-testid="ui-strings-table">
            {CHECKOUT_KEYS.map((key) => (
              <tr key={key} className="border-t border-slate-100 align-top">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{key}</td>
                <td className="px-4 py-3 text-slate-600">{CHECKOUT_STRINGS.bg[key]}</td>
                <td className="px-4 py-3">
                  <textarea value={valueOf(key)} rows={valueOf(key).length > 80 ? 3 : 1}
                    onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                    className={`w-full border rounded-md px-2 py-1.5 text-sm ${key in draft ? "border-coral-500 bg-coral-50/40" : "border-slate-300"}`}
                    data-testid={`ui-input-${key}`} />
                </td>
                <td className="px-4 py-3">
                  {saved[key] && (
                    <button type="button" onClick={() => resetKey(key)} title="Върни оригинала"
                      className="p-1.5 text-slate-400 hover:text-slate-800" data-testid={`ui-reset-${key}`}>
                      <RotateCcw className="h-4 w-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
