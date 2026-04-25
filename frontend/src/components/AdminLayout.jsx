import { useEffect } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Package, ShoppingBag, Users, Upload, Settings, LogOut, FolderTree } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/admin", label: "Табло", icon: LayoutDashboard, end: true },
  { to: "/admin/orders", label: "Поръчки", icon: ShoppingBag },
  { to: "/admin/products", label: "Продукти", icon: Package },
  { to: "/admin/customers", label: "Клиенти", icon: Users },
  { to: "/admin/import", label: "Импорт", icon: Upload },
  { to: "/admin/settings", label: "Настройки", icon: Settings },
];

export default function AdminLayout({ children, title }) {
  const { user, logout, loading } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) nav("/admin/login");
  }, [user, loading, nav]);

  if (loading || !user) return <div className="p-10 text-slate-500">Зареждане…</div>;

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="w-60 bg-white border-r border-slate-200 flex flex-col" data-testid="admin-sidebar">
        <Link to="/admin" className="px-6 py-5 border-b border-slate-200">
          <p className="font-display font-extrabold text-lg">Pure<span className="text-coral-600">Peptide</span></p>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-0.5">Admin</p>
        </Link>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive ? "bg-coral-50 text-coral-700" : "text-slate-700 hover:bg-slate-50"
                }`
              }
              data-testid={`admin-nav-${to.split("/").pop() || "dashboard"}`}
            >
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <p className="text-xs text-slate-500 mb-2 px-2 truncate">{user.email}</p>
          <button onClick={async () => { await logout(); nav("/admin/login"); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-slate-700 hover:bg-slate-50">
            <LogOut className="h-4 w-4" /> Изход
          </button>
          <Link to="/" className="block text-xs text-slate-500 hover:text-coral-600 mt-2 px-2">← Към магазина</Link>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <header className="bg-white border-b border-slate-200 px-8 h-16 flex items-center sticky top-0 z-10">
          <h1 className="font-display font-bold text-xl text-slate-900">{title}</h1>
        </header>
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
