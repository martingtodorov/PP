import { useState } from "react";
import { Stethoscope, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { api, formatErr } from "../../lib/api";

const Flag = ({ ok, label }) => (
  <span className={`inline-flex items-center gap-1 text-xs font-medium ${ok ? "text-emerald-700" : "text-red-600"}`}>
    {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}{label}
  </span>
);

export const MediaStatusPanel = () => {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const run = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/media/status");
      setStatus(data);
      if (!data.writable) toast.error("Папката за снимки НЕ е записваема — качването не може да работи");
      else if (data.broken.length) toast.error(`${data.broken.length} снимки не могат да се покажат`);
      else toast.success("Всички снимки са на диска");
    } catch (e) { toast.error(formatErr(e)); } finally { setLoading(false); }
  };

  return (
    <div className="mt-6 border-t border-slate-200 pt-6" data-testid="media-status-panel">
      <p className="text-xs uppercase tracking-wide text-slate-500 font-bold mb-2">Диагностика на снимките</p>
      <p className="text-sm text-slate-600">
        Показва къде този сървър пази снимките, дали може да записва в папката и кои от използваните снимки липсват.
      </p>
      <Button onClick={run} disabled={loading} variant="outline" className="mt-3" data-testid="media-status-btn">
        <Stethoscope className="h-4 w-4 mr-1" /> {loading ? "Проверявам…" : "Провери снимките"}
      </Button>
      {status && (
        <div className="mt-4 text-sm text-slate-700 space-y-2" data-testid="media-status-result">
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs">
            <span>папка: <strong data-testid="media-root">{status.media_root}</strong></span>
            <span>потребител: {status.process_user}</span>
            <span>файлове на диска: {status.files_on_disk} ({status.size_mb} MB)</span>
            <span>записи в базата: {status.files_in_db} · използвани: {status.referenced}</span>
          </div>
          <div className="flex flex-wrap gap-4">
            <Flag ok={status.exists} label="папката съществува" />
            <Flag ok={status.writable} label="записваема" />
            <Flag ok={status.image_cache_writable} label="кешът е записваем" />
            {status.remote_enabled && <Flag ok={status.remote_ok} label="огледално хранилище" />}
          </div>
          {status.write_error && <p className="text-red-600 text-xs font-mono" data-testid="media-write-error">{status.write_error}</p>}
          {status.remote_error && <p className="text-amber-700 text-xs font-mono">{status.remote_error}</p>}
          {status.broken.length > 0 && (
            <div className="border border-red-200 bg-red-50 rounded-lg p-3">
              <p className="font-semibold text-red-800 text-xs mb-2">Липсващи ({status.broken.length})</p>
              <ul className="space-y-1 max-h-56 overflow-y-auto font-mono text-[11px]" data-testid="media-broken-list">
                {status.broken.map((b) => (
                  <li key={b.path} className="flex flex-wrap gap-2">
                    <span className="truncate max-w-full">{b.path}</span>
                    <span className="text-slate-500">{b.on_disk ? "на диска" : "НЕ е на диска"} · {b.record ? "има запис" : "без запис"}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
