import { useEffect, useState } from "react";
import { link } from "../lib/links";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Layout from "../components/Layout";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import { api, fmtPrice, formatErr } from "../lib/api";
import CancelOrderButton from "../components/CancelOrderButton";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { LOCALE_META } from "../i18n/locales";

const STATUS_CLS = {
  awaiting_payment: "bg-amber-100 text-amber-800 border-amber-300",
  paid: "bg-coral-100 text-coral-800 border-coral-300",
  cancelled: "bg-slate-200 text-slate-700 border-slate-300",
  shipped: "bg-emerald-100 text-emerald-800 border-emerald-300",
  fulfilled: "bg-emerald-100 text-emerald-800 border-emerald-300",
  unfulfilled: "bg-slate-100 text-slate-700 border-slate-300",
};
const STATUS_KEY = {
  awaiting_payment: "stAwaitingPayment", paid: "stPaid", cancelled: "stCancelled",
  shipped: "stShipped", fulfilled: "stFulfilled", unfulfilled: "stUnfulfilled",
};

export default function AccountPage() {
  const { t, locale } = useLocaleCtx();
  useSeo({ title: `${t("accountTitle")}`, description: t("accountTitle"), path: "/account", robots: "noindex,nofollow" });

  const { user, login, logout } = useAuth();
  const [orders, setOrders] = useState([]);
  const [li, setLi] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const loadOrders = () => api.get("/me/orders").then(({ data }) => setOrders(data.orders));
  useEffect(() => { if (user) loadOrders(); }, [user]);

  const doLogin = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(li.email, li.password);
      toast.success(t("welcomeToast"));
      if (u.role === "admin") nav("/admin");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  if (!user) {
    return (
      <Layout>
        <div className="max-w-md mx-auto px-4 py-16">
          <h1 className="font-display text-3xl font-extrabold text-slate-900 mb-8 text-center">{t("accountTitle")}</h1>
          <form onSubmit={doLogin} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 mt-4" data-testid="login-form">
            <div><Label>{t("emailLabel")}</Label><Input type="email" required value={li.email} onChange={(e) => setLi({...li, email: e.target.value})} data-testid="login-email" /></div>
            <div><Label>{t("passwordLabel")}</Label><Input type="password" required value={li.password} onChange={(e) => setLi({...li, password: e.target.value})} data-testid="login-password" /></div>
            <Button type="submit" disabled={busy} className="w-full bg-coral-600 hover:bg-coral-700" data-testid="login-submit">{busy ? "…" : t("loginBtn")}</Button>
            <p className="text-xs text-slate-500 text-center leading-relaxed">
              {t("accountsInfo", { email: "info@purepeptide.bg" })}
            </p>
          </form>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="font-display text-4xl font-extrabold text-slate-900">{t("accountGreeting", { name: user.name || user.email })}</h1>
            <p className="text-slate-500 mt-2">{user.email}</p>
          </div>
          <Button variant="outline" onClick={logout} data-testid="logout-btn">{t("logoutBtn")}</Button>
        </div>

        <h2 className="font-display text-2xl font-bold text-slate-900 mb-4">{t("myOrdersTitle")}</h2>
        {orders.length === 0 ? (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-10 text-center text-slate-500">
            {t("noOrdersText")} <Link to={link("catalog")} className="text-coral-600 font-medium">{t("toCatalog")} →</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((o) => {
              const badge = (state) => ({
                label: STATUS_KEY[state] ? t(STATUS_KEY[state]) : state,
                cls: STATUS_CLS[state] || "bg-slate-100 text-slate-700 border-slate-300",
              });
              const ps = badge(o.payment_status);
              const fs = badge(o.fulfillment_status);
              return (
                <div key={o.id} className="bg-white border border-slate-200 rounded-xl p-5 flex flex-wrap gap-4 items-center" data-testid={`order-${o.order_number}`}>
                  <div>
                    <p className="font-mono font-semibold text-slate-900">{o.order_number}</p>
                    <p className="text-xs text-slate-500">{new Date(o.created_at).toLocaleDateString((LOCALE_META[locale] || {}).hreflang || "en-GB")}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge className={`${ps.cls} border`}>{ps.label}</Badge>
                    <Badge className={`${fs.cls} border`}>{fs.label}</Badge>
                  </div>
                  <div className="ml-auto text-right">
                    <p className="font-display font-bold text-slate-900">{fmtPrice(o.total_eur)}</p>
                    <p className="text-xs text-slate-500">{t("itemsCount", { n: o.items.length })}</p>
                  </div>
                  <CancelOrderButton order={o} onDone={loadOrders} className="w-full sm:w-auto" />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
