import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { LayoutDashboard, Package, ShoppingBag, Users, Upload, Settings, LogOut, Globe, Link2Off, FileText, Menu, X, LineChart, Boxes, ListOrdered, MessageSquare, Plug, Languages, Newspaper, Sparkles } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/admin", label: "Табло", icon: LayoutDashboard, end: true },
  { to: "/admin/analytics", label: "Анализи", icon: LineChart },
  { to: "/admin/orders", label: "Поръчки", icon: ShoppingBag },
  { to: "/admin/products", label: "Продукти", icon: Package },
  { to: "/admin/collections", label: "Подредба на колекции", icon: ListOrdered },
  { to: "/admin/collections/content", label: "Колекции: текст и SEO", icon: FileText },
  { to: "/admin/inventory", label: "Наличности", icon: Boxes },
  { to: "/admin/customers", label: "Клиенти", icon: Users },
  { to: "/admin/messages", label: "Запитвания", icon: MessageSquare },
  { to: "/admin/import", label: "Импорт", icon: Upload },
  { to: "/admin/translations", label: "Преводи", icon: Sparkles },
  { to: "/admin/locales", label: "Езици и URL", icon: Globe },
  { to: "/admin/pages", label: "Страници по език", icon: FileText },
  { to: "/admin/articles", label: "Блог статии", icon: Newspaper },
  { to: "/admin/ui-strings", label: "Текстове на чекаута", icon: Languages },
  { to: "/admin/delisted-links", label: "Изтеглени линкове", icon: Link2Off },
  { to: "/admin/integrations", label: "Интеграции", icon: Plug },
  { to: "/admin/settings", label: "Настройки", icon: Settings },
];

export default function AdminLayout({ children, title }) {
  const { user, logout, loading } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) nav("/admin/login");
  }, [user, loading, nav]);

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (loading || !user) return <div className="p-10 text-slate-500">Зареждане…</div>;

  return (
    <div className="min-h-screen bg-slate-50 lg:flex">
      {open && (
        <div className="fixed inset-0 bg-slate-900/50 z-40 lg:hidden" onClick={() => setOpen(false)}
          data-testid="admin-sidebar-overlay" />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-200 lg:static lg:z-auto lg:w-60 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        data-testid="admin-sidebar"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <Link to="/admin">
            <img src="/logo.svg" alt="PurePeptide" className="h-7 w-auto" />
            <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-1">Admin</p>
          </Link>
          <button onClick={() => setOpen(false)} className="lg:hidden p-2 -mr-2 text-slate-500"
            aria-label="Затвори менюто" data-testid="admin-sidebar-close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive ? "bg-coral-50 text-coral-700" : "text-slate-700 hover:bg-slate-50"
                }`
              }
              data-testid={`admin-nav-${to.split("/").pop() || "dashboard"}`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <p className="text-xs text-slate-500 mb-2 px-2 truncate">{user.email}</p>
          <button onClick={async () => { await logout(); nav("/admin/login"); }}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-slate-700 hover:bg-slate-50"
            data-testid="admin-logout-btn">
            <LogOut className="h-4 w-4" /> Изход
          </button>
          <Link to="/" className="block text-xs text-slate-500 hover:text-coral-600 mt-2 px-2">← Към магазина</Link>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <header className="bg-white border-b border-slate-200 px-4 lg:px-8 h-14 lg:h-16 flex items-center gap-3 sticky top-0 z-30">
          <button onClick={() => setOpen(true)} className="lg:hidden p-2 -ml-2 text-slate-700"
            aria-label="Отвори менюто" data-testid="admin-sidebar-toggle">
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="font-display font-bold text-lg lg:text-xl text-slate-900 truncate">{title}</h1>
        </header>
        <div className="p-4 sm:p-6 lg:p-8 min-w-0">{children}</div>
      </main>
    </div>
  );
}
