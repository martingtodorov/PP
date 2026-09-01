import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { TrendingUp, ShoppingBag, Clock, Truck, Users, Package, Coins } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR } from "../lib/api";

const Stat = ({ icon: Icon, label, value, hint, accent = "coral" }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-5">
    <div className={`w-9 h-9 rounded-lg flex items-center justify-center bg-${accent}-50 text-${accent}-600`}>
      <Icon className="h-5 w-5" />
    </div>
    <p className="text-xs uppercase tracking-wider text-slate-500 mt-4">{label}</p>
    <p className="font-display font-extrabold text-2xl text-slate-900 mt-1" data-testid={`stat-${label.toLowerCase().replace(/\s+/g,'-')}`}>{value}</p>
    {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
  </div>
);

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    api.get("/admin/stats").then(({ data }) => setStats(data)).catch(() => {});
    api.get("/admin/orders").then(({ data }) => setRecent(data.orders.slice(0, 8))).catch(() => {});
  }, []);

  return (
    <AdminLayout title="Табло">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat icon={Coins} label="Приходи" value={stats ? fmtEUR(stats.revenue_eur) : "…"} hint="Платени поръчки" accent="emerald" />
        <Stat icon={ShoppingBag} label="Поръчки" value={stats?.total_orders ?? "…"} accent="coral" />
        <Stat icon={Clock} label="Очакват плащане" value={stats?.awaiting_payment ?? "…"} accent="amber" />
        <Stat icon={Truck} label="За изпращане" value={stats?.pending_shipments ?? "…"} accent="indigo" />
        <Stat icon={Users} label="Клиенти" value={stats?.customers ?? "…"} accent="coral" />
        <Stat icon={Package} label="Продукти" value={stats?.products ?? "…"} accent="slate" />
        <Stat icon={TrendingUp} label="Платени" value={stats?.paid ?? "…"} accent="emerald" />
      </div>

      <section className="mt-10 bg-white border border-slate-200 rounded-xl">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="font-display font-bold text-slate-900">Последни поръчки</h2>
          <Link to="/admin/orders" className="text-sm font-semibold text-coral-600">Виж всички →</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="text-left px-6 py-3">№</th>
                <th className="text-left px-6 py-3">Клиент</th>
                <th className="text-left px-6 py-3">Сума</th>
                <th className="text-left px-6 py-3">Статус</th>
                <th className="text-left px-6 py-3">Дата</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((o) => (
                <tr key={o.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`recent-order-${o.order_number}`}>
                  <td className="px-6 py-3 font-mono font-semibold">{o.order_number}</td>
                  <td className="px-6 py-3">{o.customer_name}<div className="text-xs text-slate-500">{o.customer_email}</div></td>
                  <td className="px-6 py-3 font-semibold">{fmtEUR(o.total_eur)}</td>
                  <td className="px-6 py-3"><span className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-700">{o.payment_status}</span></td>
                  <td className="px-6 py-3 text-slate-500">{new Date(o.created_at).toLocaleDateString("bg-BG")}</td>
                </tr>
              ))}
              {recent.length === 0 && <tr><td colSpan="5" className="text-center text-slate-500 py-10">Няма поръчки.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </AdminLayout>
  );
}
