import { useEffect, useState } from "react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { api, fmtEUR, formatErr } from "../lib/api";

const STATUS = {
  awaiting_payment: { label: "Очаква плащане", cls: "bg-amber-100 text-amber-800 border-amber-300" },
  paid: { label: "Платена", cls: "bg-coral-100 text-coral-800 border-coral-300" },
  cancelled: { label: "Отказана", cls: "bg-slate-200 text-slate-700 border-slate-300" },
};
const FSTATUS = {
  unfulfilled: { label: "Неизпратена", cls: "bg-slate-100 text-slate-700 border-slate-300" },
  shipped: { label: "Изпратена", cls: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  fulfilled: { label: "Завършена", cls: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  cancelled: { label: "Отказана", cls: "bg-slate-200 text-slate-700 border-slate-300" },
};

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);

  const load = (f = filter) => {
    const q = f === "all" ? "" : `?status=${f}`;
    api.get(`/admin/orders${q}`).then(({ data }) => setOrders(data.orders));
  };

  useEffect(() => { load(); }, [filter]);

  const markPaid = async (id) => {
    try { await api.post(`/admin/orders/${id}/mark-paid`); toast.success("Маркирана като платена"); load(); setOpen(null); }
    catch (e) { toast.error(formatErr(e)); }
  };
  const createShipment = async (id, carrier) => {
    try { const { data } = await api.post(`/admin/orders/${id}/create-shipment`, { carrier }); toast.success(`Пратка създадена: ${data.tracking.tracking_number}`); load(); setOpen(null); }
    catch (e) { toast.error(formatErr(e)); }
  };

  return (
    <AdminLayout title="Поръчки">
      <Tabs value={filter} onValueChange={setFilter} className="mb-6">
        <TabsList data-testid="orders-filter-tabs">
          <TabsTrigger value="all">Всички</TabsTrigger>
          <TabsTrigger value="awaiting_payment">Очакват плащане</TabsTrigger>
          <TabsTrigger value="paid">Платени</TabsTrigger>
          <TabsTrigger value="shipped">Изпратени</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">№</th>
              <th className="text-left px-4 py-3">Клиент</th>
              <th className="text-left px-4 py-3">Сума</th>
              <th className="text-left px-4 py-3">Плащане</th>
              <th className="text-left px-4 py-3">Изпращане</th>
              <th className="text-left px-4 py-3">Дата</th>
              <th className="text-right px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => {
              const ps = STATUS[o.payment_status] || { label: o.payment_status, cls: "bg-slate-100 text-slate-700" };
              const fs = FSTATUS[o.fulfillment_status] || { label: o.fulfillment_status, cls: "bg-slate-100 text-slate-700" };
              return (
                <tr key={o.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`admin-order-${o.order_number}`}>
                  <td className="px-4 py-3 font-mono font-semibold">{o.order_number}</td>
                  <td className="px-4 py-3">{o.customer_name}<div className="text-xs text-slate-500">{o.customer_email}</div></td>
                  <td className="px-4 py-3 font-semibold">{fmtEUR(o.total_eur)}</td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-1 rounded border ${ps.cls}`}>{ps.label}</span></td>
                  <td className="px-4 py-3"><span className={`text-xs px-2 py-1 rounded border ${fs.cls}`}>{fs.label}</span></td>
                  <td className="px-4 py-3 text-slate-500">{new Date(o.created_at).toLocaleDateString("bg-BG")}</td>
                  <td className="px-4 py-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => setOpen(o)} data-testid={`order-details-${o.order_number}`}>Детайли</Button>
                  </td>
                </tr>
              );
            })}
            {orders.length === 0 && <tr><td colSpan="7" className="text-center text-slate-500 py-10">Няма поръчки.</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={!!open} onOpenChange={(v) => !v && setOpen(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Поръчка {open?.order_number}</DialogTitle>
          </DialogHeader>
          {open && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs text-slate-500">Клиент</p><p className="font-medium">{open.customer_name}</p><p className="text-slate-500 text-xs">{open.customer_email} • {open.customer_phone}</p></div>
                <div><p className="text-xs text-slate-500">Сума</p><p className="font-display font-bold text-lg">{fmtEUR(open.total_eur)}</p></div>
                <div className="col-span-2"><p className="text-xs text-slate-500">Адрес</p><p>{open.shipping?.line1}, {open.shipping?.city} {open.shipping?.postal_code}, {open.shipping?.country}</p></div>
              </div>
              <div className="border-t border-slate-200 pt-3">
                <p className="text-xs text-slate-500 mb-2">Артикули</p>
                <ul className="space-y-1.5">
                  {open.items.map((it) => (
                    <li key={it.variant_sku} className="flex justify-between text-sm">
                      <span>{it.title} — {it.variant_name} × {it.quantity}</span>
                      <span className="font-semibold">{fmtEUR(it.price_eur * it.quantity)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              {open.tracking && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm">
                  <p className="font-semibold text-emerald-800">Пратка: {open.tracking.tracking_number}</p>
                  <a href={open.tracking.tracking_url} target="_blank" rel="noreferrer" className="text-emerald-700 underline text-xs">Проследи</a>
                  {open.tracking.mocked && <p className="text-[10px] text-amber-700 mt-1">MOCKED — добавете реален Speedy/Econt API ключ за production</p>}
                </div>
              )}
              <div className="flex gap-2 border-t border-slate-200 pt-4">
                {open.payment_status === "awaiting_payment" && (
                  <Button onClick={() => markPaid(open.id)} className="bg-coral-600 hover:bg-coral-700" data-testid="mark-paid-btn">Маркирай като платена</Button>
                )}
                {open.payment_status === "paid" && open.fulfillment_status === "unfulfilled" && (
                  <>
                    <Button onClick={() => createShipment(open.id, "speedy")} className="bg-emerald-600 hover:bg-emerald-700" data-testid="create-shipment-speedy-btn">Speedy пратка</Button>
                    <Button onClick={() => createShipment(open.id, "econt")} variant="outline" data-testid="create-shipment-econt-btn">Еконт пратка</Button>
                  </>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AdminLayout>
  );
}
