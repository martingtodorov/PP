import { useState } from "react";
import { toast } from "sonner";
import { PackageCheck, XCircle, RefreshCw, AlertTriangle } from "lucide-react";
import { api, formatErr } from "../../lib/api";

const TONE = {
  delivered: "bg-emerald-100 text-emerald-800",
  shipped: "bg-sky-100 text-sky-800",
  cancelled: "bg-slate-200 text-slate-600",
  pending: "bg-amber-100 text-amber-900",
  new: "bg-amber-100 text-amber-900",
};
const DONE = ["delivered", "returned", "cancelled", "duplicated", "trash"];

export const FulfillmentOrderCard = ({ order, onChanged }) => {
  const [busy, setBusy] = useState("");
  const ff = order.fulfillment;
  const active = ff?.number && !DONE.includes(ff.status || "");

  const run = async (key, fn, ok) => {
    setBusy(key);
    try { await fn(); if (ok) toast.success(ok); onChanged(); }
    catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };
  const create = () => run("create", () => api.post(`/admin/orders/${order.id}/fulfillment${ff?.number ? "?force=true" : ""}`), "Поръчката е подадена към склада");
  const cancel = () => window.confirm(`Отказ на фулфилмент поръчка ${ff.number}?`) &&
    run("cancel", () => api.delete(`/admin/orders/${order.id}/fulfillment`), "Фулфилмент поръчката е отказана");
  const refresh = () => run("refresh", () => api.post(`/admin/orders/${order.id}/fulfillment/refresh`), "Статусът е обновен");
  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5" data-testid="order-warehouse-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2"><PackageCheck className="h-4 w-4 text-coral-600" /> NextLevel фулфилмент</h3>
        {ff?.status && (
          <span className={`text-xs font-semibold px-2 py-1 rounded ${TONE[ff.status] || "bg-sky-100 text-sky-800"}`} data-testid="fulfillment-status">{ff.status}</span>
        )}
      </div>

      {order.fulfillment_error && !active && (
        <p className="mb-3 text-sm text-red-700 flex gap-2 bg-red-50 border border-red-200 rounded-lg p-3" data-testid="fulfillment-error">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /> {order.fulfillment_error}
        </p>
      )}

      {ff?.cancel_error && (
        <p className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3" data-testid="fulfillment-cancel-error">
          <span className="flex gap-2 font-medium"><AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /> Складът не потвърди отказа</span>
          <span className="block mt-1 text-red-600 text-xs">{ff.cancel_error}</span>
          <button onClick={cancel} disabled={!!busy} className="mt-2 inline-flex items-center gap-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-60"
            data-testid="fulfillment-cancel-retry-btn">
            <RefreshCw className={`h-3.5 w-3.5 ${busy === "cancel" ? "animate-spin" : ""}`} /> Опитай пак
          </button>
        </p>
      )}

      {ff?.number ? (
        <dl className="text-sm space-y-1.5" data-testid="fulfillment-details">
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Номер в склада</dt><dd className="font-mono font-semibold" data-testid="fulfillment-number">{ff.number}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Подадена през</dt><dd>{ff.transport === "api" ? "API" : "webhook"} · {new Date(ff.created_at).toLocaleString("bg-BG")}</dd></div>
          {ff.awb && <div className="flex justify-between gap-3"><dt className="text-slate-500">Товарителница</dt><dd className="font-mono">{ff.courier ? `${ff.courier} · ` : ""}{ff.awb}</dd></div>}
          {ff.shipment_status && <div className="flex justify-between gap-3"><dt className="text-slate-500">Пратка</dt><dd>{ff.shipment_status}</dd></div>}
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Съдържание</dt><dd className="font-mono text-xs text-right">{ff.payload?.contents}</dd></div>
        </dl>
      ) : (
        <p className="text-sm text-slate-500">Поръчката не е подадена към склада на NextLevel.</p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {!active && (
          <button onClick={create} disabled={!!busy} className="bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-60" data-testid="fulfillment-create-btn">
            {busy === "create" ? "Подаване…" : ff?.number ? "Подай отново" : "Подай към склада"}
          </button>
        )}
        {active && (
          <>
            <button onClick={refresh} disabled={!!busy} className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-slate-500 text-sm font-medium px-3 py-2 rounded-lg" data-testid="fulfillment-refresh-btn">
              <RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} /> Обнови статуса
            </button>
            <button onClick={cancel} disabled={!!busy} className="inline-flex items-center gap-1.5 text-red-700 hover:bg-red-50 text-sm font-medium px-3 py-2 rounded-lg" data-testid="fulfillment-cancel-btn">
              <XCircle className="h-4 w-4" /> Откажи
            </button>
          </>
        )}
      </div>
    </section>
  );
};
