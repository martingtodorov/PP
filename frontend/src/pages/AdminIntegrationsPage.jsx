import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Eye, EyeOff, KeyRound, Loader2, Send } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";

const copy = async (value, label) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} е копиран`);
  } catch (e) {
    toast.error("Копирането не е разрешено от браузъра");
  }
};

/** Read-only value with a copy button — webhook URL and the revealed keys. */
const CopyField = ({ value, label, testId, mono = true }) => (
  <div className="flex items-center gap-2 min-w-0">
    <code className={`flex-1 min-w-0 truncate rounded-md bg-slate-50 border border-slate-200 px-2 py-1.5 text-xs ${mono ? "font-mono" : ""}`}
      data-testid={testId}>{value || "—"}</code>
    <button type="button" onClick={() => copy(value, label)} disabled={!value}
      className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-40 transition-colors"
      title={`Копирай ${label}`} data-testid={`${testId}-copy`}>
      <Copy className="h-4 w-4" />
    </button>
  </div>
);

const DomainCard = ({ domain, cfg, onChanged }) => {
  const [form, setForm] = useState({ api_base: cfg.api_base, orders_path: cfg.orders_path, enabled: cfg.enabled });
  const [shown, setShown] = useState(null);
  const [busy, setBusy] = useState("");

  // never reset `shown` here: the reload right after "Генерирай" would hide the fresh keys
  useEffect(() => {
    setForm({ api_base: cfg.api_base, orders_path: cfg.orders_path, enabled: cfg.enabled });
  }, [cfg]);

  useEffect(() => setShown(null), [domain]);

  const run = async (kind, fn) => {
    setBusy(kind);
    try { await fn(); } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  const generate = () => run("gen", async () => {
    const { data } = await api.post("/admin/integrations/revorder/generate", { domain });
    setShown(data);
    toast.success("Новите ключове са генерирани — копирай ги в RevOrder");
    onChanged();
  });

  const reveal = () => run("reveal", async () => {
    if (shown) { setShown(null); return; }
    const { data } = await api.get("/admin/integrations/revorder/reveal", { params: { domain } });
    setShown(data);
  });

  const save = (patch = {}) => run("save", async () => {
    const body = { domain, ...form, ...patch };
    await api.put("/admin/integrations/revorder", body);
    setForm((f) => ({ ...f, ...patch }));
    toast.success("Запазено");
    onChanged();
  });

  const test = () => run("test", async () => {
    const { data } = await api.post("/admin/integrations/revorder/test", { domain });
    if (data.sent) toast.success(`RevOrder отговори ${data.status}`);
    else toast.error(`Неуспешно: ${data.reason || data.status} ${data.response || ""}`.trim());
    onChanged();
  });

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`revorder-card-${domain}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="font-display font-bold text-slate-900">{domain}</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {cfg.has_keys
              ? `Ключове: издадени${cfg.updated_at ? ` · ${new Date(cfg.updated_at).toLocaleString("bg-BG")}` : ""}`
              : "Ключове: още не са издадени"}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700 cursor-pointer">
          <input type="checkbox" checked={form.enabled}
            onChange={(e) => save({ enabled: e.target.checked })}
            className="h-4 w-4 accent-coral-600" data-testid={`revorder-enabled-${domain}`} />
          Изпращай поръчките
        </label>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500 mb-1.5">Webhook URL (дай го на RevOrder)</p>
          <CopyField value={cfg.webhook_url} label="Webhook URL" testId={`revorder-webhook-${domain}`} />
          {Object.entries(cfg.aliases || {}).map(([alias, url]) => (
            <div key={alias} className="mt-2">
              <p className="text-[11px] text-slate-500 mb-1">
                Същите ключове важат и за <strong>{alias}</strong>:
              </p>
              <CopyField value={url} label="Webhook URL" testId={`revorder-webhook-${alias}`} />
            </div>
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1.5">API key</p>
            <CopyField value={shown ? shown.api_key : cfg.api_key} label="API key"
              testId={`revorder-apikey-${domain}`} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1.5">Secret key (за HMAC подписа)</p>
            <CopyField value={shown ? shown.secret_key : cfg.secret_key} label="Secret key"
              testId={`revorder-secret-${domain}`} />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={generate} disabled={Boolean(busy)}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors"
            data-testid={`revorder-generate-${domain}`}>
            {busy === "gen" ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            {cfg.has_keys ? "Генерирай нови" : "Генерирай ключове"}
          </button>
          <button type="button" onClick={reveal} disabled={!cfg.has_keys || Boolean(busy)}
            className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            data-testid={`revorder-reveal-${domain}`}>
            {shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {shown ? "Скрий" : "Покажи"}
          </button>
          <button type="button" onClick={test} disabled={!cfg.has_keys || !cfg.enabled || Boolean(busy)}
            className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            data-testid={`revorder-test-${domain}`}>
            {busy === "test" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Тествай връзката
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-[1fr_200px] pt-1">
          <label className="text-xs text-slate-500">
            RevOrder API адрес
            <input value={form.api_base} onChange={(e) => setForm({ ...form, api_base: e.target.value })}
              onBlur={() => save()}
              className="mt-1 w-full border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono text-slate-900"
              data-testid={`revorder-apibase-${domain}`} />
          </label>
          <label className="text-xs text-slate-500">
            Път за поръчките
            <input value={form.orders_path} onChange={(e) => setForm({ ...form, orders_path: e.target.value })}
              onBlur={() => save()}
              className="mt-1 w-full border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono text-slate-900"
              data-testid={`revorder-orderspath-${domain}`} />
          </label>
        </div>
      </div>
    </div>
  );
};

export default function AdminIntegrationsPage() {
  const [domains, setDomains] = useState({});
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/integrations/revorder");
      setDomains(data.domains || {});
      setEvents(data.events || []);
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminLayout title="Интеграции — RevOrder">
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">
        Ключовете се издават тук и се поставят в RevOrder. <strong>Webhook URL</strong> е нашият входящ
        адрес — RevOrder го вика при промяна на поръчка и подписва тялото с HMAC-SHA256 върху
        secret key-а. Щом домейнът е включен и има ключове, всяка нова поръчка от чекаута се изпраща
        автоматично.
      </p>

      {loading ? (
        <p className="text-slate-500">Зареждане…</p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2" data-testid="revorder-domains">
          {Object.entries(domains).map(([domain, cfg]) => (
            <DomainCard key={domain} domain={domain} cfg={cfg} onChanged={load} />
          ))}
        </div>
      )}

      <h2 className="font-display font-bold text-slate-900 mt-10 mb-3">Последни събития</h2>
      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Кога</th>
              <th className="text-left px-4 py-3">Домейн</th>
              <th className="text-left px-4 py-3">Посока</th>
              <th className="text-left px-4 py-3">Поръчка</th>
              <th className="text-left px-4 py-3">Резултат</th>
            </tr>
          </thead>
          <tbody data-testid="revorder-events">
            {events.map((e, i) => (
              <tr key={`${e.created_at}-${i}`} className="border-t border-slate-100">
                <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
                  {e.created_at ? new Date(e.created_at).toLocaleString("bg-BG") : "—"}
                </td>
                <td className="px-4 py-3">{e.domain}</td>
                <td className="px-4 py-3">{e.direction === "inbound" ? "входящо" : "изходящо"}</td>
                <td className="px-4 py-3 font-mono text-xs">{e.order_number || e.order_ref || "—"}</td>
                <td className="px-4 py-3 text-xs">
                  <span className={e.ok === false ? "text-red-600" : "text-emerald-700"}>
                    {e.status_code ?? (e.matched ? "приложено" : "прието")}
                  </span>
                  {e.response ? <span className="text-slate-500"> · {String(e.response).slice(0, 80)}</span> : null}
                </td>
              </tr>
            ))}
            {!events.length && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">Още няма събития.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
