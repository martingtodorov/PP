import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import {
  ShoppingBag, Search, X, Truck, Banknote, Atom, Menu, ChevronLeft, ChevronRight, ChevronDown,
  Minus, Plus, Tag, MessageSquare,
} from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "./ui/sheet";
import { Button } from "./ui/button";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { LOCALES, LOCALE_META } from "../i18n/locales";
import { api, fmtEUR, fmtBGN, showsBGN, formatErr, img } from "../lib/api";
import { toast } from "sonner";

const Price = ({ eur, className = "" }) => (
  <span className={className}>
    {fmtEUR(eur)}
    {showsBGN() && <span className="text-slate-500 font-normal text-[12px] ml-1.5">({fmtBGN(eur)})</span>}
  </span>
);

/* ---------------- Announcement bar (coral, arrow carousel) ---------------- */
const AnnouncementBar = ({ messages }) => {
  const [i, setI] = useState(0);
  const list = messages && messages.length ? messages : [];
  useEffect(() => {
    if (list.length < 2) return;
    const t = setInterval(() => setI((v) => (v + 1) % list.length), 5000);
    return () => clearInterval(t);
  }, [list.length]);
  if (!list.length) return null;

  return (
    <div className="pp-announce" data-testid="announcement-bar">
      <button
        type="button"
        className="pp-announce__nav"
        aria-label="Previous announcement"
        onClick={() => setI((v) => (v - 1 + list.length) % list.length)}
        data-testid="announcement-prev"
      >
        <ChevronLeft className="h-5 w-5" />
      </button>
      <p className="pp-announce__text" data-testid="announcement-text">{list[i]}</p>
      <button
        type="button"
        className="pp-announce__nav"
        aria-label="Next announcement"
        onClick={() => setI((v) => (v + 1) % list.length)}
        data-testid="announcement-next"
      >
        <ChevronRight className="h-5 w-5" />
      </button>
    </div>
  );
};

/* ---------------- Search drawer ---------------- */
const SearchDrawer = ({ open, setOpen, collections }) => {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const nav = useNavigate();
  const { lp, t } = useLocaleCtx();

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
    else { setQ(""); setResults([]); }
  }, [open]);

  useEffect(() => {
    if (!q || q.length < 2) { setResults([]); return; }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get(`/products?search=${encodeURIComponent(q)}&limit=8`);
        setResults(data.products);
      } finally { setLoading(false); }
    }, 200);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="top" className="h-auto max-h-[85vh] overflow-hidden flex flex-col" data-testid="search-drawer">
        <SheetHeader className="text-left">
          <SheetTitle>{t("search")}</SheetTitle>
          <SheetDescription className="sr-only">{t("searchPlaceholder")}</SheetDescription>
        </SheetHeader>
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full pl-10 pr-10 py-3 rounded-md border border-slate-300 focus:outline-none focus:border-coral-600 text-base"
            data-testid="search-input"
          />
          {q && (
            <button onClick={() => setQ("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" aria-label="clear">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="mt-4 overflow-y-auto -mx-6 px-6">
          {loading && <p className="text-sm text-slate-500">{t("loading")}</p>}
          {!loading && q.length >= 2 && results.length === 0 && (
            <p className="text-sm text-slate-500" data-testid="search-no-results">{t("noResults")} „{q}"</p>
          )}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {results.map((p) => {
              const min = Math.min(...(p.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
              return (
                <button
                  key={p.id}
                  onClick={() => { setOpen(false); nav(lp(`/products/${p.handle}`)); }}
                  className="text-left bg-white border border-slate-200 rounded-md p-3 hover:border-slate-400 transition-colors"
                  data-testid={`search-result-${p.handle}`}
                >
                  <div className="aspect-square bg-white">
                    <img src={img(p.image, 160)} alt={p.title} className="w-full h-full object-contain" loading="lazy" decoding="async" />
                  </div>
                  <p className="text-sm font-medium text-slate-900 mt-2 line-clamp-2">{p.title}</p>
                  <Price eur={min} className="text-sm font-semibold text-slate-900 mt-1 block" />
                </button>
              );
            })}
          </div>
          {q.length < 2 && (
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-3">{t("categories")}</p>
              <div className="flex flex-wrap gap-2">
                {collections.map((c) => (
                  <Link
                    key={c.handle}
                    to={lp(`/collections/${c.handle}`)}
                    onClick={() => setOpen(false)}
                    className="px-3 py-1.5 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-slate-400"
                  >
                    {c.title}
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

/* ---------------- Left drawer navigation ---------------- */
const NavDrawer = ({ open, setOpen, collections }) => {
  const { lp, t } = useLocaleCtx();
  const [shopOpen, setShopOpen] = useState(true);
  const close = () => setOpen(false);
  const menu = [...collections].sort((a, b) => (a.menu_order ?? 99) - (b.menu_order ?? 99));

  const links = [
    { to: lp("/"), label: t("home") },
    { to: lp("/pages/какво-са-пептиди"), label: t("whatArePeptides") },
    { to: lp("/pages/articles"), label: t("articles") },
    { to: lp("/pages/contact-1"), label: t("contacts") },
    { to: lp("/pages/chemical-analysis"), label: t("chemicalAnalysis") },
    { to: lp("/pages/faq"), label: t("faq") },
    { to: lp("/pages/become-a-distributor"), label: t("partners") },
  ];

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="left" className="w-[88vw] sm:w-[400px] p-0 flex flex-col pp-drawer-panel" data-testid="nav-drawer">
        <SheetHeader className="px-5 pt-4 pb-1 text-left">
          <SheetTitle className="sr-only">{t("menu")}</SheetTitle>
          <SheetDescription className="sr-only">{t("categories")}</SheetDescription>
          <button
            type="button"
            onClick={close}
            className="w-9 h-9 -ml-1 flex items-center justify-center text-slate-900"
            aria-label={t("close")}
            data-testid="nav-drawer-close"
          >
            <X className="h-6 w-6" strokeWidth={1.6} />
          </button>
        </SheetHeader>
        <nav className="pp-drawer flex-1 overflow-y-auto px-5 pb-10">
          <Link to={links[0].to} onClick={close} className="pp-drawer__link" data-testid="drawer-link-home">
            {t("home")}
          </Link>

          <button
            type="button"
            className="pp-drawer__link pp-drawer__link--toggle"
            onClick={() => setShopOpen((v) => !v)}
            data-testid="drawer-shop-toggle"
          >
            <span>{t("shop")}</span>
            <span className="pp-drawer__sign">{shopOpen ? <Minus className="h-5 w-5" /> : <Plus className="h-5 w-5" />}</span>
          </button>
          {shopOpen && (
            <ul className="pp-drawer__sub" data-testid="drawer-shop-submenu">
              {menu.map((c) => (
                <li key={c.handle}>
                  <Link
                    to={lp(`/collections/${c.handle}`)}
                    onClick={close}
                    className="pp-drawer__sublink"
                    data-testid={`drawer-collection-${c.handle}`}
                  >
                    {c.menu_title || c.title}
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {links.slice(1).map((l) => (
            <Link
              key={l.to + l.label}
              to={l.to}
              onClick={close}
              className="pp-drawer__link"
              data-testid={`drawer-link-${l.label.toLowerCase().replace(/[^a-zа-я]+/gi, "-")}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
};

/* ---------------- Cart drawer ---------------- */
const CartDrawer = () => {
  const {
    items, count, subtotal, remove, updateQty, open, setOpen,
    note, setNote, discount, applyDiscount, removeDiscount, discountAmount, total,
  } = useCart();
  const { lp, t, locale } = useLocaleCtx();
  const [code, setCode] = useState("");
  const [terms, setTerms] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const submitCode = async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      const data = await applyDiscount(code.trim());
      toast.success(`Код ${data.code} е приложен`);
      setCode("");
    } catch (e) {
      toast.error(formatErr(e));
    } finally { setBusy(false); }
  };

  const goCheckout = () => {
    if (!terms) {
      toast.error(locale === "bg" ? "Моля, приемете общите условия" : "Please accept the terms & conditions");
      return;
    }
    setOpen(false);
    nav(lp("/checkout"));
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent className="w-[88vw] sm:w-[400px] sm:max-w-none flex flex-col p-0" data-testid="cart-drawer">
        <div className="pp-drawer-right flex flex-col h-full min-h-0">
        <SheetHeader className="px-6 pt-6 pb-3 border-b border-slate-100">
          <SheetTitle>{t("cart")} ({count})</SheetTitle>
          <SheetDescription className="sr-only">{t("subtotal")}</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {items.length === 0 && (
            <p className="text-slate-500 text-sm" data-testid="cart-empty">{t("cartEmpty")}</p>
          )}
          {items.map((it) => (
            <div key={it.variant_sku} className="flex gap-3 border-b border-slate-100 pb-4" data-testid={`cart-line-${it.variant_sku}`}>
              <img src={img(it.image, 160)} alt={it.title} className="w-20 h-20 object-contain bg-white border border-slate-200 rounded" loading="lazy" decoding="async" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900">{it.title}</p>
                <p className="text-xs text-slate-500">{it.variant_name}</p>
                <Price eur={it.price_eur} className="text-sm font-semibold text-slate-900 mt-1 block" />
                <div className="flex items-center gap-2 mt-2">
                  <button onClick={() => updateQty(it.variant_sku, it.quantity - 1)} className="w-7 h-7 border border-slate-300 rounded text-sm" aria-label="-">−</button>
                  <span className="text-sm w-8 text-center" data-testid={`cart-qty-${it.variant_sku}`}>{it.quantity}</span>
                  <button onClick={() => updateQty(it.variant_sku, it.quantity + 1)} className="w-7 h-7 border border-slate-300 rounded text-sm" aria-label="+">+</button>
                  <button onClick={() => remove(it.variant_sku)} className="ml-auto text-xs text-slate-500 hover:text-red-600" data-testid={`cart-remove-${it.variant_sku}`}>
                    {t("remove")}
                  </button>
                </div>
              </div>
            </div>
          ))}

          {items.length > 0 && (
            <>
              {/* Special instructions */}
              <div className="border border-slate-200 rounded-lg">
                <button
                  type="button"
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-sm font-medium text-slate-800"
                  onClick={() => setNoteOpen((v) => !v)}
                  data-testid="cart-note-toggle"
                >
                  <MessageSquare className="h-4 w-4 text-coral-600" />
                  {locale === "bg" ? "Специални инструкции към поръчката" : "Special instructions"}
                  <span className="ml-auto text-slate-400">{noteOpen ? "−" : "+"}</span>
                </button>
                {noteOpen && (
                  <div className="px-3 pb-3">
                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      rows={3}
                      placeholder={locale === "bg" ? "Напр. предпочитан офис на Спиди, час за доставка…" : "e.g. preferred pickup point, delivery time…"}
                      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-coral-600"
                      data-testid="cart-note-input"
                    />
                  </div>
                )}
              </div>

              {/* Discount code */}
              <div className="border border-slate-200 rounded-lg px-3 py-3">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-800 mb-2">
                  <Tag className="h-4 w-4 text-coral-600" />
                  {locale === "bg" ? "Код за отстъпка" : "Discount code"}
                </label>
                {discount ? (
                  <div className="flex items-center justify-between text-sm" data-testid="cart-discount-applied">
                    <span className="font-mono font-semibold text-coral-700">{discount.code}</span>
                    <button onClick={removeDiscount} className="text-xs text-slate-500 hover:text-red-600" data-testid="cart-discount-remove">
                      {t("remove")}
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <input
                      value={code}
                      onChange={(e) => setCode(e.target.value.toUpperCase())}
                      placeholder="WELCOME10"
                      className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm uppercase focus:outline-none focus:border-coral-600"
                      data-testid="cart-discount-input"
                    />
                    <button
                      onClick={submitCode}
                      disabled={busy}
                      className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:opacity-50"
                      data-testid="cart-discount-apply"
                    >
                      {locale === "bg" ? "Приложи" : "Apply"}
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {items.length > 0 && (
          <div className="border-t border-slate-200 p-6 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">{t("subtotal")}</span>
              <Price eur={subtotal} className="font-semibold" />
            </div>
            {discountAmount > 0 && (
              <div className="flex justify-between text-sm text-coral-700" data-testid="cart-discount-row">
                <span>{locale === "bg" ? "Отстъпка" : "Discount"} ({discount?.code})</span>
                <span className="font-semibold">− {fmtEUR(discountAmount)}</span>
              </div>
            )}
            <div className="flex justify-between text-base border-t border-slate-100 pt-3">
              <span className="font-semibold text-slate-900">{locale === "bg" ? "Общо" : "Total"}</span>
              <Price eur={total} className="font-bold" />
            </div>

            <label className="flex items-start gap-2 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={terms}
                onChange={(e) => setTerms(e.target.checked)}
                className="mt-0.5 accent-coral-600"
                data-testid="cart-terms-checkbox"
              />
              <span>
                {locale === "bg" ? "Съгласявам се с " : "I agree to the "}
                <Link to={lp("/pages/terms-conditions")} className="underline hover:text-coral-600" onClick={() => setOpen(false)}>
                  {locale === "bg" ? "общите условия" : "terms & conditions"}
                </Link>
                {locale === "bg" ? " и политиката за поверителност." : " and privacy policy."}
              </span>
            </label>

            <Button
              className="w-full h-14 text-base sm:text-lg font-semibold bg-coral-600 hover:bg-coral-700 disabled:opacity-50"
              onClick={goCheckout}
              disabled={!terms}
              data-testid="cart-checkout-btn"
            >
              {t("checkout")}
            </Button>
          </div>
        )}
        </div>
      </SheetContent>
    </Sheet>
  );
};

/* ---------------- Header ---------------- */
const Header = ({ collections, settings }) => {
  const { count, setOpen } = useCart();
  const { user } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const { lp, t, locale } = useLocaleCtx();
  const { pathname, hash } = useLocation();

  const topNav = [
    { to: lp("/"), label: t("home"), exact: true },
    { to: lp("/collections/2all-the-peptides-1"), label: t("shop"), dropdown: true },
    { to: lp("/pages/какво-са-пептиди"), label: t("whatArePeptides") },
    { to: lp("/pages/articles"), label: t("articles") },
    { to: lp("/pages/contact-1"), label: t("contacts") },
    { to: lp("/pages/chemical-analysis"), label: t("chemicalAnalysis") },
    { to: lp("/pages/faq"), label: t("faq") },
    { to: lp("/pages/become-a-distributor"), label: t("partners") },
  ];

  const menuCollections = [...collections].sort((a, b) => (a.menu_order ?? 99) - (b.menu_order ?? 99));

  const isActive = (item) => {
    const [path] = item.to.split("#");
    if (item.exact) return pathname === path && !hash;
    return pathname === path;
  };

  return (
    <>
      <AnnouncementBar messages={(settings.announcements_i18n || {})[locale] || settings.announcements} />

      <header className="sticky top-0 z-40 bg-white border-b border-slate-200" data-testid="site-header">
        {/* ---------- mobile / tablet ---------- */}
        <div className="lg:hidden max-w-7xl mx-auto px-4 sm:px-6 h-16 relative flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setNavOpen(true)}
              className="p-2 -ml-2 rounded-md text-slate-800 hover:bg-slate-50"
              aria-label={t("menu")}
              data-testid="nav-drawer-trigger"
            >
              <Menu className="h-6 w-6" strokeWidth={1.7} />
            </button>
            <button
              onClick={() => setSearchOpen(true)}
              className="p-2 rounded-md text-slate-800 hover:bg-slate-50"
              aria-label={t("search")}
              data-testid="search-trigger"
            >
              <Search className="h-5 w-5" strokeWidth={1.8} />
            </button>
          </div>

          <Link
            to={lp("/")}
            className="absolute left-1/2 -translate-x-1/2 flex items-center"
            data-testid="logo-link"
            aria-label="PurePeptide"
          >
            <img
              src="/logo-header.png"
              alt="PurePeptide"
              width="220"
              height="44"
              className="h-9 w-auto"
              fetchPriority="high"
              decoding="async"
            />
          </Link>

          <button
            onClick={() => setOpen(true)}
            className="relative p-2 -mr-2 rounded-md text-slate-800 hover:bg-slate-50"
            data-testid="cart-button"
            aria-label={t("cart")}
          >
            <ShoppingBag className="h-5 w-5" strokeWidth={1.8} />
            {count > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-coral-600 text-white text-[11px] h-5 min-w-[20px] rounded-full flex items-center justify-center px-1 font-bold" data-testid="cart-count">
                {count}
              </span>
            )}
          </button>
        </div>

        {/* ---------- desktop: one row, logo left of the nav, search next to cart ---------- */}
        <div className="hidden lg:flex max-w-7xl mx-auto px-6 xl:px-8 h-20 items-center gap-8" data-testid="desktop-header">
          <Link to={lp("/")} className="flex-shrink-0" aria-label="PurePeptide" data-testid="logo-link-desktop">
            <img src="/logo-header.png" alt="PurePeptide" width="240" height="48" className="h-10 w-auto" fetchPriority="high" decoding="async" />
          </Link>

          <nav className="flex items-center gap-7" aria-label="Primary" data-testid="desktop-nav">
            {topNav.map((n) =>
              n.dropdown ? (
                <div key={n.label} className="relative group" data-testid="shop-dropdown-wrap">
                  <NavLink to={n.to} className={`pp-desknav__link${isActive(n) ? " is-active" : ""}`} data-testid="nav-shop">
                    {n.label}
                    <ChevronDown className="h-3.5 w-3.5 ml-1 inline-block transition-transform group-hover:rotate-180" />
                  </NavLink>
                  <div className="pp-megamenu" data-testid="shop-dropdown">
                    <ul>
                      {menuCollections.map((c) => (
                        <li key={c.handle}>
                          <Link to={lp(`/collections/${c.handle}`)} data-testid={`dropdown-collection-${c.handle}`}>
                            {c.menu_title || c.title}
                          </Link>
                        </li>
                      ))}
                      <li className="pp-megamenu__all">
                        <Link to={lp("/collections/2all-the-peptides-1")} data-testid="dropdown-collection-all">
                          {t("viewAll")} →
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              ) : (
                <NavLink
                  key={n.label}
                  to={n.to}
                  className={`pp-desknav__link${isActive(n) ? " is-active" : ""}`}
                  data-testid={`nav-${n.label.toLowerCase().replace(/[^a-zа-я0-9]+/gi, "-")}`}
                >
                  {n.label}
                </NavLink>
              )
            )}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {user?.role === "admin" && (
              <Link to="/admin" className="text-xs uppercase tracking-wider text-coral-600 font-bold mr-2">Admin</Link>
            )}
            <button onClick={() => setSearchOpen(true)} className="p-2 rounded-md text-slate-800 hover:bg-slate-50"
              aria-label={t("search")} data-testid="search-trigger-desktop">
              <Search className="h-5 w-5" strokeWidth={1.8} />
            </button>
            <button onClick={() => setOpen(true)} className="relative p-2 rounded-md text-slate-800 hover:bg-slate-50"
              aria-label={t("cart")} data-testid="cart-button-desktop">
              <ShoppingBag className="h-5 w-5" strokeWidth={1.8} />
              {count > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-coral-600 text-white text-[11px] h-5 min-w-[20px] rounded-full flex items-center justify-center px-1 font-bold">
                  {count}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* sliding text nav — mobile only */}
        <nav className="pp-topnav lg:hidden" data-testid="sliding-nav" aria-label="Primary mobile">
          <ul>
            {topNav.map((n) => (
              <li key={n.label}>
                <NavLink
                  to={n.to}
                  className={`pp-topnav__link${isActive(n) ? " is-active" : ""}`}
                  data-testid={`nav-m-${n.label.toLowerCase().replace(/[^a-zа-я0-9]+/gi, "-")}`}
                >
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <NavDrawer open={navOpen} setOpen={setNavOpen} collections={collections} />
      <SearchDrawer open={searchOpen} setOpen={setSearchOpen} collections={collections} />
      <CartDrawer />
    </>
  );
};

/* ---------------- Footer with dense internal linking ---------------- */
const Footer = ({ collections, articles, settings }) => {
  const { lp, t, localeUrl, basePath, locale } = useLocaleCtx();

  return (
    <footer className="bg-slate-900 text-white mt-20" data-testid="footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 grid grid-cols-1 md:grid-cols-4 gap-10">
        <div>
          <img src="/logo-white.svg" alt="PurePeptide" className="h-8 w-auto" />
          <p className="text-slate-300 text-sm mt-3 leading-relaxed">{locale === "bg" ? (settings.tagline || t("tagline")) : t("tagline")}</p>
          <p className="text-sm font-semibold mt-5">{t("newsletter")}</p>
          <p className="text-xs text-slate-400 mt-1">{t("newsletterSub")}</p>
          <div className="mt-3 flex gap-2">
            <input
              placeholder={t("email")}
              className="bg-slate-800 border border-slate-700 px-3 py-2 rounded-md text-sm flex-1 min-w-0 placeholder:text-slate-500 focus:outline-none focus:border-coral-600"
              data-testid="newsletter-input"
            />
            <button className="bg-coral-600 hover:bg-coral-700 px-4 py-2 rounded-md text-sm font-semibold whitespace-nowrap">
              {t("subscribe")}
            </button>
          </div>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-coral-500 mb-4 font-bold">{t("shopLinks")}</p>
          <ul className="space-y-2 text-sm text-slate-300">
            {collections.map((c) => (
              <li key={c.handle}>
                <Link to={lp(`/collections/${c.handle}`)} className="hover:text-white">{c.title}</Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-coral-500 mb-4 font-bold">{t("articles")}</p>
          <ul className="space-y-2 text-sm text-slate-300">
            {articles.slice(0, 5).map((a) => (
              <li key={a.handle}>
                <Link to={lp(`/articles/${a.handle}`)} className="hover:text-white line-clamp-2">{a.title}</Link>
              </li>
            ))}
          </ul>
          <p className="text-xs uppercase tracking-[0.2em] text-coral-500 mb-3 mt-6 font-bold">{t("help")}</p>
          <ul className="space-y-2 text-sm text-slate-300">
            <li><Link to={lp("/pages/faq")} className="hover:text-white">{t("faq")}</Link></li>
            <li><Link to={lp("/pages/chemical-analysis")} className="hover:text-white">{t("chemicalAnalysis")}</Link></li>
            <li><Link to={lp("/pages/contact-1")} className="hover:text-white">{t("contacts")}</Link></li>
            <li><Link to={lp("/account")} className="hover:text-white">{t("account")}</Link></li>
          </ul>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-coral-500 mb-4 font-bold">{t("policies")}</p>
          <ul className="space-y-2 text-sm text-slate-300">
            <li><Link to={lp("/pages/privacy-policy")} className="hover:text-white">{t("policyPrivacy")}</Link></li>
            <li><Link to={lp("/pages/refund-policy")} className="hover:text-white">{t("policyRefund")}</Link></li>
            <li><Link to={lp("/pages/terms-conditions")} className="hover:text-white">{t("policyTerms")}</Link></li>
            <li><Link to={lp("/pages/delivery-and-payment")} className="hover:text-white">{t("policyShipping")}</Link></li>
            <li><Link to={lp("/pages/html-sitemap")} className="hover:text-white" data-testid="footer-html-sitemap">Карта на сайта</Link></li>
          </ul>
          <p className="text-xs uppercase tracking-[0.2em] text-coral-500 mb-3 mt-6 font-bold">{t("otherCountries")}</p>
          <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm text-slate-300" data-testid="footer-locales">
            {LOCALES.filter((l) => l !== locale).map((l) => (
              <li key={l}>
                <a href={localeUrl(l, basePath)} className="hover:text-white" hrefLang={LOCALE_META[l].hreflang} data-testid={`footer-locale-${l}`}>
                  {LOCALE_META[l].label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-xs text-slate-500 space-y-2">
          <p>{locale === "bg" ? (settings.footer_text || t("footerDisclaimer")) : t("footerDisclaimer")}</p>
          <p>© 2026 PurePeptide · Janoshik Labs tested · &gt;99% purity</p>
        </div>
      </div>
    </footer>
  );
};

export const USPRow = () => {
  const { t } = useLocaleCtx();
  return (
    <section className="border-y border-slate-200 bg-white" data-testid="usp-row">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
        {[
          { Icon: Truck, title: t("uspShippingTitle"), desc: t("uspShippingDesc") },
          { Icon: Banknote, title: t("uspPayTitle"), desc: t("uspPayDesc") },
          { Icon: Atom, title: t("uspQualityTitle"), desc: t("uspQualityDesc") },
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
};

export default function Layout({ children }) {
  const [collections, setCollections] = useState([]);
  const [articles, setArticles] = useState([]);
  const [settings, setSettings] = useState({});
  const { locale } = useLocaleCtx();
  const { pathname } = useLocation();

  useEffect(() => {
    Promise.all([api.get("/collections"), api.get("/articles"), api.get("/settings")]).then(
      ([c, a, s]) => {
        setCollections(c.data.collections.filter((x) => (x.base_handle || x.handle) !== "2all-the-peptides-1" && !x.nav_hidden));
        setArticles(a.data.articles);
        setSettings(s.data);
      }
    );
  }, [locale]);

  useEffect(() => {
    let sid = sessionStorage.getItem("pp_sid");
    if (!sid) {
      sid = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random())).slice(0, 36);
      sessionStorage.setItem("pp_sid", sid);
    }
    api.post("/track", { session_id: sid, path: pathname, referrer: document.referrer || "", locale }).catch(() => {});
  }, [pathname, locale]);

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Header collections={collections} settings={settings} />
      <main id="main-content" className="flex-1">{children}</main>
      <Footer collections={collections} articles={articles} settings={settings} />
    </div>
  );
}
