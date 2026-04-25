import { useEffect, useState } from "react";
import { Upload, FileText } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { Button } from "../components/ui/button";
import { api, formatErr } from "../lib/api";

export default function AdminImportPage() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState([]);

  const loadLogs = () => api.get("/admin/imports").then(({ data }) => setLogs(data.imports));
  useEffect(() => { loadLogs(); }, []);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/import/products", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Импортирани: ${data.inserted} нови, ${data.updated} обновени`);
      setFile(null);
      loadLogs();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <AdminLayout title="Импорт от Matrixify / Shopify">
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-8">
          <div className="border-2 border-dashed border-slate-300 rounded-xl p-10 text-center">
            <Upload className="h-10 w-10 mx-auto text-slate-400" />
            <p className="mt-4 font-medium text-slate-900">Качете Matrixify CSV файл</p>
            <p className="text-xs text-slate-500 mt-1">Очаквани колони: Handle, Title, Body HTML, Image Src, Variant SKU, Variant Price, Variant Inventory Qty, Tags, Collection</p>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="mt-6 mx-auto block text-sm"
              data-testid="import-file-input"
            />
            {file && <p className="text-xs text-slate-700 mt-3 font-medium">{file.name}</p>}
            <Button onClick={upload} disabled={!file || busy} className="mt-6 bg-coral-600 hover:bg-coral-700" data-testid="import-submit-btn">
              {busy ? "Качване…" : "Импортирай"}
            </Button>
          </div>
          <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm">
            <p className="font-semibold text-amber-900">Съвет</p>
            <p className="text-amber-800 mt-1">При повторно качване продуктите ще бъдат обновени по handle (без дублиране).</p>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-display font-bold text-slate-900 mb-4 flex items-center gap-2"><FileText className="h-4 w-4" /> История на импортите</h2>
          <ul className="space-y-3">
            {logs.length === 0 && <p className="text-sm text-slate-500">Няма импорти все още.</p>}
            {logs.map((l) => (
              <li key={l.id} className="border border-slate-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-slate-900 truncate">{l.filename || l.type}</p>
                <p className="text-xs text-slate-500 mt-1">+{l.inserted} • ↻{l.updated} • {l.errors?.length || 0} грешки</p>
                <p className="text-xs text-slate-400">{new Date(l.at).toLocaleString("bg-BG")}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}
