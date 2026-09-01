import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR, fmtMoney } from "../lib/api";

const TABS = [
  { key: "all", label: "Всички" },
  { key: "unfulfilled", label: "Неизпратени" },
  { key: "unpaid", label: "Неплатени" },
  { key: "open", label: "Отворени" },
  { key: "archived", label: "Архив" },
];

const PAY_BADGE = {
  paid: { label: "Платена", cls: "bg-emerald-100 text-emerald-800" },
  awaiting_payment: { label: "Очаква плащане", cls: "bg-orange-100 text-orange-900" },
  pending: { label: "Очаква плащане", cls: "bg-orange-100 text-orange-900" },
  refunded: { label: "Възстановена", cls: "bg-slate-200 text-slate-700" },
  voided: { label: "Анулирана", cls: "bg-slate-200 text-slate-700" },
};
const FUL_BADGE = {
  unfulfilled: { label: "Неизпратена", cls: "bg-amber-100 text-amber-900" },
  fulfilled: { label: "Изпратена", cls: "bg-emerald-100 text-emerald-800" },
  shipped: { label: "Изпратена", cls: "bg-emerald-100 text-emerald-800" },
  cancelled: { label: "Отказана", cls: "bg-slate-200 text-slate-700" },
};

export const Badge = ({ map, value }) => {
  const b = map[value] || { label: value || "—", cls: "bg-slate-100 text-slate-700" };
  return <span className={`text-xs font-semibold px-2.5 py-1 rounded-md ${b.cls}`}>{b.label}</span>;
};

const fmtTime = (v) =>
  v ? new Date(v).toLocaleString("bg-BG", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const perPage = 50;

  const load = useCallback(() => {
    setLoading(true);
    const params = { limit: perPage, skip: page * perPage };
    if (filter !== "all") params.status = filter;
    if (search.trim()) params.search = search.trim();
    api.get("/admin/orders", { params })
      .then(({ data }) => { setOrders(data.orders); setTotal(data.total); })
      .finally(() => setLoading(false));
  }, [filter, search, page]);

  useEffect(() => { const t = setTimeout(load, search ? 350 : 0); return () => clearTimeout(t); }, [load, search]);
  useEffect(() => setPage(0), [filter, search]);

  return (
    <AdminLayout title="Поръчки">
      <div className="relative mb-4">
        <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Търсене по номер, име, имейл или телефон"
          className="w-full bg-slate-100 rounded-full pl-9 pr-4 py-2.5 text-sm outline-none focus:bg-white focus:ring-2 focus:ring-coral-200"
          data-testid="orders-search" />
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar mb-4" data-testid="orders-filter-tabs">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setFilter(t.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold whitespace-nowrap transition-colors ${
              filter === t.key ? "bg-slate-900 text-white" : "bg-white text-slate-600 border border-slate-200 hover:border-slate-400"
            }`}
            data-testid={`orders-tab-${t.key}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" data-testid="orders-list">
        {loading && orders.length === 0 && <p className="p-6 text-sm text-slate-400">Зареждане…</p>}
        {!loading && orders.length === 0 && <p className="p-8 text-sm text-slate-500 text-center">Няма поръчки.</p>}
        {orders.map((o) => (
          <Link key={o.id} to={`/admin/orders/${o.id}`} className="block px-4 py-4 hover:bg-slate-50 transition-colors"
            data-testid={`admin-order-${o.order_number}`}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-bold text-slate-900">{o.order_number}</span>
              <span className="font-semibold text-slate-900" data-testid={`order-total-${o.order_number}`}>
                {fmtMoney(o.total_display ?? o.total_eur, o.currency)}
                {o.currency && o.currency !== "EUR" && (
                  <span className="ml-1.5 text-xs font-normal text-slate-500">≈ {fmtEUR(o.total_eur)}</span>
                )}
              </span>
            </div>
            <p className="text-sm text-slate-600 mt-0.5">
              {o.customer.name || o.customer.email || "—"} • {o.items_count} {o.items_count === 1 ? "артикул" : "артикула"} • {fmtTime(o.created_at)}
            </p>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <Badge map={FUL_BADGE} value={o.fulfillment_status} />
              <Badge map={PAY_BADGE} value={o.payment_status} />
            </div>
            {o.shipping_method && <p className="text-sm text-slate-500 mt-1.5">{o.shipping_method}</p>}
          </Link>
        ))}
      </div>

      {total > perPage && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <button onClick={() => setPage((p) => Math.max(p - 1, 0))} disabled={page === 0}
            className="px-4 py-2 rounded-md border border-slate-300 disabled:opacity-40" data-testid="orders-prev">
            ← Назад
          </button>
          <span className="text-slate-500">{page * perPage + 1}–{Math.min((page + 1) * perPage, total)} от {total}</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={(page + 1) * perPage >= total}
            className="px-4 py-2 rounded-md border border-slate-300 disabled:opacity-40" data-testid="orders-next">
            Напред →
          </button>
        </div>
      )}
    </AdminLayout>
  );
}

export { PAY_BADGE, FUL_BADGE };
