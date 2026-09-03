import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, PackageCheck, CheckCircle2, XCircle, Copy, KeyRound, RefreshCw } from "lucide-react";
import { api, formatErr } from "../../lib/api";

const Field = ({ label, children }) => (
  <label className="block text-sm">
    <span className="text-xs uppercase tracking-wide text-slate-500 font-bold">{label}</span>
    {children}
  </label>
);
const input = "mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono focus:border-coral-500 outline-none";

export const FulfillmentCard = () => {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState("");
  const [test, setTest] = useState(null);
  const [plainSecret, setPlainSecret] = useState("");
  const [log, setLog] = useState(null);
  const storeUrl = window.location.origin;
  const copyText = (value) => { navigator.clipboard?.writeText(value); toast.success("Копирано"); };

  const load = () => api.get("/admin/integrations/nextlevel-fulfillment").then(({ data }) => { setCfg(data); setForm({}); }).catch((e) => toast.error(formatErr(e)));
  useEffect(() => { load(); }, []);

  const genKeys = async () => {
    if (cfg.has_wc && !window.confirm("Новите ключове ще направят старите невалидни — ще трябва да ги смените и в NextLevel. Продължаваме?")) return;
    setBusy("keys");
    try {
      const { data } = await api.post("/admin/integrations/nextlevel-fulfillment/wc-keys");
      setPlainSecret(data.wc_consumer_secret_plain); setCfg(data); setForm({}); toast.success("Ключовете са генерирани");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };
  const loadLog = async () => {
    setBusy("log");
    try { const { data } = await api.get("/admin/integrations/nextlevel-fulfillment/wc-log"); setLog(data.events || []); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  const save = async (patch = {}) => {
    setBusy("save");
    try {
      const { data } = await api.put("/admin/integrations/nextlevel-fulfillment", { ...form, ...patch });
      setCfg(data); setForm({}); toast.success("Записано");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };
  const runTest = async () => {
    setBusy("test");
    try {
      const { data } = await api.post("/admin/integrations/nextlevel-fulfillment/test");
      setTest(data);
      data.ok ? toast.success(data.mode === "api" ? "Фулфилмент API отговаря" : data.mode === "woocommerce" ? "WooCommerce режимът е готов" : "Webhook адресът е настроен") : toast.error(data.error);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  if (!cfg) return null;
  const v = (k) => (form[k] !== undefined ? form[k] : cfg[k] ?? "");
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "number" ? Number(e.target.value) : e.target.value }));

  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5 mb-8" data-testid="fulfillment-card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-display font-bold text-slate-900 flex items-center gap-2"><PackageCheck className="h-5 w-5 text-coral-600" /> NextLevel Fulfillment — склад</h2>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!cfg.enabled} onChange={(e) => save({ enabled: e.target.checked })} className="h-4 w-4 accent-coral-600" data-testid="fulfillment-enabled" /> Включено
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!cfg.auto_create} onChange={(e) => save({ auto_create: e.target.checked })} className="h-4 w-4 accent-coral-600" data-testid="fulfillment-auto" /> Автоматично при нова поръчка
          </label>
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-4 max-w-3xl">
        Когато е включено, всяка поръчка отива в склада на NextLevel като фулфилмент поръчка (SKU, количества, получател, наложен платеж)
        и складът сам пакетира и издава товарителницата — ние не създаваме отделна. Товарителницата се взима автоматично, клиентът
        получава имейл при изпращане и при доставка. С app-secret четем статуси; само с webhook адрес поръчките само се изпращат.
      </p>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <Field label="app-id на магазина (ff-…)"><input value={v("app_id")} onChange={set("app_id")} className={input} data-testid="fulfillment-app-id" /></Field>
        <Field label="app-secret"><input value={v("app_secret")} onChange={set("app_secret")} className={input} data-testid="fulfillment-app-secret" /></Field>
        <Field label="Тегло на артикул (kg)"><input type="number" step="0.1" value={v("weight")} onChange={set("weight")} className={input} data-testid="fulfillment-weight" /></Field>
        <Field label="Съдържание на товарителницата">
          <input value={v("contents_text")} onChange={set("contents_text")} className={input} placeholder="аминокиселини" data-testid="fulfillment-contents-text" />
        </Field>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Поръчките с банков превод не се подават автоматично към склада — подаваш ги ръчно от поръчката.
        Товарителниците им са без наложен платеж.
      </p>
      <div className="mt-3 text-xs text-slate-500 flex items-center gap-2 font-mono break-all" data-testid="fulfillment-webhook">
        webhook: {cfg.webhook_url || "—"}
        {cfg.webhook_url && (
          <button type="button" onClick={() => { navigator.clipboard?.writeText(cfg.webhook_url); toast.success("Копирано"); }} className="text-slate-400 hover:text-slate-700" aria-label="Копирай" data-testid="fulfillment-webhook-copy"><Copy className="h-3.5 w-3.5" /></button>
        )}
      </div>

      <div className="mt-5 border-t border-slate-200 pt-4" data-testid="fulfillment-wc">
        <h3 className="text-sm font-bold text-slate-900 mb-1">Магазин тип WooCommerce в NextLevel</h3>
        <p className="text-xs text-slate-500 mb-3 max-w-3xl">
          NextLevel очаква WooCommerce магазин. Ние отговаряме на същия REST API — в панела им (Fulfillment → Магазини → WooCommerce)
          въведете адреса на магазина, двата ключа и кода на държавата. Складът чете новите поръчки от тук и връща статус и товарителница обратно.
        </p>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <Field label="Адрес на магазина">
            <div className="mt-1 flex items-center gap-1">
              <input readOnly value={storeUrl} className={input} data-testid="fulfillment-store-url" />
              <button type="button" onClick={() => copyText(storeUrl)} className="text-slate-400 hover:text-slate-700" aria-label="Копирай адреса" data-testid="fulfillment-store-url-copy"><Copy className="h-4 w-4" /></button>
            </div>
          </Field>
          <Field label="Потребителски ключ (consumer key)">
            <div className="mt-1 flex items-center gap-1">
              <input value={v("wc_consumer_key")} onChange={set("wc_consumer_key")} className={input} data-testid="fulfillment-wc-key" />
              {cfg.wc_consumer_key && <button type="button" onClick={() => copyText(cfg.wc_consumer_key)} className="text-slate-400 hover:text-slate-700" aria-label="Копирай ключа" data-testid="fulfillment-wc-key-copy"><Copy className="h-4 w-4" /></button>}
            </div>
          </Field>
          <Field label="Секретен ключ (consumer secret)">
            <div className="mt-1 flex items-center gap-1">
              <input value={plainSecret || v("wc_consumer_secret")} onChange={set("wc_consumer_secret")} className={input} data-testid="fulfillment-wc-secret" />
              {plainSecret && <button type="button" onClick={() => copyText(plainSecret)} className="text-slate-400 hover:text-slate-700" aria-label="Копирай секрета" data-testid="fulfillment-wc-secret-copy"><Copy className="h-4 w-4" /></button>}
            </div>
          </Field>
          <Field label="Код на държавата"><input value={v("wc_country")} onChange={set("wc_country")} maxLength={2} className={input} data-testid="fulfillment-wc-country" /></Field>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button onClick={genKeys} disabled={!!busy} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg disabled:opacity-50" data-testid="fulfillment-wc-generate">
            {busy === "keys" ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} {cfg.has_wc ? "Генерирай нови ключове" : "Генерирай ключове"}
          </button>
          {plainSecret && <span className="text-xs text-amber-700" data-testid="fulfillment-wc-secret-note">Секретът се показва само сега — копирайте го в NextLevel.</span>}
          <button onClick={loadLog} disabled={!!busy} className="ml-auto inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900" data-testid="fulfillment-wc-log-btn">
            <RefreshCw className={`h-4 w-4 ${busy === "log" ? "animate-spin" : ""}`} /> Заявки от NextLevel
          </button>
        </div>
        {log && (
          <ul className="mt-3 font-mono text-xs text-slate-600 space-y-0.5 max-h-48 overflow-auto" data-testid="fulfillment-wc-log">
            {log.length === 0 && <li className="text-slate-400">Още няма заявки от NextLevel.</li>}
            {log.map((e) => (
              <li key={e.id}>{new Date(e.at).toLocaleString("bg-BG")} · {e.direction === "inbound" ? "←" : "→"} {e.method} {e.path} · {e.status}{e.response ? ` · ${String(e.response).slice(0, 60)}` : ""}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => save()} disabled={!!busy || !Object.keys(form).length} className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50" data-testid="fulfillment-save">
          {busy === "save" ? "Записване…" : "Запази"}
        </button>
        <button onClick={runTest} disabled={!!busy || !cfg.app_id} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg disabled:opacity-50" data-testid="fulfillment-test">
          {busy === "test" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Тествай връзката
        </button>
      </div>
      {test && (
        <div className="mt-4 text-sm" data-testid="fulfillment-test-result">
          {test.ok ? (
            <div className="text-emerald-700 space-y-1">
              <p className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4" />
                {test.mode === "api" ? `Свързано · ${test.count} последни фулфилмент поръчки` : test.note}</p>
              <ul className="font-mono text-xs text-slate-500">
                {test.recent?.map((r, i) => <li key={`${r.number}-${i}`}>{r.number} · {r.order_id} · {r.status}{r.awb ? ` · ${r.courier} ${r.awb}` : ""}</li>)}
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
