import { useEffect, useState } from "react";
import { X } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR } from "../lib/api";

const fmtDate = (v) => (v ? new Date(v).toLocaleDateString("bg-BG") : "—");

export default function AdminCustomersPage() {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api.get("/admin/customers").then(({ data }) => setCustomers(data.customers));
  }, []);

  const openDetail = async (c) => {
    setDetail({ customer: c, orders: null });
    const { data } = await api.get(`/admin/customers/${encodeURIComponent(c.email)}/orders`);
    setDetail({ customer: c, ...data });
  };

  const q = search.trim().toLowerCase();
  const filtered = q
    ? customers.filter((c) => `${c.email} ${c.name || ""} ${c.phone || ""}`.toLowerCase().includes(q))
    : customers;
  const totalSpent = customers.reduce((s, c) => s + (c.total_spent || 0), 0);

  return (
    <AdminLayout title="Клиенти">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <input placeholder="Търсене по имейл, име или телефон…" value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-slate-300 rounded-md px-4 py-2 text-sm flex-1 min-w-[220px] max-w-md"
          data-testid="customers-search" />
        <span className="text-xs text-slate-500" data-testid="customers-summary">
          {customers.length} клиенти · оборот {fmtEUR(totalSpent)}
        </span>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Име</th>
              <th className="text-left px-4 py-3">Имейл</th>
              <th className="text-left px-4 py-3">Телефон</th>
              <th className="text-left px-4 py-3">Поръчки</th>
              <th className="text-left px-4 py-3">Похарчено</th>
              <th className="text-left px-4 py-3">Последна поръчка</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 500).map((c) => (
              <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                onClick={() => openDetail(c)} data-testid={`customer-${c.email}`}>
                <td className="px-4 py-3 font-medium">{c.name?.trim() || "—"}</td>
                <td className="px-4 py-3">{c.email}</td>
                <td className="px-4 py-3 text-slate-500">{c.phone || "—"}</td>
                <td className="px-4 py-3 font-semibold">{c.total_orders ?? c.orders_count ?? 0}</td>
                <td className="px-4 py-3 font-semibold">{fmtEUR(c.total_spent || 0)}</td>
                <td className="px-4 py-3 text-slate-500">{fmtDate(c.last_order_at || c.created_at)}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan="6" className="text-center text-slate-500 py-10">Няма клиенти.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > 500 && (
        <p className="text-xs text-slate-400 mt-3">Показани са първите 500 от {filtered.length}. Използвайте търсенето.</p>
      )}

      {detail && (
        <div className="fixed inset-0 bg-slate-900/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6"
          onClick={() => setDetail(null)} data-testid="customer-detail-overlay">
          <div className="bg-white w-full sm:max-w-2xl max-h-[85vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl p-5"
            onClick={(e) => e.stopPropagation()} data-testid="customer-detail">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="font-bold text-lg text-slate-900">{detail.customer.name?.trim() || detail.customer.email}</h2>
                <p className="text-sm text-slate-500">{detail.customer.email} · {detail.customer.phone || "без телефон"}</p>
              </div>
              <button onClick={() => setDetail(null)} className="p-2 text-slate-400 hover:text-slate-700"
                data-testid="customer-detail-close"><X className="h-5 w-5" /></button>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-[11px] uppercase text-slate-500">Поръчки</p>
                <p className="font-bold text-slate-900">{detail.orders_count ?? detail.customer.total_orders ?? 0}</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-[11px] uppercase text-slate-500">Похарчено</p>
                <p className="font-bold text-slate-900">{fmtEUR(detail.total_spent ?? detail.customer.total_spent ?? 0)}</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-[11px] uppercase text-slate-500">Клиент от</p>
                <p className="font-bold text-slate-900">{fmtDate(detail.customer.first_order_at || detail.customer.created_at)}</p>
              </div>
            </div>

            {detail.orders === null ? (
              <p className="text-sm text-slate-400">Зареждане на историята…</p>
            ) : detail.orders.length === 0 ? (
              <p className="text-sm text-slate-500">Няма намерени поръчки за този имейл.</p>
            ) : (
              <ul className="divide-y divide-slate-100" data-testid="customer-orders-list">
                {detail.orders.map((o) => (
                  <li key={o.id} className="py-3">
                    <div className="flex justify-between items-baseline gap-3">
                      <span className="font-semibold text-slate-900">{o.order_number}</span>
                      <span className="font-semibold">{fmtEUR(o.total_eur)}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {fmtDate(o.created_at)} · {o.status} · {(o.line_items || []).map((li) => `${li.title}${li.variant ? ` (${li.variant})` : ""} ×${li.quantity}`).join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
