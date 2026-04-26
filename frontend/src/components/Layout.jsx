import { Link, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { ShoppingCart, Search, User, X, Truck, Banknote, Atom } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Button } from "./ui/button";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { api, fmtEUR, fmtBGN } from "../lib/api";

const NAV = [
  { to: "/collections/all-peptides", label: "Всички пептиди" },
  { to: "/collections/weight-loss", label: "Отслабване" },
  { to: "/collections/regeneration", label: "Възстановяване" },
  { to: "/collections/muscles", label: "Мускули" },
  { to: "/collections/skin-longevity", label: "Кожа" },
  { to: "/collections/melanin-and-libido", label: "Меланин" },
  { to: "/collections/immune-system", label: "Имунитет" },
];

const SearchDrawer = ({ open, setOpen }) => {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const nav = useNavigate();

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
    else { setQ(""); setResults([]); }
  }, [open]);

  useEffect(() => {
    if (!q || q.length < 2) { setResults([]); return; }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get(`/products?search=${encodeURIComponent(q)}&limit=8`);
        setResults(data.products);
      } finally { setLoading(false); }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const goTo = (handle) => { setOpen(false); nav(`/products/${handle}`); };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="top" className="h-auto max-h-[85vh] overflow-hidden flex flex-col" data-testid="search-drawer">
        <SheetHeader className="text-left">
          <SheetTitle>Търсене</SheetTitle>
        </SheetHeader>
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Търсене на пептиди…"
            className="w-full pl-10 pr-10 py-3 rounded-md border border-slate-300 focus:outline-none focus:border-coral-600 text-base"
            data-testid="search-input"
          />
          {q && (
            <button onClick={() => setQ("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="mt-4 overflow-y-auto -mx-6 px-6">
          {loading && <p className="text-sm text-slate-500">Зареждане…</p>}
          {!loading && q.length >= 2 && results.length === 0 && (
            <p className="text-sm text-slate-500">Няма резултати за „{q}".</p>
          )}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {results.map((p) => {
              const min = Math.min(...(p.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
              return (
                <button
                  key={p.id}
                  onClick={() => goTo(p.handle)}
                  className="text-left bg-white border border-slate-200 rounded-md p-3 hover:border-slate-400 transition-colors"
                  data-testid={`search-result-${p.handle}`}
                >
                  <div className="aspect-square bg-white">
                    <img src={p.image} alt={p.title} className="w-full h-full object-contain" />
                  </div>
                  <p className="text-sm font-medium text-slate-900 mt-2 line-clamp-2">{p.title}</p>
                  <p className="text-sm font-semibold text-slate-900 mt-1">
                    {fmtEUR(min)} <span className="text-xs text-slate-500 font-normal">({fmtBGN(min)})</span>
                  </p>
                </button>
              );
            })}
          </div>
          {q.length < 2 && (
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-3">Категории</p>
              <div className="flex flex-wrap gap-2">
                {NAV.map((n) => (
                  <Link
                    key={n.to}
                    to={n.to}
                    onClick={() => setOpen(false)}
                    className="px-3 py-1.5 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-slate-400"
                  >
                    {n.label}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
};

const Header = () => {
  const { count, items, subtotal, remove, updateQty, open, setOpen } = useCart();
  const { user, logout } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    api.get("/settings").then(({ data }) => setAnnouncement(data.announcement || ""));
  }, []);

  return (
    <>
      {announcement && (
        <div className="bg-slate-900 text-white text-xs sm:text-sm" data-testid="announcement-bar">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 text-center tracking-wide">
            {announcement}
          </div>
        </div>
      )}
      <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center" data-testid="logo-link" aria-label="PurePeptide">
            <img src="/logo.svg" alt="PurePeptide" className="h-7 sm:h-8 w-auto" />
          </Link>

          {/* Center search trigger (purepeptide.bg pattern) */}
          <button
            onClick={() => setSearchOpen(true)}
            className="hidden md:flex flex-1 max-w-md items-center gap-2 px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-500 hover:border-slate-400 transition-colors"
            data-testid="search-trigger-desktop"
          >
            <Search className="h-4 w-4" />
            <span>Търсене на пептиди…</span>
          </button>

          <div className="flex items-center gap-1">
            {user && user.role === "admin" && (
              <Link to="/admin" className="hidden md:inline text-xs uppercase tracking-wider text-coral-600 font-bold mr-2">
                Админ
              </Link>
            )}
            <button
              onClick={() => setSearchOpen(true)}
              className="md:hidden p-2 hover:bg-slate-50 rounded-md text-slate-700"
              data-testid="search-trigger-mobile"
              aria-label="Търсене"
            >
              <Search className="h-5 w-5" />
            </button>
            <Link
              to="/account"
              className="p-2 hover:bg-slate-50 rounded-md text-slate-700"
              data-testid="account-link"
              title={user ? user.email : "Вход"}
              aria-label="Профил"
            >
              <User className="h-5 w-5" />
            </Link>
            <button
              onClick={() => setOpen(true)}
              className="relative p-2 hover:bg-slate-50 rounded-md text-slate-700"
              data-testid="cart-button"
              aria-label="Количка"
            >
              <ShoppingCart className="h-5 w-5" />
              {count > 0 && (
                <span className="absolute -top-1 -right-1 bg-coral-600 text-white text-xs h-5 min-w-[20px] rounded-full flex items-center justify-center px-1 font-bold">
                  {count}
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      <SearchDrawer open={searchOpen} setOpen={setSearchOpen} />

      {/* Cart drawer */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-full sm:max-w-md flex flex-col" data-testid="cart-drawer">
          <SheetHeader>
            <SheetTitle>Количка ({count})</SheetTitle>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto -mx-6 px-6 py-4 space-y-4">
            {items.length === 0 && (
              <p className="text-slate-500 text-sm" data-testid="cart-empty">Количката е празна.</p>
            )}
            {items.map((it) => (
              <div key={it.variant_sku} className="flex gap-3 border-b border-slate-100 pb-4">
                <img src={it.image} alt={it.title} className="w-20 h-20 object-contain bg-white border border-slate-200 rounded" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{it.title}</p>
                  <p className="text-xs text-slate-500">{it.variant_name}</p>
                  <p className="text-sm font-semibold text-slate-900 mt-1">
                    {fmtEUR(it.price_eur)} <span className="text-xs text-slate-500 font-normal">({fmtBGN(it.price_eur)})</span>
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <button onClick={() => updateQty(it.variant_sku, it.quantity - 1)} className="w-7 h-7 border border-slate-300 rounded text-sm">−</button>
                    <span className="text-sm w-8 text-center">{it.quantity}</span>
                    <button onClick={() => updateQty(it.variant_sku, it.quantity + 1)} className="w-7 h-7 border border-slate-300 rounded text-sm">+</button>
                    <button onClick={() => remove(it.variant_sku)} className="ml-auto text-xs text-slate-500 hover:text-red-600">Премахни</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {items.length > 0 && (
            <div className="border-t border-slate-200 pt-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Междинна сума</span>
                <span className="font-semibold">{fmtEUR(subtotal)} <span className="text-slate-500 text-xs font-normal">({fmtBGN(subtotal)})</span></span>
              </div>
              <Button
                className="w-full bg-coral-600 hover:bg-coral-700"
                onClick={() => { setOpen(false); nav("/checkout"); }}
                data-testid="cart-checkout-btn"
              >
                Към плащане
              </Button>
              <Button variant="outline" className="w-full" onClick={() => { setOpen(false); nav("/cart"); }}>
                Виж количката
              </Button>
              {user && (
                <button onClick={async () => { await logout(); }} className="w-full text-xs text-slate-500 hover:text-slate-700">
                  Изход
                </button>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
};

const Footer = () => (
  <footer className="bg-slate-900 text-white mt-24" data-testid="footer">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 grid grid-cols-1 md:grid-cols-4 gap-10">
      <div className="md:col-span-2">
        <img src="/logo-white.svg" alt="PurePeptide" className="h-9 w-auto" />
        <p className="text-slate-300 text-sm mt-3 max-w-md leading-relaxed">
          Лиофилизирани пептиди с лабораторно доказана чистота над 99%. Тествани от Janoshik Labs.
        </p>
        <div className="mt-6 flex flex-col sm:flex-row gap-2 max-w-md">
          <input placeholder="Имейл за бюлетин" className="bg-slate-800 border border-slate-700 px-4 py-2.5 rounded-md text-sm flex-1 placeholder:text-slate-500 focus:outline-none focus:border-coral-600" data-testid="newsletter-input" />
          <button className="bg-coral-600 hover:bg-coral-700 px-5 py-2.5 rounded-md text-sm font-semibold">Абонирай се</button>
        </div>
      </div>
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-coral-600 mb-4 font-bold">Магазин</p>
        <ul className="space-y-2 text-sm text-slate-300">
          {NAV.map((n) => (
            <li key={n.to}><Link to={n.to} className="hover:text-white">{n.label}</Link></li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-coral-600 mb-4 font-bold">Помощ</p>
        <ul className="space-y-2 text-sm text-slate-300">
          <li><Link to="/account" className="hover:text-white">Моят профил</Link></li>
          <li><a href="#faq" className="hover:text-white">Въпроси и отговори</a></li>
          <li><span className="text-slate-400">Доставка с Еконт</span></li>
          <li><span className="text-slate-400">Наложен платеж</span></li>
        </ul>
      </div>
    </div>
    <div className="border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-xs text-slate-500 flex flex-col sm:flex-row justify-between gap-2">
        <span>© 2026 PurePeptide. Продуктите са за научноизследователски цели.</span>
        <span>Тествани от Janoshik Labs • &gt;99% чистота</span>
      </div>
    </div>
  </footer>
);

export const USPRow = () => (
  <section className="border-y border-slate-200 bg-white" data-testid="usp-row">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
      {[
        { Icon: Truck, title: "Експресна доставка", desc: "Всички поръчки се изпращат с Еконт" },
        { Icon: Banknote, title: "Наложен платеж", desc: "Надеждни и удобни методи за плащане" },
        { Icon: Atom, title: "Доказано качество", desc: "Тествани пептиди в Janoshik Labs" },
      ].map(({ Icon, title, desc }) => (
        <div key={title} className="flex items-start gap-4">
          <div className="w-12 h-12 bg-coral-50 text-coral-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Icon className="h-6 w-6" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="font-bold text-slate-900">{title}</h3>
            <p className="text-sm text-slate-500 mt-1">{desc}</p>
          </div>
        </div>
      ))}
    </div>
  </section>
);

export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
