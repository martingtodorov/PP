import { useEffect, useState } from "react";
import AdminLayout from "../components/AdminLayout";
import { api } from "../lib/api";

export default function AdminCustomersPage() {
  const [customers, setCustomers] = useState([]);

  useEffect(() => {
    api.get("/admin/customers").then(({ data }) => setCustomers(data.customers));
  }, []);

  return (
    <AdminLayout title="Клиенти">
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Име</th>
              <th className="text-left px-4 py-3">Имейл</th>
              <th className="text-left px-4 py-3">Телефон</th>
              <th className="text-left px-4 py-3">Поръчки</th>
              <th className="text-left px-4 py-3">Регистриран</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`customer-${c.email}`}>
                <td className="px-4 py-3 font-medium">{c.name || "—"}</td>
                <td className="px-4 py-3">{c.email}</td>
                <td className="px-4 py-3 text-slate-500">{c.phone || "—"}</td>
                <td className="px-4 py-3 font-semibold">{c.orders_count}</td>
                <td className="px-4 py-3 text-slate-500">{new Date(c.created_at).toLocaleDateString("bg-BG")}</td>
              </tr>
            ))}
            {customers.length === 0 && <tr><td colSpan="5" className="text-center text-slate-500 py-10">Няма регистрирани клиенти.</td></tr>}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
