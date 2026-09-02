import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Truck, CheckCircle2, XCircle } from "lucide-react";
import { api, formatErr } from "../../lib/api";

const Field = ({ label, children }) => (
  <label className="block text-sm">
    <span className="text-xs uppercase tracking-wide text-slate-500 font-bold">{label}</span>
    {children}
  </label>
);
const input = "mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono focus:border-coral-500 outline-none";

export const NextLevelCard = () => {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState("");
  const [test, setTest] = useState(null);

  const load = () => api.get("/admin/integrations/nextlevel").then(({ data }) => { setCfg(data); setForm({}); }).catch((e) => toast.error(formatErr(e)));
  useEffect(() => { load(); }, []);

  const save = async (patch = {}) => {
    setBusy("save");
    try {
      const { data } = await api.put("/admin/integrations/nextlevel", { ...form, ...patch });
      setCfg(data); setForm({}); toast.success("Записано");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };
  const runTest = async () => {
    setBusy("test");
    try {
      const { data } = await api.post("/admin/integrations/nextlevel/test");
      setTest(data);
      data.ok ? toast.success(`NextLevel отговаря · подател „${data.sender_seen}“`) : toast.error(data.error);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  if (!cfg) return null;
  const v = (k) => (form[k] !== undefined ? form[k] : cfg[k] ?? "");
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "number" ? Number(e.target.value) : e.target.value }));

  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5 mb-8" data-testid="nextlevel-card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-display font-bold text-slate-900 flex items-center gap-2"><Truck className="h-5 w-5 text-coral-600" /> NextLevel Delivery — товарителници</h2>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!cfg.enabled} onChange={(e) => save({ enabled: e.target.checked })} className="h-4 w-4 accent-coral-600" data-testid="nextlevel-enabled" /> Включено
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!cfg.auto_create} onChange={(e) => save({ auto_create: e.target.checked })} className="h-4 w-4 accent-coral-600" data-testid="nextlevel-auto" /> Автоматично при нова поръчка
          </label>
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-4 max-w-3xl">
        Всяка поръчка става товарителница в NextLevel (Econt, Speedy, BoxNow, Sameday, FAN, GLS, ACS…): офисът от чекаута
        се подава директно, адресите изискват пощенски код, наложен платеж се събира във валутата на държавата.
      </p>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <Field label="app-id"><input value={v("app_id")} onChange={set("app_id")} className={input} data-testid="nextlevel-app-id" /></Field>
        <Field label="app-secret"><input value={v("app_secret")} onChange={set("app_secret")} className={input} data-testid="nextlevel-app-secret" /></Field>
        <Field label="Подател (sender id)"><input type="number" value={v("sender_id")} onChange={set("sender_id")} className={input} data-testid="nextlevel-sender" /></Field>
        <Field label="Тегло по подразбиране (kg)"><input type="number" step="0.1" value={v("default_weight")} onChange={set("default_weight")} className={input} data-testid="nextlevel-weight" /></Field>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => save()} disabled={!!busy || !Object.keys(form).length} className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50" data-testid="nextlevel-save">
          {busy === "save" ? "Записване…" : "Запази"}
        </button>
        <button onClick={runTest} disabled={!!busy || !cfg.has_keys} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg disabled:opacity-50" data-testid="nextlevel-test">
          {busy === "test" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Тествай връзката
        </button>
      </div>
      {test && (
        <div className="mt-4 text-sm" data-testid="nextlevel-test-result">
          {test.ok ? (
            <div className="text-slate-700 space-y-1">
              <p className="flex items-center gap-2 text-emerald-700 font-semibold"><CheckCircle2 className="h-4 w-4" /> Свързано · {test.countries} държави · Econt до София от {test.sample_price_bg} € · подател „{test.sender_seen}“</p>
              <ul className="font-mono text-xs text-slate-500">
                {test.recent?.map((r) => <li key={r.awb}>{r.awb} · {r.courier} · {r.status} · поръчка {r.ref}</li>)}
              </ul>
            </div>
          ) : (
            <p className="flex items-center gap-2 text-red-700"><XCircle className="h-4 w-4" /> {test.error}</p>
          )}
        </div>
      )}
    </section>
  );
};
