import { useEffect, useState } from "react";
import { Languages, Square, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { Button } from "../components/ui/button";
import { api, formatErr } from "../lib/api";
import { LOCALE_META } from "../i18n/locales";

const TARGETS = Object.keys(LOCALE_META).filter((l) => l !== "bg");
const COVERAGE = [
  "Продукти — заглавие, описание, мета заглавие и мета описание",
  "Колекции — заглавие, описание, име в менюто, мета заглавие и описание",
  "Статии от блога — заглавие, откъс, съдържание, мета данни",
  "Статични страници — Контакти, Доставка, Условия, Политики, FAQ и др.",
  "Настройки на сайта — лента със съобщения, слоган, текст във футъра",
  "Чекаут и всички текстове на сайта — бутони, полета, съобщения, контакти",
];

const active = (job) => job && ["queued", "running"].includes(job.status);

export default function AdminTranslationsPage() {
  const [job, setJob] = useState(null);
  const [history, setHistory] = useState([]);
  const [overwrite, setOverwrite] = useState(false);
  const [locales, setLocales] = useState(TARGETS);
  const [busy, setBusy] = useState(false);

  const load = () => Promise.all([
    api.get("/admin/translate/bulk").then(({ data }) => setJob(data.job)),
    api.get("/admin/translate/bulk/history").then(({ data }) => setHistory(data.jobs)),
  ]).catch(() => {});

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!active(job)) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [job?.status]);

  const start = async () => {
    if (!locales.length) return toast.error("Избери поне един език");
    if (overwrite && !window.confirm("Ще презапишеш ВСИЧКИ съществуващи преводи, включително ръчно редактираните. Продължаваш ли?")) return;
    setBusy(true);
    try {
      await api.post("/admin/translate/bulk", { resource: "everything", overwrite, locales });
      toast.success("Преводът е в опашката — работи на заден план, дори да затвориш страницата");
      await load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const stop = async () => {
    try { await api.post("/admin/translate/bulk/stop"); toast("Спряно"); await load(); }
    catch (e) { toast.error(formatErr(e)); }
  };

  const toggle = (l) => setLocales((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l]));
  const pct = job?.total ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <AdminLayout title="Преводи">
      <div className="max-w-4xl space-y-6" data-testid="admin-translations">
        <div className="bg-white border border-slate-200 rounded-2xl p-6">
          <div className="flex items-start gap-3">
            <Languages className="h-6 w-6 text-coral-600 mt-0.5" />
            <div>
              <h2 className="text-lg font-bold text-slate-900">Преведи абсолютно всичко</h2>
              <p className="text-sm text-slate-600 mt-1">
                Един бутон слага в опашката всеки текст на сайта за всеки език. Работи на заден план и продължава след рестарт.
              </p>
            </div>
          </div>

          <ul className="mt-5 grid sm:grid-cols-2 gap-2 text-sm text-slate-700" data-testid="translate-coverage">
            {COVERAGE.map((c) => (
              <li key={c} className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />{c}</li>
            ))}
          </ul>

          <div className="mt-6">
            <p className="text-xs uppercase tracking-wide text-slate-500 font-bold mb-2">Езици</p>
            <div className="flex flex-wrap gap-2">
              {TARGETS.map((l) => (
                <button key={l} type="button" onClick={() => toggle(l)} data-testid={`translate-locale-${l}`}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${locales.includes(l)
                    ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-300 hover:border-slate-500"}`}>
                  {LOCALE_META[l].label}
                </button>
              ))}
            </div>
          </div>

          <label className="mt-5 flex items-center gap-3 text-sm text-slate-700 cursor-pointer">
            <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)}
              className="h-4 w-4 accent-coral-600" data-testid="translate-overwrite" />
            Презапиши съществуващите преводи (иначе се превежда само липсващото)
          </label>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={start} disabled={busy || active(job)} className="bg-coral-600 hover:bg-coral-700 text-white px-6"
              data-testid="translate-everything-btn">
              {active(job) ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Languages className="h-4 w-4 mr-2" />}
              {active(job) ? "Превеждам…" : `Преведи всичко на ${locales.length} езика`}
            </Button>
            {active(job) && (
              <Button variant="outline" onClick={stop} data-testid="translate-stop-btn">
                <Square className="h-4 w-4 mr-2" /> Спри
              </Button>
            )}
          </div>
        </div>

        {job && (
          <div className="bg-white border border-slate-200 rounded-2xl p-6" data-testid="translate-progress">
            <div className="flex justify-between text-sm">
              <span className="font-semibold text-slate-900">
                {job.status === "finished" ? "Готово" : job.status === "stopped" ? "Спряно" : "В процес"}
                {" · "}{job.done}/{job.total}
              </span>
              <span className="text-slate-500">{pct}%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-coral-600 transition-[width]" style={{ width: `${pct}%` }} />
            </div>
            {job.current && <p className="mt-2 text-xs text-slate-500 font-mono" data-testid="translate-current">{job.current}</p>}
            {job.failed?.length > 0 && (
              <div className="mt-4 text-sm text-red-700 flex gap-2" data-testid="translate-failed">
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>Неуспешни ({job.failed.length}): {job.failed.join(", ")}</span>
              </div>
            )}
          </div>
        )}

        {history.length > 1 && (
          <div className="bg-white border border-slate-200 rounded-2xl p-6">
            <p className="text-xs uppercase tracking-wide text-slate-500 font-bold mb-3">Последни преводи</p>
            <ul className="text-sm text-slate-700 space-y-1">
              {history.slice(1).map((h) => (
                <li key={h.id} className="flex justify-between gap-4">
                  <span>{new Date(h.created_at).toLocaleString("bg-BG")} · {h.resource} · {h.locales?.length} езика</span>
                  <span className="text-slate-500">{h.status} {h.done}/{h.total}{h.failed?.length ? ` · ${h.failed.length} грешки` : ""}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
