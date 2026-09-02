import { useState } from "react";
import { toast } from "sonner";
import { Truck, Printer, XCircle, RefreshCw, ExternalLink, AlertTriangle } from "lucide-react";
import { api, formatErr } from "../../lib/api";

const STATUS_TONE = {
  Delivered: "bg-emerald-100 text-emerald-800",
  Cancelled: "bg-slate-200 text-slate-600",
  "In sender": "bg-amber-100 text-amber-900",
};

export const ShipmentCard = ({ order, onChanged }) => {
  const [busy, setBusy] = useState("");
  const sh = order.shipment;
  const active = sh?.awb && sh.status !== "Cancelled";

  const run = async (key, fn, ok) => {
    setBusy(key);
    try { await fn(); if (ok) toast.success(ok); onChanged(); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };
  const create = () => run("create", () => api.post(`/admin/orders/${order.id}/shipment${active ? "" : "?force=true"}`), "Товарителницата е създадена");
  const cancel = () => window.confirm(`Отказ на товарителница ${sh.awb}?`) &&
    run("cancel", () => api.delete(`/admin/orders/${order.id}/shipment`), "Товарителницата е отказана");
  const sync = () => run("sync", () => api.post("/admin/shipments/sync"), "Статусите са обновени");
  const label = () => run("label", async () => {
    const { data } = await api.get(`/admin/orders/${order.id}/shipment/label`, { responseType: "blob" });
    window.open(URL.createObjectURL(data), "_blank");
  });

  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5" data-testid="order-shipment-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2"><Truck className="h-4 w-4 text-coral-600" /> NextLevel товарителница</h3>
        {sh?.status && (
          <span className={`text-xs font-semibold px-2 py-1 rounded ${STATUS_TONE[sh.status] || "bg-sky-100 text-sky-800"}`} data-testid="shipment-status">{sh.status}</span>
        )}
      </div>

      {order.shipment_error && !active && (
        <p className="mb-3 text-sm text-red-700 flex gap-2 bg-red-50 border border-red-200 rounded-lg p-3" data-testid="shipment-error">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /> {order.shipment_error}
        </p>
      )}

      {sh?.awb ? (
        <dl className="text-sm space-y-1.5" data-testid="shipment-details">
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Номер</dt><dd className="font-mono font-semibold" data-testid="shipment-awb">{sh.awb}</dd></div>
          {sh.courier && <div className="flex justify-between gap-3"><dt className="text-slate-500">Куриер</dt><dd className="font-medium">{sh.courier}{sh.courier_awb ? ` · ${sh.courier_awb}` : ""}</dd></div>}
          {sh.total_price && <div className="flex justify-between gap-3"><dt className="text-slate-500">Цена на доставката</dt><dd>{sh.total_price} €</dd></div>}
          {sh.cod_native && <div className="flex justify-between gap-3"><dt className="text-slate-500">Наложен платеж</dt><dd>{sh.cod_native} {sh.currency}</dd></div>}
          {sh.tracking_link && (
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Проследяване</dt>
              <dd><a href={sh.tracking_link} target="_blank" rel="noreferrer" className="text-coral-600 inline-flex items-center gap-1" data-testid="shipment-tracking-link">при куриера <ExternalLink className="h-3 w-3" /></a></dd></div>
          )}
        </dl>
      ) : (
        <p className="text-sm text-slate-500">Няма създадена товарителница за тази поръчка.</p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {!active && (
          <button onClick={create} disabled={!!busy} className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-60" data-testid="shipment-create-btn">
            {busy === "create" ? "Създаване…" : sh?.awb ? "Създай нова" : "Създай товарителница"}
          </button>
        )}
        {active && (
          <>
            <button onClick={label} disabled={!!busy} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg" data-testid="shipment-label-btn">
              <Printer className="h-4 w-4" /> Етикет PDF
            </button>
            <button onClick={sync} disabled={!!busy} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg" data-testid="shipment-sync-btn">
              <RefreshCw className={`h-4 w-4 ${busy === "sync" ? "animate-spin" : ""}`} /> Обнови статуса
            </button>
            <button onClick={cancel} disabled={!!busy} className="inline-flex items-center gap-1.5 text-red-700 hover:bg-red-50 text-sm font-medium px-3 py-2 rounded-lg" data-testid="shipment-cancel-btn">
              <XCircle className="h-4 w-4" /> Откажи
            </button>
          </>
        )}
      </div>
    </section>
  );
};
