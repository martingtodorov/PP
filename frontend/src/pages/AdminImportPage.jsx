import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, FileText, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { Button } from "../components/ui/button";
import { api, formatErr } from "../lib/api";

const STEPS = [
  { key: "products", label: "Продукти (с варианти, SKU, снимки)" },
  { key: "collections", label: "Колекции" },
  { key: "pages", label: "Страници (в „Страници по език“, bg)" },
  { key: "articles", label: "Блог статии" },
  { key: "redirects", label: "Пренасочвания" },
  { key: "discounts", label: "Кодове за отстъпка" },
  { key: "customers", label: "Клиенти" },
  { key: "orders", label: "Поръчки (история на разходите)" },
];

export default function AdminImportPage() {
  const [file, setFile] = useState(null);
  const [steps, setSteps] = useState(["products", "collections"]);
  const [skipImages, setSkipImages] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const timer = useRef(null);

  const loadJobs = useCallback(() => {
    api.get("/admin/import/jobs").then(({ data }) => setJobs(data.jobs)).catch(() => {});
  }, []);
  useEffect(() => { loadJobs(); }, [loadJobs]);

  const poll = useCallback((id) => {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/admin/import/jobs/${id}`);
        setJob(data.job);
        if (data.job.status !== "running") {
          clearInterval(timer.current);
          loadJobs();
          if (data.job.status === "completed") toast.success("Импортът завърши успешно");
          else toast.error("Импортът се провали — виж лога");
        }
      } catch { clearInterval(timer.current); }
    }, 2000);
  }, [loadJobs]);

  useEffect(() => () => clearInterval(timer.current), []);

  const toggle = (key) => setSteps((c) => (c.includes(key) ? c.filter((k) => k !== key) : [...c, key]));

  const upload = async () => {
    if (!file || !steps.length) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("steps", steps.join(","));
      fd.append("skip_images", skipImages ? "true" : "false");
      const { data } = await api.post("/admin/import/matrixify", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.info("Импортът стартира — следи прогреса по-долу");
      setJob({ id: data.job_id, status: "running", log: [], steps: data.steps });
      poll(data.job_id);
      setFile(null);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <AdminLayout title="Импорт от Matrixify">
      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6 min-w-0">
          <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-8">
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 sm:p-10 text-center">
              <Upload className="h-10 w-10 mx-auto text-slate-400" />
              <p className="mt-4 font-medium text-slate-900">Качете Matrixify Excel (.xlsx) експорт</p>
              <p className="text-xs text-slate-500 mt-1">
                Поддържани листове: Products, Custom Collections, Pages, Blog Posts, Redirects, Discounts, Customers, Orders
              </p>
              <input type="file" accept=".xlsx,.xlsm"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="mt-6 mx-auto block text-sm"
                data-testid="import-file-input" />
              {file && <p className="text-xs text-slate-700 mt-3 font-medium">{file.name}</p>}
            </div>

            <div className="mt-6">
              <p className="text-xs uppercase tracking-wide text-slate-500 font-bold mb-3">Какво да импортирам</p>
              <div className="grid sm:grid-cols-2 gap-2" data-testid="import-steps">
                {STEPS.map((s) => (
                  <label key={s.key} className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
                    <input type="checkbox" checked={steps.includes(s.key)} onChange={() => toggle(s.key)}
                      className="mt-0.5 accent-coral-600" data-testid={`import-step-${s.key}`} />
                    {s.label}
                  </label>
                ))}
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700 mt-4 cursor-pointer">
                <input type="checkbox" checked={skipImages} onChange={(e) => setSkipImages(e.target.checked)}
                  className="accent-coral-600" data-testid="import-skip-images" />
                Не сваляй снимките (по-бързо, остават линковете от Shopify)
              </label>
            </div>

            <Button onClick={upload} disabled={!file || busy || !steps.length}
              className="mt-6 bg-coral-600 hover:bg-coral-700" data-testid="import-submit-btn">
              {busy ? "Качване…" : "Стартирай импорта"}
            </Button>
            <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm">
              <p className="font-semibold text-amber-900">Внимание</p>
              <p className="text-amber-800 mt-1">
                Продуктите, колекциите, статиите и клиентите се заместват изцяло от файла (по handle / имейл).
                Свалянето на снимките отнема няколко минути.
              </p>
            </div>
          </div>

          {job && (
            <div className="bg-slate-950 text-slate-200 rounded-xl p-5" data-testid="import-job-panel">
              <div className="flex items-center gap-2 mb-3">
                {job.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-sky-400" />}
                {job.status === "completed" && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
                {job.status === "failed" && <XCircle className="h-4 w-4 text-red-400" />}
                <span className="font-semibold">
                  {job.status === "running" ? "Импортът се изпълнява…" : job.status === "completed" ? "Готово" : "Провалено"}
                </span>
                <span className="text-xs text-slate-500">{(job.steps || []).join(", ")}</span>
              </div>
              <pre className="text-[11px] leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap" data-testid="import-job-log">
                {(job.log || []).join("\n") || "Стартиране…"}
              </pre>
            </div>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="font-display font-bold text-slate-900 mb-4 flex items-center gap-2">
            <FileText className="h-4 w-4" /> История на импортите
          </h2>
          <ul className="space-y-3" data-testid="import-history">
            {jobs.length === 0 && <p className="text-sm text-slate-500">Няма импорти все още.</p>}
            {jobs.map((j) => (
              <li key={j.id} className="border border-slate-200 rounded-lg p-3 text-sm cursor-pointer hover:border-slate-400"
                onClick={() => api.get(`/admin/import/jobs/${j.id}`).then(({ data }) => setJob(data.job))}>
                <p className="font-medium text-slate-900 truncate">{j.filename}</p>
                <p className="text-xs text-slate-500 mt-1">{(j.steps || []).join(", ")}</p>
                {(j.summary || []).length > 0 && (
                  <p className="text-xs text-slate-600 mt-1">{j.summary.join(" · ")}</p>
                )}
                <p className={`text-xs mt-1 ${j.status === "completed" ? "text-emerald-600" : j.status === "failed" ? "text-red-600" : "text-sky-600"}`}>
                  {j.status} · {new Date(j.at).toLocaleString("bg-BG")}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}
